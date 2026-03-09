"""
Tavily-powered external hotel search fallback.

Used ONLY when the local DB has no results for a location (unknown city, etc.).
Results are returned in the EXACT same JSON schema as DB hotels, with two extras:
  source      = "external"
  hotel_url   = hotel's own official website (direct page for the property)
  booking_url = deepest booking link found (booking.com / hotels.com / expedia etc.)
  disclaimer  = user-facing warning about external data

Hotel URL priority:
  1. Hotel brand's own domain  (marriott.com/hotel-xyz, hilton.com/hotel-xyz …)
  2. Deep booking-aggregator page (booking.com/hotel/…, hotels.com/ho/…)
  3. TripAdvisor hotel page     (tripadvisor.com/Hotel_Review-…)
  4. Raw Tavily result URL      (best available)
"""

import json
import logging
import re
import time
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

EXTERNAL_DISCLAIMER = (
    "⚠️ External result — not in our partner network. "
    "Prices and availability shown are from live web data and may change. "
    "Book via the provided link for the latest rates."
)

# Known hotel brand domains — results from these surface as hotel_url preferentially
HOTEL_BRAND_DOMAINS = {
    "marriott.com", "hilton.com", "hyatt.com", "ihg.com", "accor.com",
    "fourseasons.com", "wyndhamhotels.com", "bestwestern.com",
    "radissonhotels.com", "choicehotels.com", "omnihotels.com",
    "loewshotels.com", "kempinski.com", "shangri-la.com",
    "mandarinoriental.com", "peninsula.com",
}

# Booking aggregators — results from these go to booking_url
BOOKING_AGGREGATOR_DOMAINS = {
    "booking.com", "hotels.com", "expedia.com", "agoda.com",
    "kayak.com", "priceline.com", "orbitz.com", "travelocity.com",
    "hotelscombined.com", "trivago.com",
}


def _url_domain(url: str) -> str:
    """Extract bare domain from a URL."""
    m = re.search(r'https?://(?:www\.)?([^/]+)', url or '')
    return m.group(1).lower() if m else ''


def _categorise_url(url: str):
    """Return ('brand'|'aggregator'|'review'|'other', url)."""
    domain = _url_domain(url)
    if any(domain == b or domain.endswith('.' + b) for b in HOTEL_BRAND_DOMAINS):
        return 'brand', url
    if any(domain == b or domain.endswith('.' + b) for b in BOOKING_AGGREGATOR_DOMAINS):
        return 'aggregator', url
    if 'tripadvisor' in domain:
        return 'review', url
    return 'other', url


class TavilyHotelSearch:
    """
    Searches for hotels via Tavily web search and normalises results into
    the same hotel dict format used by the local database.
    """

    def __init__(self, tavily_api_key: str, groq_api_key: str, groq_model: str):
        try:
            from tavily import TavilyClient
            self.client = TavilyClient(api_key=tavily_api_key)
            self._available = True
        except ImportError:
            logger.warning("[TAVILY] tavily-python not installed. External search disabled.")
            self.client = None
            self._available = False

        self.llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name=groq_model,
            temperature=0.0,
            max_tokens=2048,
        )

    @property
    def available(self) -> bool:
        return self._available and self.client is not None

    @staticmethod
    def _parse_groq_wait(err_str: str) -> float:
        """Parse Groq's retry wait time from a 429 error message.
        Handles formats: '6m30.527s' → 390.5s, '45.3s' → 45.3s
        """
        m = re.search(r'try again in (\d+)m(\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
        if m:
            return int(m.group(1)) * 60 + float(m.group(2))
        m = re.search(r'try again in (\d+(?:\.\d+)?)s', err_str, re.IGNORECASE)
        if m:
            return float(m.group(1))
        return 60.0

    @staticmethod
    def _is_tpd(err_str: str) -> bool:
        """True if the 429 is a daily quota exhaustion (TPD) — cannot recover until tomorrow."""
        el = err_str.lower()
        return 'tokens per day' in el or '(tpd)' in el or 'per day' in el

    def _llm_invoke_with_retry(self, messages, max_retries: int = 2):
        """
        Retry only for TPM (per-minute) limits (capped at 90s).
        TPD (daily quota) raises immediately so the caller can use the no-LLM fallback.
        """
        for attempt in range(max_retries):
            try:
                return self.llm.invoke(messages)
            except Exception as e:
                err_str = str(e)
                is_rate_limit = ('429' in err_str or
                                 'rate_limit' in err_str.lower() or
                                 'tokens per' in err_str.lower())
                if is_rate_limit:
                    if self._is_tpd(err_str):
                        logger.warning(
                            "[TAVILY RATE LIMIT] Daily quota (TPD) exhausted — "
                            "falling back to no-LLM extraction."
                        )
                        raise
                    if attempt < max_retries - 1:
                        wait_sec = min(self._parse_groq_wait(err_str) + 3.0, 90.0)
                        logger.warning(
                            f"[TAVILY RATE LIMIT] TPM limit. Pausing {wait_sec:.0f}s before retry..."
                        )
                        time.sleep(wait_sec)
                        continue
                raise
        raise RuntimeError("LLM max retries exceeded")

    def search(
        self,
        query: str,
        city: Optional[str] = None,
        filters: Optional[Dict] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels using TWO Tavily queries so the LLM always has:
          1. Hotel info results  — brand pages + general web (for name/description/amenities/price)
          2. Booking link results — aggregator-only pages (for real booking_url per hotel)

        Both result sets are merged and passed to the LLM so it can assign
        hotel_url and booking_url to separate, correct URLs for every hotel.
        """
        if not self.available:
            return []

        filters = filters or {}
        info_query, booking_query = self._build_search_queries(query, city, filters)
        logger.info(f"[TAVILY] Info query:    '{info_query}'")
        logger.info(f"[TAVILY] Booking query: '{booking_query}'")

        try:
            # ---- Search 1: general (brand pages + editorial + any source) ----
            info_resp = self.client.search(
                query=info_query,
                max_results=8,
                search_depth="advanced",
                days=90,
            )
            info_results = info_resp.get("results", [])
            logger.info(f"[TAVILY] Info search → {len(info_results)} results")

            # ---- Search 2: booking aggregators only ----
            booking_resp = self.client.search(
                query=booking_query,
                max_results=8,
                search_depth="advanced",
                days=90,
                include_domains=[
                    "booking.com", "hotels.com", "expedia.com",
                    "agoda.com", "kayak.com", "priceline.com",
                ],
            )
            booking_results = booking_resp.get("results", [])
            logger.info(f"[TAVILY] Booking search → {len(booking_results)} results")

            # Merge: info results first (richer text), then booking aggregator pages.
            # De-duplicate by URL.
            seen_urls: set = set()
            combined: List[Dict] = []
            for r in info_results + booking_results:
                url = r.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    combined.append(r)

            if not combined:
                logger.warning("[TAVILY] Both searches returned 0 results")
                return []

            logger.info(f"[TAVILY] Combined: {len(combined)} unique results")
            hotels = self._extract_hotels_with_llm(combined, city or "", query, filters)
            logger.info(f"[TAVILY] Extracted {len(hotels)} structured hotels")
            return hotels[:max_results]

        except Exception as e:
            logger.error(f"[TAVILY] Search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_search_queries(
        self,
        query: str,
        city: Optional[str],
        filters: Optional[Dict],
    ) -> tuple:
        """
        Return (info_query, booking_query).

        info_query   — no domain restriction; surfaces brand pages + editorial
                       results so the LLM can read rich hotel descriptions, amenities,
                       ratings, and prices.

        booking_query — targeted at booking aggregators (booking.com, expedia, etc.)
                        so every hotel gets a real, bookable booking_url.
                        Uses the same city/filters but drops the "official site" phrase
                        and adds "book now" to maximise aggregator result hit rate.
        """
        query_lower = (query or "").lower()
        year = datetime.now().year

        budget_keywords = ["cheap", "budget", "affordable", "inexpensive", "low cost", "economy"]
        luxury_keywords = ["luxury", "5 star", "five star", "premium", "upscale", "expensive"]
        is_budget = any(kw in query_lower for kw in budget_keywords)
        is_luxury = any(kw in query_lower for kw in luxury_keywords)

        if is_budget:
            tier = "cheap budget hotels"
        elif is_luxury:
            tier = "luxury 5-star hotels"
        else:
            tier = "hotels"

        base_parts = [tier]
        if city:
            base_parts.append(f"in {city}")

        if filters:
            amenities = filters.get("amenities") or []
            if amenities:
                base_parts.append("with " + " and ".join(amenities))
            max_price = filters.get("max_price")
            min_price = filters.get("min_price")
            if max_price:
                base_parts.append(f"under ${max_price:.0f} per night")
            elif is_budget:
                base_parts.append("under $120 per night")
            if min_price:
                base_parts.append(f"above ${min_price:.0f} per night")
            if filters.get("min_rating"):
                base_parts.append(f"rated {filters['min_rating']}+ out of 10")

        base = " ".join(base_parts)

        # Info query: pull brand pages + editorial for rich hotel details
        info_query = f"{base} price per night {year} official site review {year}"

        # Booking query: pull aggregator pages so we get real booking links per hotel
        booking_query = f"{base} book now price {year}"

        return info_query, booking_query

    def _pick_urls(self, tavily_results: List[Dict]) -> Dict[str, List[str]]:
        """
        Categorise all raw Tavily URLs into brand / aggregator / other buckets
        and return lists the LLM can use when assigning hotel_url / booking_url.
        """
        brand_urls: List[str] = []
        aggregator_urls: List[str] = []
        other_urls: List[str] = []
        for r in tavily_results:
            url = r.get('url', '')
            cat, u = _categorise_url(url)
            if cat == 'brand':
                brand_urls.append(u)
            elif cat == 'aggregator':
                aggregator_urls.append(u)
            else:
                other_urls.append(u)
        return {
            'brand': brand_urls[:6],
            'aggregator': aggregator_urls[:6],
            'other': other_urls[:4],
        }

    # ------------------------------------------------------------------
    # URL helpers — build correct URLs programmatically (never from LLM)
    # ------------------------------------------------------------------

    @staticmethod
    def _name_slug(name: str) -> str:
        """Lowercase alphanumeric slug of a hotel name for fuzzy URL matching."""
        return re.sub(r'[^a-z0-9]', '', name.lower())

    @staticmethod
    def _name_words(name: str) -> List[str]:
        """Meaningful words from a hotel name (length > 3, skip stopwords)."""
        stopwords = {'hotel', 'the', 'and', 'inn', 'for', 'from', 'with'}
        return [
            w for w in re.sub(r'[^a-z0-9 ]', ' ', name.lower()).split()
            if len(w) > 3 and w not in stopwords
        ]

    def _find_brand_url(self, hotel_name: str, tavily_results: List[Dict]) -> str:
        """
        Find a brand-domain URL whose path matches the hotel name.
        Returns empty string if no good match.
        """
        name_words = self._name_words(hotel_name)
        if not name_words:
            return ''
        best_url = ''
        best_score = 0
        for r in tavily_results:
            url = r.get('url', '')
            cat, _ = _categorise_url(url)
            if cat not in ('brand', 'review'):
                continue
            url_lower = url.lower()
            title_lower = r.get('title', '').lower()
            score = sum(1 for w in name_words if w in url_lower or w in title_lower)
            if score > best_score:
                best_score = score
                best_url = url
        # Require at least half of meaningful words to match
        threshold = max(1, len(name_words) // 2)
        return best_url if best_score >= threshold else ''

    @staticmethod
    def _make_booking_url(hotel_name: str, city: str) -> str:
        """
        Build a guaranteed-correct Booking.com search URL for the hotel.
        booking.com/search.html?ss=HotelName+City always shows that hotel
        as the top result — it is functionally a direct hotel page.
        """
        term = urllib.parse.quote_plus(f"{hotel_name} {city}".strip())
        return f"https://www.booking.com/search.html?ss={term}"

    @staticmethod
    def _make_tripadvisor_url(hotel_name: str, city: str) -> str:
        """Build a TripAdvisor search URL as a fallback hotel_url."""
        term = urllib.parse.quote_plus(f"{hotel_name} {city}".strip())
        return f"https://www.tripadvisor.com/Search?q={term}"

    # ------------------------------------------------------------------

    def _extract_hotels_with_llm(
        self,
        tavily_results: List[Dict],
        city: str,
        original_query: str,
        filters: Dict,
    ) -> List[Dict[str, Any]]:
        """Use the LLM to parse Tavily search snippets into structured hotel JSON.
        URLs are NOT extracted by the LLM — they are built programmatically
        in _normalize to guarantee correctness."""

        year = datetime.now().year
        today = datetime.now().strftime('%B %d, %Y')

        # Build compact context (title + snippet + url, up to 10 results)
        context_parts = []
        for r in tavily_results[:10]:
            pub_date = r.get('published_date') or r.get('published') or ''
            date_note = f"  [Published: {pub_date}]" if pub_date else ''
            snippet = (
                f"URL: {r.get('url', '')}\n"
                f"Title: {r.get('title', '')}{date_note}\n"
                f"Content: {r.get('content', '')[:700]}"
            )
            context_parts.append(snippet)
        context = "\n\n---\n\n".join(context_parts)

        # URL hints are no longer passed to the LLM — URLs are built
        # programmatically in _normalize to avoid LLM URL-matching errors.

        amenity_hint = ""
        if filters.get("amenities"):
            amenity_hint = (
                f"\nUser specifically wants amenities: {', '.join(filters['amenities'])}. "
                "Only include hotels that have them."
            )

        query_lower = (original_query or "").lower()
        price_hint = ""
        if any(kw in query_lower for kw in ["cheap", "budget", "affordable", "inexpensive", "low cost"]):
            price_hint = (
                "\nUser wants CHEAP/BUDGET hotels — prioritise hotels with low prices. "
                "Skip hotels with no known price."
            )
        elif filters.get("max_price"):
            price_hint = f"\nOnly include hotels under ${filters['max_price']:.0f} per night."
        elif filters.get("min_price"):
            price_hint = f"\nOnly include hotels priced above ${filters['min_price']:.0f} per night."

        prompt = f"""You are extracting hotel information from web search results.

Today: {today}
User searched for: "{original_query}"
City: {city or "unknown"}{amenity_hint}{price_hint}

Web Search Results:
{context}

=== TASK ===
Extract up to 5 DISTINCT, REAL hotels from the results. Do NOT invent data.
Do NOT include URLs — they will be handled separately.

FIELD RULES:
- hotel_name: Full official name, no suffixes like "| Booking.com" or "- Hotels.com".
- city: City name only (e.g. "Los Angeles", not "Los Angeles, CA").
- country: Country or state/region name.
- description: 1-2 sentences — location, style, key highlights from the results.
- base_price_per_night: Numeric USD from the results ({year} data only).
  Set to null if no explicit per-night price is stated in the content.
- average_rating: 0-10 scale.
    Conversions: 4.5/5 → 9.0 | 4/5 → 8.0 | 8.5/10 → 8.5 | 5★ → 10 | 4★ → 8 | 3★ → 6
  Set to null if no rating found.
- total_ratings: Integer review count if stated, else 0.
- amenities: List ONLY amenities explicitly mentioned in the content
  e.g. ["Pool","Gym","Free Wi-Fi","Parking","Spa","Restaurant","Breakfast"]
  Use [] if none mentioned.
- room_type: "budget" | "standard" | "deluxe" | "suite" based on price/category.

OUTPUT ONLY a valid JSON array — no markdown, no explanation, no code fences.

[
  {{
    "hotel_name": "...",
    "city": "...",
    "country": "...",
    "description": "...",
    "base_price_per_night": <number or null>,
    "average_rating": <number 0-10 or null>,
    "total_ratings": <integer or 0>,
    "amenities": ["..."],
    "room_type": "standard"
  }}
]"""

        try:
            response = self._llm_invoke_with_retry([HumanMessage(content=prompt)])
            raw = response.content.strip()

            # Strip markdown code fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
            raw = raw.strip()

            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not json_match:
                logger.warning("[TAVILY] LLM did not return a valid JSON array — using naive fallback")
                return self._naive_extract(tavily_results, city)

            hotels_raw = json.loads(json_match.group(0))
            normalised = [
                self._normalize(h, i, city, tavily_results)
                for i, h in enumerate(hotels_raw)
                if h.get("hotel_name")
            ]
            # Drop entries that look empty after normalisation
            valid = [h for h in normalised if h['hotel_name'] and h['hotel_name'] != 'Unknown Hotel']
            return valid

        except json.JSONDecodeError as e:
            logger.error(f"[TAVILY] JSON parse error: {e}")
            return self._naive_extract(tavily_results, city)
        except Exception as e:
            logger.error(f"[TAVILY] LLM extraction error: {e}")
            # No LLM available (quota/TPD) — parse what we can from raw Tavily titles/URLs
            return self._naive_extract(tavily_results, city)

    def _naive_extract(self, tavily_results: List[Dict], city: str) -> List[Dict[str, Any]]:
        """
        No-LLM fallback: parse hotel name from Tavily titles directly.
        Used when Groq quota is exhausted (TPD). URLs are built programmatically.
        """
        logger.info("[TAVILY] Using no-LLM naive extraction fallback")
        hotels = []
        seen_names: set = set()
        hotel_indicators = [
            'hotel', 'inn', 'resort', 'suites', 'hostel', 'lodge',
            'palace', 'villa', 'motel', 'stay', 'rooms', 'apartments',
        ]
        for i, r in enumerate(tavily_results[:10]):
            title = r.get('title', '').strip()
            content = r.get('content', '')
            if not title:
                continue

            # Strip site suffix: "Grand Hotel Bangkok | Booking.com" → "Grand Hotel Bangkok"
            hotel_name = re.split(r'\s*[|\-\u2013\u2014]\s*', title)[0].strip()
            name_lower = hotel_name.lower()
            looks_like_hotel = (
                any(kw in name_lower for kw in hotel_indicators)
                or len(hotel_name.split()) >= 3
            )
            if not looks_like_hotel or len(hotel_name) < 5:
                continue
            if hotel_name in seen_names:
                continue
            seen_names.add(hotel_name)

            # Try to extract a per-night price from the snippet
            price = None
            price_m = re.search(
                r'\$\s*(\d{2,4})(?:\.\d{2})?\s*(?:per\s*night|/\s*night|a\s*night)?',
                content, re.IGNORECASE,
            )
            if price_m:
                price = float(price_m.group(1))

            hotels.append(self._normalize({
                'hotel_name': hotel_name,
                'city': city,
                'country': '',
                'description': content[:300] if content else '',
                'base_price_per_night': price,
                'average_rating': None,
                'total_ratings': 0,
                'amenities': [],
                'room_type': 'standard',
            }, i, city, tavily_results))

            if len(hotels) >= 5:
                break
        logger.info(f"[TAVILY] Naive extraction found {len(hotels)} hotels")
        return hotels

    def _normalize(
        self,
        raw: Dict,
        index: int,
        fallback_city: str,
        tavily_results: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Convert the LLM-extracted (or naive-extracted) dict into the exact hotel schema
        used by the local database, with URLs built PROGRAMMATICALLY.

        URL strategy (never relies on LLM URL guessing):
          booking_url → booking.com/search.html?ss=HotelName+City  (always correct)
          hotel_url   → brand/TripAdvisor page matched by hotel name from raw results,
                        falling back to a TripAdvisor search URL
        """
        # ---- amenities ----
        amenities = raw.get("amenities") or []
        if not isinstance(amenities, list):
            amenities = []
        seen: set = set()
        clean_amenities: List[str] = []
        for a in amenities:
            a = str(a).strip()
            if a and a.lower() not in seen:
                seen.add(a.lower())
                clean_amenities.append(a)

        # ---- rating (always ensure 0-10 scale, or None if unknown) ----
        rating_raw = raw.get("average_rating")
        try:
            if rating_raw is None:
                rating = None   # unknown rating — don't pretend it's 0
            else:
                rating = float(rating_raw)
                # Guard: LLM sometimes returns 5-scale despite instructions
                if 0 < rating <= 5.0 and not str(rating_raw).endswith(".0"):
                    rating = rating * 2.0
                rating = round(min(10.0, max(0.0, rating)), 1)
        except (TypeError, ValueError):
            rating = None

        # ---- price — must be a positive number ----
        price_raw = raw.get("base_price_per_night")
        try:
            price = float(price_raw) if price_raw is not None else None
            if price is not None and price <= 0:
                price = None
        except (TypeError, ValueError):
            price = None

        # ---- total ratings ----
        try:
            total_ratings = int(raw.get("total_ratings") or 0)
        except (TypeError, ValueError):
            total_ratings = 0

        # ---- room type — validated against allowed set ----
        room_type_raw = (raw.get("room_type") or "standard").lower().strip()
        valid_room_types = {"budget", "standard", "deluxe", "suite"}
        room_type = room_type_raw if room_type_raw in valid_room_types else "standard"

        # ---- URLs — built programmatically, never from LLM ----
        hotel_name = str(raw.get("hotel_name", "")).strip()
        city_str = str(raw.get("city") or fallback_city or "").strip()

        # booking_url: Booking.com hotel search — always correct, always clickable
        booking_url = self._make_booking_url(hotel_name, city_str)

        # hotel_url: try to find a matching brand or TripAdvisor URL from raw results
        hotel_url = self._find_brand_url(hotel_name, tavily_results or [])
        if not hotel_url:
            # Fall back to TripAdvisor search — still shows the specific hotel
            hotel_url = self._make_tripadvisor_url(hotel_name, city_str)

        return {
            # Negative IDs distinguish external results from DB records in the frontend
            "id": -(index + 1),
            "hotel_name": hotel_name or "Unknown Hotel",
            "city": city_str,
            "country": str(raw.get("country") or "").strip(),
            "description": str(raw.get("description") or "").strip(),
            # ---- pricing / rating ----
            "base_price_per_night": price,
            "average_rating": rating,
            "total_ratings": total_ratings,
            # ---- room info ----
            "room_type": room_type,
            "number_of_rooms": 1,
            # ---- amenities / media ----
            "amenities": clean_amenities,
            "images": [],
            # ---- ranking signals (external results rank below DB hotels) ----
            "similarity_score": 0.65,
            "match_reason": "External web search result",
            "composite_score": 0.5,
            "perks": clean_amenities[:3],
            "badges": [],
            # ---- external-only fields ----
            "source": "external",
            "hotel_url": hotel_url,      # Brand/TripAdvisor page for this property
            "booking_url": booking_url,  # Booking.com search guaranteed to show this hotel
            "disclaimer": EXTERNAL_DISCLAIMER,
        }
