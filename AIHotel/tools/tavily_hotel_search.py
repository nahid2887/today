"""
Tavily-powered external hotel search fallback.

Used ONLY when the local DB has no results for a location (unknown city, etc.).
Results are returned in the same JSON schema as DB hotels, but flagged with:
  source = "external"
  booking_url = <direct booking link>
  disclaimer = <user-facing warning>
"""

import json
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

EXTERNAL_DISCLAIMER = (
    "⚠️ External result — not in our partner network. "
    "We cannot guarantee availability or pricing. "
    "Book directly via the provided link."
)


class TavilyHotelSearch:
    """
    Searches for hotels via Tavily web search and parses results into
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
            max_tokens=2048
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
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for hotels using Tavily and return up to max_results hotel dicts.

        Args:
            query: Original user query
            city: Extracted city name (if any)
            filters: Dict with optional keys: amenities, min_rating, max_price, min_price
            max_results: Maximum number of hotels to return

        Returns:
            List of hotel dicts in the same schema as DB hotels, with added
            source/booking_url/disclaimer fields.
        """
        if not self.available:
            return []

        search_query = self._build_search_query(query, city, filters)
        logger.info(f"[TAVILY] Searching: '{search_query}'")

        try:
            response = self.client.search(
                query=search_query,
                max_results=10,
                search_depth="advanced",
                days=180,          # Restrict to last 6 months for real-time relevance
                include_domains=[
                    "booking.com", "hotels.com", "expedia.com",
                    "tripadvisor.com", "agoda.com", "marriott.com",
                    "hilton.com", "hyatt.com"
                ]
            )
            results = response.get("results", [])
            logger.info(f"[TAVILY] Got {len(results)} raw results")

            if not results:
                return []

            hotels = self._extract_hotels_with_llm(results, city or "", query, filters or {})
            logger.info(f"[TAVILY] Extracted {len(hotels)} structured hotels")
            return hotels[:max_results]

        except Exception as e:
            logger.error(f"[TAVILY] Search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_search_query(
        self,
        query: str,
        city: Optional[str],
        filters: Optional[Dict]
    ) -> str:
        """Build a focused search string for Tavily."""
        query_lower = (query or "").lower()

        # Detect price preference from natural language
        budget_keywords = ["cheap", "budget", "affordable", "inexpensive", "low cost", "economy"]
        luxury_keywords = ["luxury", "5 star", "five star", "premium", "upscale", "expensive"]
        is_budget = any(kw in query_lower for kw in budget_keywords)
        is_luxury = any(kw in query_lower for kw in luxury_keywords)

        if is_budget:
            parts = ["cheap budget affordable hotels"]
        elif is_luxury:
            parts = ["luxury 5-star hotels"]
        else:
            parts = ["best hotels"]

        if city:
            parts.append(f"in {city}")

        if filters:
            amenities = filters.get("amenities") or []
            if amenities:
                parts.append("with " + " and ".join(amenities))
            if filters.get("max_price"):
                parts.append(f"under ${filters['max_price']:.0f} per night")
            elif is_budget:
                parts.append("under $150 per night")
            if filters.get("min_rating"):
                parts.append(f"rated above {filters['min_rating']}/10")
            if filters.get("min_price"):
                parts.append(f"above ${filters['min_price']:.0f} per night")

        parts.append(f"booking price rating reviews {datetime.now().year}")
        return " ".join(parts)

    def _extract_hotels_with_llm(
        self,
        tavily_results: List[Dict],
        city: str,
        original_query: str,
        filters: Dict
    ) -> List[Dict[str, Any]]:
        """Use Groq LLM to parse Tavily search snippets into structured hotel JSON."""

        # Build compact context (avoid token overflow)
        context_parts = []
        for r in tavily_results[:8]:
            pub_date = r.get('published_date') or r.get('published') or ''
            date_note = f"\nPublished: {pub_date}" if pub_date else ''
            snippet = (
                f"URL: {r.get('url', '')}\n"
                f"Title: {r.get('title', '')}{date_note}\n"
                f"Excerpt: {r.get('content', '')[:600]}"
            )
            context_parts.append(snippet)
        context = "\n\n---\n\n".join(context_parts)

        amenity_hint = ""
        if filters.get("amenities"):
            amenity_hint = f"\nUser specifically wants: {', '.join(filters['amenities'])}"

        query_lower = (original_query or "").lower()
        budget_keywords = ["cheap", "budget", "affordable", "inexpensive", "low cost"]
        price_hint = ""
        if any(kw in query_lower for kw in budget_keywords):
            price_hint = "\nUser wants CHEAP/BUDGET hotels — prioritise results with low prices. Only extract hotels that have a known price."
        elif filters.get("max_price"):
            price_hint = f"\nOnly include hotels that cost under ${filters['max_price']:.0f} per night."

        prompt = f"""Extract hotel information from the web search results below.
Today's date: {datetime.now().strftime('%B %d, %Y')}
User searched for: "{original_query}"
City: {city or "unknown"}{amenity_hint}{price_hint}

Web Search Results:
{context}

Instructions:
- Extract up to 5 distinct, real hotels mentioned or clearly implied in the results.
- These results are from {datetime.now().year} — use the pricing and ratings as current data.
- For average_rating always use a 10-point scale (convert 4.5/5 stars → 9.0, 8/10 → 8.0).
- For booking_url pick the most direct booking link from the results URL (booking.com, hotels.com, expedia preferred).
- amenities: list common ones found in the text e.g. ["Pool","Gym","Spa","Restaurant","Wi-Fi","Free Parking"].
- If a field cannot be determined use: null for numbers, [] for arrays, "" for strings.
- Do NOT invent hotels not mentioned in the search results.
- Output ONLY a valid JSON array, no explanations.

JSON array format:
[
  {{
    "hotel_name": "...",
    "city": "...",
    "country": "...",
    "description": "1-2 sentences",
    "base_price_per_night": <number or null>,
    "average_rating": <number 0-10 or null>,
    "total_ratings": <number or 0>,
    "amenities": [...],
    "room_type": "standard|deluxe|suite",
    "booking_url": "..."
  }}
]"""

        try:
            response = self._llm_invoke_with_retry([HumanMessage(content=prompt)])
            raw = response.content.strip()

            # Extract JSON array (handle markdown code fences)
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not json_match:
                logger.warning("[TAVILY] LLM did not return a valid JSON array")
                return self._naive_extract(tavily_results, city)

            hotels_raw = json.loads(json_match.group(0))
            return [self._normalize(h, i, city) for i, h in enumerate(hotels_raw) if h.get("hotel_name")]

        except json.JSONDecodeError as e:
            logger.error(f"[TAVILY] JSON parse error: {e}")
            return self._naive_extract(tavily_results, city)
        except Exception as e:
            logger.error(f"[TAVILY] LLM extraction error: {e}")
            # No LLM available (quota/TPD) — parse what we can from raw Tavily titles/URLs
            return self._naive_extract(tavily_results, city)

    def _naive_extract(self, tavily_results: List[Dict], city: str) -> List[Dict[str, Any]]:
        """
        No-LLM fallback: parse hotel name + URL directly from raw Tavily titles.
        Used when Groq quota is exhausted (TPD). Less structured but still useful.
        """
        logger.info("[TAVILY] Using no-LLM naive extraction fallback")
        hotels = []
        seen_names: set = set()
        for i, r in enumerate(tavily_results[:8]):
            title = r.get('title', '').strip()
            url = r.get('url', '')
            content = r.get('content', '')
            if not title:
                continue
            # Strip site suffix: "Grand Hotel Bangkok | Booking.com" → "Grand Hotel Bangkok"
            hotel_name = re.split(r'\s*[|\-\u2013\u2014]\s*', title)[0].strip()
            # Must look like a hotel name (contains hotel/inn/resort/suites or has enough length)
            hotel_indicators = ['hotel', 'inn', 'resort', 'suites', 'hostel', 'lodge',
                                'palace', 'villa', 'motel', 'stay', 'rooms']
            name_lower = hotel_name.lower()
            looks_like_hotel = (any(kw in name_lower for kw in hotel_indicators)
                                or len(hotel_name.split()) >= 3)
            if not looks_like_hotel or len(hotel_name) < 4:
                continue
            if hotel_name in seen_names:
                continue
            seen_names.add(hotel_name)
            hotels.append(self._normalize({
                'hotel_name': hotel_name,
                'city': city,
                'country': '',
                'description': content[:250] if content else '',
                'base_price_per_night': None,
                'average_rating': None,
                'total_ratings': 0,
                'amenities': [],
                'room_type': 'standard',
                'booking_url': url,
            }, i, city))
            if len(hotels) >= 5:
                break
        logger.info(f"[TAVILY] Naive extraction found {len(hotels)} hotels")
        return hotels

    def _normalize(self, raw: Dict, index: int, fallback_city: str) -> Dict[str, Any]:
        """Convert LLM-extracted dict into the standard hotel schema."""
        amenities = raw.get("amenities") or []
        if not isinstance(amenities, list):
            amenities = []

        rating_raw = raw.get("average_rating")
        try:
            rating = float(rating_raw) if rating_raw is not None else 0.0
            # Guard: some LLMs return 5-scale even after instruction
            if rating > 0 and rating <= 5.0 and not str(rating_raw).endswith(".0"):
                rating = rating * 2  # convert 4.5 scale → 9.0
            rating = min(10.0, max(0.0, rating))
        except (TypeError, ValueError):
            rating = 0.0

        price_raw = raw.get("base_price_per_night")
        try:
            price = float(price_raw) if price_raw is not None else None
        except (TypeError, ValueError):
            price = None

        total_ratings_raw = raw.get("total_ratings")
        try:
            total_ratings = int(total_ratings_raw) if total_ratings_raw else 0
        except (TypeError, ValueError):
            total_ratings = 0

        return {
            # Use negative IDs so frontend can distinguish external from DB hotels
            "id": -(index + 1),
            "hotel_name": str(raw.get("hotel_name", "Unknown Hotel")).strip(),
            "city": str(raw.get("city") or fallback_city or "").strip(),
            "country": str(raw.get("country") or "").strip(),
            "description": str(raw.get("description") or "").strip(),
            "base_price_per_night": price,
            "amenities": amenities,
            "images": [],
            "average_rating": rating,
            "total_ratings": total_ratings,
            "room_type": raw.get("room_type") or "standard",
            "number_of_rooms": 1,
            # Ranking fields — external hotels rank below DB hotels by default
            "similarity_score": 0.65,
            "match_reason": "External web search result",
            "composite_score": 0.5,
            "perks": amenities[:3],
            "badges": [],
            # External-only fields
            "source": "external",
            "booking_url": str(raw.get("booking_url") or "").strip(),
            "disclaimer": EXTERNAL_DISCLAIMER,
        }
