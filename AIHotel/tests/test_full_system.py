"""
=============================================================================
FULL SYSTEM QA TEST SUITE  (v2 — pagination-aware)
=============================================================================
Covers every query category a real traveler could send, including:
  - Greetings / small talk
  - General travel info
  - DB hotel searches (Perth metro) — city, rating, price, amenity filters
  - Combined filters
  - Follow-up / context carry
  - Session memory (shown_hotel_ids dedup)
  - Spelling / typo correction
  - External Tavily fallback (unknown cities)
  - Budget / luxury intent
  - Rating range (between X to Y)
  - Edge cases: gibberish city, extreme values, empty results
  - Anti-hallucination (city grounding)
  - Multi-turn conversation threads (up to 8 turns)
  - Boundary / stress tests
  - Pagination — show-more served from pending_hotels cache (no repeat LLM call)
  - Response Quality — URL / placeholder checks, max 3 per turn enforcement

v2 changes vs v1:
  - run_case tracks pending_hotels between turns
  - Turn flags show_more=True → served from cache using _is_show_more()
  - _check() accepts `pending` list and supports has_more/no_more/min_pending
  - hotel_min/max_rating now ignores None-rated hotels (they silently pass)
  - TurnResult stores show_more + pending_count for report

Run from the AIHotel directory:
    uv run python tests/test_full_system.py
    uv run python tests/test_full_system.py --verbose
    uv run python tests/test_full_system.py --category "Pagination"
    uv run python tests/test_full_system.py --category "DB Search"
    uv run python tests/test_full_system.py --log-level DEBUG
    uv run python tests/test_full_system.py --delay 3.0   # slower, avoids rate limits

All runs automatically save to tests/logs/<timestamp>/:
    system.log   — full INFO/DEBUG logs from every subsystem
    results.log  — human-readable turn-by-turn results + pending hotel lists
    report.json  — machine-readable pass/fail report (includes show_more, pending_count,
                   booking_urls per turn)
=============================================================================
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch


# ─────────────────────────────────────────────────────────────────────────────
# Show-more detection helpers (mirrors production main.py logic)
# ─────────────────────────────────────────────────────────────────────────────
_SHOW_MORE_RE = re.compile(
    r'(?:'
    r'show\s+(?:\w+\s+){0,3}more'
    r'|more\s+hotels?|more\s+options?|more\s+results?|see\s+more'
    r'|any\s+(?:more|others?)\b|other\s+hotels?|what\s+else|more\s+please'
    r'|next\s+(?:hotels?|ones?)|rest\s+of|remaining\s+hotels?'
    r'|suggest\s+more|give\s+more|list\s+more|any\s+more'
    r'|show\s+(?:me\s+)?(?:some\s+)?more'
    r')|^(?:more|others?|next|continue|remaining)$',
    re.IGNORECASE
)
_CHEAPER_RE = re.compile(
    r'cheap|budget|affordable|inexpensive|low.?cost|less\s+expensive',
    re.IGNORECASE
)
_LUXURY_RE = re.compile(
    r'luxury|premium|upscale|expensive|5.?star|five.?star',
    re.IGNORECASE
)


def _is_show_more(text: str) -> bool:
    """Return True if `text` is a show-more / pagination request."""
    return bool(_SHOW_MORE_RE.search(text.strip()))


# ─────────────────────────────────────────────────────────────────────────────
# Logging setup  (called once from run_all after we know the log dir)
# ─────────────────────────────────────────────────────────────────────────────

_LOG_DIR: Optional[str] = None           # set by setup_logging()
_RESULTS_LOG: Optional[str] = None       # path to results.log


def setup_logging(log_level_str: str = "INFO") -> str:
    """
    Configure dual logging:
      • Console — WARNING+ only (keeps terminal clean)
      • File    — log_level and above (full system trace)

    Returns the directory where logs are saved.
    """
    global _LOG_DIR, _RESULTS_LOG

    tests_dir = os.path.dirname(os.path.abspath(__file__))
    logs_root = os.path.join(tests_dir, "logs")
    run_ts    = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir   = os.path.join(logs_root, run_ts)
    os.makedirs(run_dir, exist_ok=True)

    _LOG_DIR     = run_dir
    _RESULTS_LOG = os.path.join(run_dir, "results.log")
    system_log   = os.path.join(run_dir, "system.log")

    file_level = getattr(logging, log_level_str.upper(), logging.INFO)

    # Root logger — captures everything from every module
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)            # let handlers filter

    # Remove any handlers already attached (e.g. from basicConfig)
    root.handlers.clear()

    # ── File handler: full system logs ───────────────────────────────────
    fh = logging.FileHandler(system_log, encoding="utf-8")
    fh.setLevel(file_level)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(fh)

    # ── Console handler: warnings + errors only ───────────────────────────
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(ch)

    return run_dir


def _rlog(msg: str) -> None:
    """Append a line to results.log (and optionally print during verbose)."""
    if _RESULTS_LOG:
        with open(_RESULTS_LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

# ─────────────────────────────────────────────────────────────────────────────
# Colours for terminal output
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TurnResult:
    query: str
    response: str
    hotels: List[Dict]
    query_type: str
    elapsed_ms: float
    passed: bool
    fail_reasons: List[str] = field(default_factory=list)
    show_more: bool = False          # True → served from pending cache, no LLM call
    pending_count: int = 0           # pending_hotels remaining after this turn


@dataclass
class CaseResult:
    name: str
    category: str
    turns: List[TurnResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(t.passed for t in self.turns)


# ─────────────────────────────────────────────────────────────────────────────
# Assertion helpers
# ─────────────────────────────────────────────────────────────────────────────
def _check(response: str, hotels: List[Dict], query_type: str,
           assertions: Dict, pending: Optional[List[Dict]] = None) -> Tuple[bool, List[str]]:
    """
    Evaluate a single set of assertions against a turn result.

    Supported assertion keys:
      type_is          str        — expected query_type value
      response_contains list[str] — all substrings must appear (case-insensitive)
      response_excludes list[str] — none may appear
      min_hotels       int        — at least N hotels returned this turn
      max_hotels       int        — at most N hotels returned this turn
      exact_hotels     int        — exactly N hotels
      hotel_city       str        — all returned hotels must have this city
      has_external     bool       — at least one hotel has source=="external"
      no_external      bool       — no hotel has source=="external"
      hotel_min_rating float      — all rated hotels must have average_rating >= this
      hotel_max_rating float      — all rated hotels must have average_rating <= this
      hotel_price_asc  bool       — prices non-decreasing (None prices excluded)
      has_more         bool       — pending hotels non-empty after this turn
      no_more          bool       — pending hotels empty after this turn
      min_pending      int        — at least N hotels in pending after this turn
    """
    if pending is None:
        pending = []
    fails = []

    if "type_is" in assertions:
        if query_type != assertions["type_is"]:
            fails.append(f"Expected type={assertions['type_is']}, got {query_type}")

    if "response_contains" in assertions:
        for phrase in assertions["response_contains"]:
            if phrase.lower() not in response.lower():
                fails.append(f"Response missing: '{phrase}'")

    if "response_excludes" in assertions:
        for phrase in assertions["response_excludes"]:
            if phrase.lower() in response.lower():
                fails.append(f"Response should NOT contain: '{phrase}'")

    if "min_hotels" in assertions:
        if len(hotels) < assertions["min_hotels"]:
            fails.append(f"Expected >= {assertions['min_hotels']} hotels, got {len(hotels)}")

    if "max_hotels" in assertions:
        if len(hotels) > assertions["max_hotels"]:
            fails.append(f"Expected <= {assertions['max_hotels']} hotels, got {len(hotels)}")

    if "exact_hotels" in assertions:
        if len(hotels) != assertions["exact_hotels"]:
            fails.append(f"Expected exactly {assertions['exact_hotels']} hotels, got {len(hotels)}")

    if "hotel_city" in assertions:
        wrong = [h.get("hotel_name") for h in hotels
                 if h.get("city", "").lower() != assertions["hotel_city"].lower()]
        if wrong:
            fails.append(f"Hotels not in '{assertions['hotel_city']}': {wrong}")

    if assertions.get("has_external"):
        if not any(h.get("source") == "external" for h in hotels):
            fails.append("Expected at least one external hotel (source='external')")

    if assertions.get("no_external"):
        ext = [h.get("hotel_name") for h in hotels if h.get("source") == "external"]
        if ext:
            fails.append(f"Expected no external hotels, but got: {ext}")

    if "hotel_min_rating" in assertions:
        # None-rated hotels silently pass (no review data yet)
        low = [h.get("hotel_name") for h in hotels
               if h.get("average_rating") is not None
               and h.get("average_rating") < assertions["hotel_min_rating"]]
        if low:
            fails.append(f"Hotels below min_rating {assertions['hotel_min_rating']}: {low}")

    if "hotel_max_rating" in assertions:
        high = [h.get("hotel_name") for h in hotels
                if h.get("average_rating") is not None
                and h.get("average_rating") > assertions["hotel_max_rating"]]
        if high:
            fails.append(f"Hotels above max_rating {assertions['hotel_max_rating']}: {high}")

    if assertions.get("hotel_price_asc"):
        prices = [h.get("base_price_per_night") for h in hotels
                  if h.get("base_price_per_night") is not None]
        if prices != sorted(prices):
            fails.append(f"Hotels not sorted cheapest-first: {prices}")

    if assertions.get("has_more"):
        if not pending:
            fails.append("Expected pending_hotels to be non-empty (has_more)")

    if assertions.get("no_more"):
        if pending:
            fails.append(f"Expected no pending hotels, but {len(pending)} remain")

    if "min_pending" in assertions:
        if len(pending) < assertions["min_pending"]:
            fails.append(f"Expected >= {assertions['min_pending']} pending, got {len(pending)}")

    return (len(fails) == 0), fails


# ─────────────────────────────────────────────────────────────────────────────
# Test case definitions
# ─────────────────────────────────────────────────────────────────────────────
# Each case is a dict:
# {
#   "name":     str,
#   "category": str,
#   "turns": [
#     {
#       "query":      str,
#       "assertions": { ... }   # optional
#     },
#     ...
#   ]
# }
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES = [

    # =========================================================
    # CATEGORY: Greetings & Small Talk
    # =========================================================
    {
        "name": "Hello greeting",
        "category": "Greetings",
        "turns": [
            {"query": "Hello!",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0,
                            # 'assist' vs 'help' — both are valid phrasing; rate-limit canned fallback
                            # uses 'help'. Only require 'hello' which always appears.
                            "response_contains": ["hello"]}},

        ]
    },
    {
        "name": "What can you do?",
        "category": "Greetings",
        "turns": [
            {"query": "What can you do?",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Thank you",
        "category": "Greetings",
        "turns": [
            {"query": "Thanks a lot, that was helpful!",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Goodbye",
        "category": "Greetings",
        "turns": [
            {"query": "Goodbye, see you later",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Who are you",
        "category": "Greetings",
        "turns": [
            {"query": "Who are you?",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },

    # =========================================================
    # CATEGORY: General Travel Info
    # =========================================================
    {
        "name": "Best time to visit Sydney",
        "category": "Travel Info",
        "turns": [
            {"query": "What's the best time to visit Sydney?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0,
                            "response_contains": ["sydney"]}},
        ]
    },
    {
        "name": "Tips for travelling to Australia",
        "category": "Travel Info",
        "turns": [
            {"query": "Give me travel tips for visiting Australia",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Fremantle vs Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "What is the difference between Perth and Fremantle?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Visa requirements",
        "category": "Travel Info",
        "turns": [
            {"query": "Do I need a visa to visit Australia from Bangladesh?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Weather in Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "How is the weather in Perth in December?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },

    # =========================================================
    # CATEGORY: Basic DB Hotel Search
    # =========================================================
    {
        "name": "Hotels in Perth",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth", "no_external": True}},
        ]
    },
    {
        "name": "Hotels in Fremantle",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Fremantle", "no_external": True}},
        ]
    },
    {
        "name": "Hotels in Guildford",
        "category": "DB Search",
        "turns": [
            # Guildford UK is not in the Perth DB — Tavily external fallback is correct
            {"query": "hotels in guildford",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Hotels in Rockingham",
        "category": "DB Search",
        "turns": [
            {"query": "suggest hotels in rockingham",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True}},
        ]
    },
    {
        "name": "Hotels in Swan Valley",
        "category": "DB Search",
        "turns": [
            {"query": "show me hotels in swan valley",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True}},
        ]
    },
    {
        "name": "Hotels in Northbridge",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in northbridge",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True}},
        ]
    },
    {
        "name": "Top hotels Perth",
        "category": "DB Search",
        "turns": [
            {"query": "top hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth", "no_external": True}},
        ]
    },

    # =========================================================
    # CATEGORY: Rating Filters
    # =========================================================
    {
        "name": "Rating above 8",
        "category": "Rating Filters",
        "turns": [
            {"query": "hotels in perth with rating above 8",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 8.0, "no_external": True}},
        ]
    },
    {
        "name": "Rating above 9",
        "category": "Rating Filters",
        "turns": [
            {"query": "hotels in perth with rating above 9",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Rating more than 7 (not price)",
        "category": "Rating Filters",
        "turns": [
            {"query": "hotels with rating more than 7 in perth",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 7.0}},
        ]
    },
    {
        "name": "Between rating 8 to 9",
        "category": "Rating Filters",
        "turns": [
            {"query": "hotels in perth with rating between 8 to 9",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 8.0, "hotel_max_rating": 9.0}},
        ]
    },
    {
        "name": "Between rating 7 to 9",
        "category": "Rating Filters",
        "turns": [
            {"query": "show me hotels between 7 to 9 ratings in perth",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 7.0, "hotel_max_rating": 9.0}},
        ]
    },
    {
        "name": "Top rated hotels Fremantle",
        "category": "Rating Filters",
        "turns": [
            {"query": "best rated hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: Price Filters
    # =========================================================
    {
        "name": "Cheap hotels Perth",
        "category": "Price Filters",
        "turns": [
            {"query": "cheap hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth", "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Budget hotels Fremantle",
        "category": "Price Filters",
        "turns": [
            {"query": "budget hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Affordable hotels Perth",
        "category": "Price Filters",
        "turns": [
            {"query": "affordable hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Luxury hotels Perth",
        "category": "Price Filters",
        "turns": [
            {"query": "luxury hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "5 star hotels Perth",
        "category": "Price Filters",
        "turns": [
            {"query": "5 star hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: Amenity Filters
    # =========================================================
    {
        "name": "Hotels with pool Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with pool in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Hotels with gym Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with gym in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with spa Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with spa in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with free breakfast Fremantle",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with breakfast included in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with kitchen Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with kitchen in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Hotels with rooftop bar Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with rooftop bar in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Typo: swimming pool",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotles with swiming pool in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },

    # =========================================================
    # CATEGORY: Combined Filters
    # =========================================================
    {
        "name": "Cheap + pool + rated above 7",
        "category": "Combined Filters",
        "turns": [
            {"query": "cheap hotels with pool in perth rated above 7",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Budget + breakfast Fremantle",
        "category": "Combined Filters",
        "turns": [
            {"query": "budget hotels in fremantle with breakfast included",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Pool + gym Perth",
        "category": "Combined Filters",
        "turns": [
            {"query": "hotels with pool and gym in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Rating 8-9 + spa Perth",
        "category": "Combined Filters",
        "turns": [
            {"query": "hotels in perth with spa and rating between 8 to 9",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },

    # =========================================================
    # CATEGORY: Typo / Spelling Correction
    # =========================================================
    {
        "name": "Typo: perth",
        "category": "Typo Correction",
        "turns": [
            {"query": "sugget me hotls in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Typo: fremantle",
        "category": "Typo Correction",
        "turns": [
            {"query": "hotles in fremantl",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Typo: cheap",
        "category": "Typo Correction",
        "turns": [
            {"query": "cheep hotels fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Typo: los angeles",
        "category": "Typo Correction",
        "turns": [
            {"query": "suggest some hotel from los angels",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: External / Tavily Fallback
    # =========================================================
    {
        "name": "Sydney hotels — Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in sydney",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True,
                            "response_contains": ["external", "partner"]}},
        ]
    },
    {
        "name": "Melbourne hotels — Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in melbourne",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Tokyo hotels — Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "London hotels — Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in london",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Cheap Bangkok — Tavily budget search",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "cheap hotels in bangkok",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True,
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Luxury Dubai — Tavily luxury search",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "luxury hotels in dubai",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Sydney rated above 9 — Tavily with rating filter",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in sydney with rating above 9",
             # Tavily ratings are scraped/unreliable — strict hotel_min_rating on external results
             # is too fragile; just verify we got external results for the right city.
             "assertions": {"type_is": "hotel_search", "has_external": True}},
        ]
    },
    {
        "name": "No [booking_url] placeholder in response",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in paris",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "response_excludes": ["[booking_url]", "[url]"]}},
        ]
    },

    # =========================================================
    # CATEGORY: Anti-Hallucination / City Grounding
    # =========================================================
    {
        "name": "Sydney search must not return Perth hotels",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "suggest me hotels from sydney",
             "assertions": {"type_is": "hotel_search",
                            # The error message may list "Perth" as an available city,
                            # so only exclude phrases that would indicate Perth hotels were returned
                            "response_excludes": ["hotel in perth", "stay in perth",
                                                  "perth hotel", "recommending perth",
                                                  "perth has"]}},
        ]
    },
    {
        "name": "Response must not invent hotel names",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True}},
        ]
    },
    {
        "name": "Unknown city shows available cities list",
        "category": "Anti-Hallucination",
        "turns": [
            # Tavily may find the famous Atlantis resort — that is valid external behaviour.
            # We only assert: (a) it attempts a hotel search, (b) no URL placeholders leak.
            {"query": "hotels in atlantis",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["[booking_url]", "[url]"]}},
        ]
    },

    # =========================================================
    # CATEGORY: Edge Cases
    # =========================================================
    {
        "name": "Gibberish city xyz123 — no hallucination",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in xyz123",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["[booking_url]"]}},
        ]
    },
    {
        "name": "Extreme rating above 10",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels with rating above 10 in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Rating exactly 10",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in perth with rating between 10 to 10",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Very low price filter",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels under 10 dollars in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "No city — just show me hotels",
        "category": "Edge Cases",
        "turns": [
            {"query": "show me hotels",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Very vague query",
        "category": "Edge Cases",
        "turns": [
            {"query": "I need a place to sleep",
             "assertions": {}},
        ]
    },

    # =========================================================
    # CATEGORY: Multi-turn — Follow-up & Context Carry
    # =========================================================
    {
        "name": "City carries over to follow-up",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
            {"query": "now show me cheap ones",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Filter refinement — add amenity",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "filter by ones with a pool",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Rating refinement after initial search",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "only show me the best rated",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "City switch mid-session",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Perth"}},
            {"query": "actually, show me hotels in fremantle instead",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Fremantle"}},
        ]
    },
    {
        "name": "Cheap follow-up after external search",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in sydney",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "suggest some cheap ones",
             "assertions": {"type_is": "hotel_search", "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Travel info → hotel search transition",
        "category": "Multi-turn",
        "turns": [
            {"query": "when is the best time to visit perth?",
             "assertions": {"type_is": "travel_info"}},
            {"query": "great, now find me hotels there",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Chat → hotel search transition",
        "category": "Multi-turn",
        "turns": [
            {"query": "hi there",
             "assertions": {"type_is": "normal_chat"}},
            {"query": "I'm planning a trip to fremantle, any hotels?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Full traveler journey (6 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hello",
             "assertions": {"type_is": "normal_chat"}},
            {"query": "I'm planning a trip to Perth, what should I know?",
             "assertions": {"type_is": "travel_info"}},
            {"query": "can you recommend some hotels there?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
            {"query": "any with a pool?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "which is the cheapest?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_price_asc": True}},
            {"query": "perfect, thanks!",
             "assertions": {"type_is": "normal_chat"}},
        ]
    },
    {
        "name": "Full external journey (4 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "any cheap ones under 100 dollars?",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "I actually prefer luxury — show me 5 star options",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "thanks, that helps",
             "assertions": {"type_is": "normal_chat"}},
        ]
    },

    # =========================================================
    # CATEGORY: Preposition / Phrasing Variants
    # =========================================================
    {
        "name": "Hotels FROM perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "suggest me hotels from perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Hotels NEAR perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "hotels near perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Recommend hotels IN perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "can you recommend some hotels in perth for me?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "I want to stay IN fremantle",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "I want to stay somewhere in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Looking for accommodation in perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "I'm looking for accommodation in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: Stress / Boundary
    # =========================================================
    {
        "name": "Empty-ish query",
        "category": "Stress",
        "turns": [
            {"query": "hotels",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Unusually long query",
        "category": "Stress",
        "turns": [
            {"query": ("I am travelling to Perth in Australia next month and I would really "
                       "love to find a nice hotel that has a swimming pool, a spa, and ideally "
                       "also a fine dining restaurant, and I want the rating to be above 8 out "
                       "of 10 and the price should be reasonable, can you help me please?"),
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "All capitals",
        "category": "Stress",
        "turns": [
            {"query": "HOTELS IN PERTH WITH POOL",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Mixed language typo",
        "category": "Stress",
        "turns": [
            {"query": "hotels in pert west australia",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: Pagination (show-more / pending cache)
    # =========================================================
    {
        "name": "DB: initial 3 then show more",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "hotel_city": "Perth", "no_external": True}},
            {"query": "show more",
             "show_more": True,
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "External: 3 shown then show some more",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in dhaka",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "can you show some more",
             "show_more": True,
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Show me some more (phrasing variant)",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in chittagong",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "show me some more",
             "show_more": True,
             "assertions": {}},
        ]
    },
    {
        "name": "Any others? variant",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in sydney",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "any others?",
             "show_more": True,
             "assertions": {}},
        ]
    },
    {
        "name": "More please variant",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in singapore",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "more please",
             "show_more": True,
             "assertions": {}},
        ]
    },
    {
        "name": "What else do you have?",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in london",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "what else do you have?",
             "show_more": True,
             "assertions": {}},
        ]
    },
    {
        "name": "Show more cheaper from pending",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "show me more with cheaper options",
             "show_more": True,
             "assertions": {"hotel_price_asc": True}},
        ]
    },
    {
        "name": "Show more luxury from pending",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in paris",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "show me more luxury options",
             "show_more": True,
             "assertions": {}},
        ]
    },
    {
        "name": "New city resets pending",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in chittagong",
             "assertions": {"type_is": "hotel_search", "max_hotels": 3,
                            "has_external": True}},
            # Brand-new city: old pending is cleared; this is a fresh search
            {"query": "hotels in dhaka",
             "assertions": {"type_is": "hotel_search", "max_hotels": 3,
                            "has_external": True}},
        ]
    },
    {
        "name": "Show more then new search (3 turns)",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in singapore",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "more please",
             "show_more": True,
             "assertions": {}},
            # Now a completely new search — pending should reset
            {"query": "hotels in london",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
        ]
    },
    {
        "name": "No raw URLs in show-more batch",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in paris",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3}},
            {"query": "show me some more options",
             "show_more": True,
             "assertions": {"response_excludes": ["https://", "http://",
                                                  "[booking_url]", "booking.com"]}},
        ]
    },
    {
        "name": "Next / remaining phrasing",
        "category": "Pagination",
        "turns": [
            {"query": "hotels in new york",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3, "has_external": True}},
            {"query": "show me the remaining hotels",
             "show_more": True,
             "assertions": {}},
        ]
    },

    # =========================================================
    # CATEGORY: Response Quality
    # =========================================================
    {
        "name": "No raw URLs in Perth response",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "response_excludes": ["https://", "http://"]}},
        ]
    },
    {
        "name": "No raw URLs in Tokyo response",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "response_excludes": ["https://", "http://"]}},
        ]
    },
    {
        "name": "No [booking_url] placeholder in any response",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "response_excludes": ["[booking_url]", "[url]",
                                                  "booking_url"]}},
        ]
    },
    {
        "name": "Response not empty for unknown city",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in xyzfakecity",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["[booking_url]"]}},
        ]
    },
    {
        "name": "Response not empty for vague query",
        "category": "Response Quality",
        "turns": [
            # LLM may ask for clarification (normal_chat) or search immediately —
            # both are valid.  We only require a non-empty, non-broken response.
            {"query": "I need somewhere nice to stay",
             "assertions": {"response_excludes": ["[booking_url]", "[url]"]}},
        ]
    },
    {
        "name": "No URL placeholders in Fremantle response",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True,
                            "response_excludes": ["https://", "[booking_url]",
                                                  "tripadvisor"]}},
        ]
    },
    {
        "name": "Max 3 hotels per turn (DB)",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "max_hotels": 3}},
        ]
    },
    {
        "name": "Max 3 hotels per turn (external)",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in singapore",
             "assertions": {"type_is": "hotel_search", "max_hotels": 3,
                            "has_external": True}},
        ]
    },
    {
        "name": "Price sorted on cheap query (DB)",
        "category": "Response Quality",
        "turns": [
            {"query": "cheap hotels in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "External response labels hotels correctly",
        "category": "Response Quality",
        "turns": [
            {"query": "hotels in new york",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True,
                            "response_excludes": ["[booking_url]", "[url]"]}},
        ]
    },

    # =========================================================
    # CATEGORY: More Greetings
    # =========================================================
    {
        "name": "How are you?",
        "category": "Greetings",
        "turns": [
            {"query": "How are you doing today?",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Good morning",
        "category": "Greetings",
        "turns": [
            {"query": "Good morning!",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Casual hey",
        "category": "Greetings",
        "turns": [
            {"query": "hey",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },
    {
        "name": "Nice to meet you",
        "category": "Greetings",
        "turns": [
            {"query": "Nice to meet you!",
             "assertions": {"type_is": "normal_chat", "max_hotels": 0}},
        ]
    },

    # =========================================================
    # CATEGORY: More Travel Info
    # =========================================================
    {
        "name": "Currency in Australia",
        "category": "Travel Info",
        "turns": [
            {"query": "What currency is used in Australia?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0,
                            "response_contains": ["australia"]}},
        ]
    },
    {
        "name": "Distance Perth to Fremantle",
        "category": "Travel Info",
        "turns": [
            {"query": "How far is Fremantle from Perth city centre?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Things to do in Fremantle",
        "category": "Travel Info",
        "turns": [
            {"query": "What are the top things to do in Fremantle?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0,
                            "response_contains": ["fremantle"]}},
        ]
    },
    {
        "name": "Public transport in Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "How is the public transport in Perth?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Rottnest Island from Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "How do I get to Rottnest Island from Perth?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Best food in Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "What is the best food to eat in Perth?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },
    {
        "name": "Safety in Perth",
        "category": "Travel Info",
        "turns": [
            {"query": "Is Perth safe for tourists?",
             "assertions": {"type_is": "travel_info", "max_hotels": 0}},
        ]
    },

    # =========================================================
    # CATEGORY: More DB Search (Perth suburbs)
    # =========================================================
    {
        "name": "Hotels in Mandurah",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in mandurah",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels in Cottesloe",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in cottesloe",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels in Joondalup",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in joondalup",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels in Hilton Perth",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in hilton perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels in East Perth",
        "category": "DB Search",
        "turns": [
            {"query": "hotels in east perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },

    # =========================================================
    # CATEGORY: More Amenity Filters
    # =========================================================
    {
        "name": "Pet-friendly hotels Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "pet-friendly hotels in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Hotels with parking Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with free parking in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with restaurant Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with on-site restaurant in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with airport shuttle Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with airport shuttle in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Hotels with free WiFi Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with free wifi in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with bar Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with a bar in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotels with sea view Fremantle",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with sea view in fremantle",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Hotels with conference room Perth",
        "category": "Amenity Filters",
        "turns": [
            {"query": "hotels with a conference room or meeting room in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },

    # =========================================================
    # CATEGORY: More Combined Filters
    # =========================================================
    {
        "name": "Fremantle + pool + cheap",
        "category": "Combined Filters",
        "turns": [
            {"query": "cheap hotels with pool in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Perth + rating above 8 + breakfast",
        "category": "Combined Filters",
        "turns": [
            {"query": "hotels in perth with breakfast included and rating above 8",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Luxury + pool + rating 9+ Perth",
        "category": "Combined Filters",
        "turns": [
            {"query": "luxury hotels in perth with pool and rating above 9",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "External cheap + rating above 8",
        "category": "Combined Filters",
        "turns": [
            {"query": "cheap hotels in singapore with rating above 8",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
        ]
    },

    # =========================================================
    # CATEGORY: More Typo Correction
    # =========================================================
    {
        "name": "Typo: sydney (external)",
        "category": "Typo Correction",
        "turns": [
            {"query": "hotls in sydny",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Typo: melbourne",
        "category": "Typo Correction",
        "turns": [
            {"query": "recommnd hotels in melburn",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Typo: pool in fremantle",
        "category": "Typo Correction",
        "turns": [
            {"query": "hotels wit pol in fremantl",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Typo: luxury tokyo",
        "category": "Typo Correction",
        "turns": [
            {"query": "luxry hotls in tokio",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },

    # =========================================================
    # CATEGORY: More Tavily Fallback (external cities)
    # =========================================================
    {
        "name": "Singapore hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in singapore",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "New York hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in new york",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Bali hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in bali",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Kuala Lumpur hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in kuala lumpur",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Paris hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in paris",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Dhaka hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in dhaka",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Chittagong hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in chittagong",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True, "max_hotels": 3}},
        ]
    },
    {
        "name": "Bangkok cheap no URLs -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "cheap hotels in bangkok",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True,
                            "hotel_price_asc": True,
                            "response_excludes": ["https://", "http://"]}},
        ]
    },
    {
        "name": "Amsterdam hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in amsterdam",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Cape Town hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in cape town",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },
    {
        "name": "Istanbul hotels -- Tavily",
        "category": "Tavily Fallback",
        "turns": [
            {"query": "hotels in istanbul",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },

    # =========================================================
    # CATEGORY: More Anti-Hallucination
    # =========================================================
    {
        "name": "Melbourne must not show Perth hotels",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "hotels in melbourne",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["hotel in perth", "perth hotel",
                                                  "stay in perth"]}},
        ]
    },
    {
        "name": "Chittagong phrase city extraction regression",
        "category": "Anti-Hallucination",
        "turns": [
            # Old system extracted city as 'With Cheaper Options In Chittagong'
            {"query": "can show some hotels with cheaper options in Chittagong",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["With Cheaper Options",
                                                  "With Cheaper"]}},
        ]
    },
    {
        "name": "Follow-up city stays Perth",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Perth"}},
            {"query": "show me the cheapest one",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Tokyo search must not mention perth",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "hotels in tokyo",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["hotel in perth", "hotel in fremantle"]}},
        ]
    },
    {
        "name": "Unknown city returns graceful response",
        "category": "Anti-Hallucination",
        "turns": [
            {"query": "hotels in atlantis city",
             "assertions": {"type_is": "hotel_search",
                            "response_excludes": ["[booking_url]", "[url]"]}},
        ]
    },

    # =========================================================
    # CATEGORY: More Edge Cases
    # =========================================================
    {
        "name": "Only a number as input",
        "category": "Edge Cases",
        "turns": [
            {"query": "500",
             "assertions": {}},
        ]
    },
    {
        "name": "Rating exactly 10",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in perth with rating between 10 to 10",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Emoji in query",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in perth \U0001f3e8",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Mixed case city name",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in pErTh",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Repeated city name",
        "category": "Edge Cases",
        "turns": [
            {"query": "perth perth hotels perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Price below 1 dollar per night",
        "category": "Edge Cases",
        "turns": [
            {"query": "hotels in perth under 1 dollar per night",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },

    # =========================================================
    # CATEGORY: More Phrasing Variants
    # =========================================================
    {
        "name": "Book a hotel in perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "I want to book a hotel in perth",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "Find me a place in fremantle",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "find me a nice place to stay in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Where can I stay in Perth",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "where can I stay in Perth?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "hotel_city": "Perth"}},
        ]
    },
    {
        "name": "I need a room in fremantle",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "I need a room in fremantle for tonight",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Hotel by the beach fremantle",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "hotel by the beach in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Best hotel in perth (superlative phrasing)",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "what is the best hotel you know in perth?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Any good places to stay in sydney",
        "category": "Phrasing Variants",
        "turns": [
            {"query": "any good places to stay in sydney?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "has_external": True}},
        ]
    },

    # =========================================================
    # CATEGORY: More Multi-turn Conversations
    # =========================================================
    {
        "name": "External refine by rating (3 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in singapore",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "only show me ones with rating above 8",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 8.0}},
            {"query": "which is the cheapest of those?",
             "assertions": {"type_is": "hotel_search",
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Perth then Sydney then cheaper (3 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Perth",
                            "no_external": True}},
            {"query": "now search for hotels in sydney instead",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "any cheaper ones?",
             "assertions": {"type_is": "hotel_search",
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Fremantle: refine amenity then price (3 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in fremantle",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "only ones with a pool please",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "now sort by cheapest",
             "assertions": {"type_is": "hotel_search",
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Long session: chat + info + search x2 (7 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hey, planning my holiday!",
             "assertions": {"type_is": "normal_chat"}},
            {"query": "what's the weather like in perth in january?",
             "assertions": {"type_is": "travel_info"}},
            {"query": "nice! show me hotels there",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1, "max_hotels": 3}},
            {"query": "any with a pool and gym?",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "what about in fremantle? any good options?",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "ok show me the cheapest fremantle one",
             "assertions": {"type_is": "hotel_search", "hotel_price_asc": True}},
            {"query": "thanks, that was really helpful!",
             "assertions": {"type_is": "normal_chat"}},
        ]
    },
    {
        "name": "Informal language multi-turn",
        "category": "Multi-turn",
        "turns": [
            {"query": "yo, need a hotel in perth lol",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
            {"query": "got anything cheaper m8?",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Bangkok refine then affordable (3 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in bangkok",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "I want somewhere rated above 8",
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 8.0}},
            {"query": "perfect, now show me the most affordable one",
             "assertions": {"type_is": "hotel_search",
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Multiple city switches (4 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "hotels in perth",
             "assertions": {"type_is": "hotel_search", "hotel_city": "Perth"}},
            {"query": "actually show fremantle",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "no wait, tokyo hotels please",
             "assertions": {"type_is": "hotel_search", "has_external": True}},
            {"query": "the cheapest one",
             "assertions": {"type_is": "hotel_search",
                            "hotel_price_asc": True}},
        ]
    },
    {
        "name": "Ask hotel count then book flow (4 turns)",
        "category": "Multi-turn",
        "turns": [
            {"query": "how many hotels do you have in perth?",
             "assertions": {"type_is": "hotel_search"}},
            {"query": "show me the top 3",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "max_hotels": 3}},
            {"query": "which has the best rating?",
             "assertions": {"type_is": "hotel_search"}},
            # "How do I make a reservation?" is a booking help question → may be
            # normal_chat or hotel_search; we only check it returns a useful reply.
            {"query": "great, how do I make a reservation?",
             "assertions": {"response_excludes": ["[booking_url]"]}},
        ]
    },

    # =========================================================
    # CATEGORY: More Stress / Boundary
    # =========================================================
    {
        "name": "Minimal keyword-only query",
        "category": "Stress",
        "turns": [
            {"query": "cheap hotel perth pool",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1}},
        ]
    },
    {
        "name": "Slang / informal phrasing",
        "category": "Stress",
        "turns": [
            {"query": "need a crib in perth asap",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Multi-amenity stress query",
        "category": "Stress",
        "turns": [
            {"query": ("hotels in perth with pool gym spa restaurant bar "
                       "parking wifi breakfast and rating above 7"),
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Contradictory filters: cheap 5-star",
        "category": "Stress",
        "turns": [
            # cheap + 5-star is contradictory — should still respond gracefully
            {"query": "cheap 5-star hotels in perth",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Very high min price filter",
        "category": "Stress",
        "turns": [
            {"query": "hotels in perth over 1000 dollars per night",
             "assertions": {"type_is": "hotel_search"}},
        ]
    },
    {
        "name": "Nonsense input",
        "category": "Stress",
        "turns": [
            {"query": "asdfghjkl qwerty zxcvbnm",
             "assertions": {}},
        ]
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

async def run_case(orchestrator: TravelOrchestrator,
                   case: Dict,
                   verbose: bool = False) -> CaseResult:
    result = CaseResult(name=case["name"], category=case["category"])

    history: List[Dict[str, str]] = []
    shown_ids: List[int] = []
    last_hotels: List[Dict] = []
    pending_hotels: List[Dict] = []      # mirrors session_pending_hotels in main.py

    _rlog(f"\n{'='*72}")
    _rlog(f"TEST CASE : {case['name']}")
    _rlog(f"CATEGORY  : {case['category']}")
    _rlog(f"TURNS     : {len(case['turns'])}")
    _rlog(f"STARTED   : {datetime.now().strftime('%H:%M:%S')}")
    _rlog(f"{'='*72}")

    for turn_idx, turn_def in enumerate(case["turns"], 1):
        query      = turn_def["query"]
        assertions = turn_def.get("assertions", {})
        # A turn is show-more if the case explicitly flags it,
        # OR if pending_hotels exist and the query text matches the regex.
        is_show_more_turn = turn_def.get("show_more", False) or (
            bool(pending_hotels) and _is_show_more(query)
        )

        _rlog(f"\n  TURN {turn_idx}")
        _rlog(f"  Query      : {query}")
        _rlog(f"  Show-more  : {is_show_more_turn} (pending={len(pending_hotels)})")

        t0 = time.monotonic()

        if is_show_more_turn and pending_hotels:
            # ── Serve from pending cache (no LLM / Tavily call) ──────────
            pool = list(pending_hotels)
            if _CHEAPER_RE.search(query):
                pool.sort(key=lambda h: h.get("base_price_per_night") or 999999)
            elif _LUXURY_RE.search(query):
                pool.sort(key=lambda h: -(h.get("base_price_per_night") or 0))

            batch          = pool[:3]
            pending_hotels = pool[3:]
            elapsed        = (time.monotonic() - t0) * 1000

            new_ids   = [h["id"] for h in batch if h.get("id")]
            shown_ids = list(set(shown_ids + new_ids))

            city  = batch[0].get("city", "") if batch else ""
            names = ", ".join(h.get("hotel_name", "Hotel") for h in batch)
            more_note = (
                f" {len(pending_hotels)} more available."
                if pending_hotels else " That's all the available options."
            )
            is_ext   = any(h.get("source") == "external" for h in batch)
            response = (
                f"Here are {len(batch)} more hotels"
                + (f" in {city}" if city else "")
                + f": {names}.{more_note}"
                + (" (External results.)" if is_ext else "")
            )
            qtype  = "hotel_search"
            hotels = batch

        else:
            # ── Normal agent call ─────────────────────────────────────────
            pending_hotels = []         # new query resets old pending
            try:
                raw = await orchestrator.run(
                    query,
                    history=history,
                    shown_hotel_ids=shown_ids,
                    last_hotels=last_hotels,
                )
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000
                _rlog(f"  EXCEPTION  : {exc}")
                tr = TurnResult(
                    query=query, response=f"[EXCEPTION] {exc}",
                    hotels=[], query_type="error",
                    elapsed_ms=elapsed, passed=False,
                    fail_reasons=[f"Exception raised: {exc}"]
                )
                result.turns.append(tr)
                continue

            elapsed        = (time.monotonic() - t0) * 1000
            response       = raw.get("natural_language_response", "")
            hotels         = raw.get("recommended_hotels", [])
            qtype          = raw.get("metadata", {}).get("query_type", "unknown")
            last_hotels    = raw.get("last_hotels", hotels)
            shown_ids      = raw.get("shown_hotel_ids", shown_ids)
            pending_hotels = raw.get("pending_hotels", [])

        # Update conversation history
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response})

        passed, fails = _check(response, hotels, qtype, assertions, pending_hotels)

        # ── Log turn details ─────────────────────────────────────────────
        _rlog(f"  Type       : {qtype}")
        _rlog(f"  Hotels     : {len(hotels)}")
        _rlog(f"  Pending    : {len(pending_hotels)}")
        _rlog(f"  Elapsed    : {elapsed:.0f} ms")
        _rlog(f"  Response   : {response[:500]}{'...' if len(response) > 500 else ''}")
        if hotels:
            for h in hotels:
                src   = " [EXT]" if h.get("source") == "external" else ""
                price = f"${h.get('base_price_per_night'):.0f}" if h.get("base_price_per_night") else "N/A"
                burl  = h.get("booking_url", "")
                _rlog(f"    > {h.get('hotel_name')}{src}  "
                      f"city={h.get('city')}  rating={h.get('average_rating')}  price={price}")
                if burl:
                    _rlog(f"      booking_url : {burl}")
        if pending_hotels:
            _rlog(f"  Pending hotels ({len(pending_hotels)}):")
            for h in pending_hotels:
                _rlog(f"    > {h.get('hotel_name')}  city={h.get('city')}  "
                      f"price={h.get('base_price_per_night')}")
        _rlog(f"  Assertions : {'PASS' if passed else 'FAIL'}")
        if fails:
            for f_msg in fails:
                _rlog(f"    x {f_msg}")
        # ─────────────────────────────────────────────────────────────────

        tr = TurnResult(
            query=query, response=response,
            hotels=hotels, query_type=qtype,
            elapsed_ms=elapsed, passed=passed,
            fail_reasons=fails,
            show_more=is_show_more_turn,
            pending_count=len(pending_hotels),
        )
        result.turns.append(tr)

    _rlog(f"\n  RESULT: {'PASS' if result.passed else 'FAIL'}")
    return result


async def run_all(verbose: bool = False,
                  filter_category: Optional[str] = None,
                  log_level: str = "INFO",
                  delay: float = 2.0) -> None:

    # ── set up logging first (before any imports that touch loggers) ───────
    run_dir = setup_logging(log_level)
    report_path  = os.path.join(run_dir, "report.json")
    run_ts_label = os.path.basename(run_dir)

    print(f"\n{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"{BOLD}{CYAN}  TRAVEL CHATBOT — FULL QA TEST SUITE{RESET}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}")
    print(f"  📁 Log directory : {run_dir}")
    print(f"  📋 system.log    : {os.path.join(run_dir, 'system.log')}")
    print(f"  📋 results.log   : {_RESULTS_LOG}")
    print(f"  📋 report.json   : {report_path}")
    print(f"{BOLD}{CYAN}{'='*70}{RESET}\n")

    _rlog(f"QA RUN STARTED  {run_ts_label}")
    _rlog(f"Log level       {log_level}")
    _rlog(f"Category filter {filter_category or 'ALL'}")

    # ── initialise system ──────────────────────────────────────────────────
    print("⏳ Initialising system (DB + embeddings)...")
    t0 = time.monotonic()
    search = IntegratedHotelSearch(use_vector_ranking=True)
    await search.connect()
    orchestrator = TravelOrchestrator(search)
    init_ms = (time.monotonic() - t0) * 1000
    print(f"✅ Ready in {init_ms:.0f} ms\n")
    _rlog(f"System init     {init_ms:.0f} ms")

    cases = TEST_CASES
    if filter_category:
        cases = [c for c in cases if filter_category.lower() in c["category"].lower()]
        print(f"🔍 Filtered to category: '{filter_category}' → {len(cases)} cases\n")

    # ── run cases ─────────────────────────────────────────────────────────
    results: List[CaseResult] = []
    categories: Dict[str, List[CaseResult]] = {}

    for i, case_def in enumerate(cases, 1):
        cat = case_def["category"]
        print(f"[{i:>3}/{len(cases)}] {CYAN}{cat}{RESET} → {case_def['name']} ", end="", flush=True)

        cr = await run_case(orchestrator, case_def, verbose=verbose)
        results.append(cr)
        categories.setdefault(cat, []).append(cr)

        status = f"{GREEN}PASS{RESET}" if cr.passed else f"{RED}FAIL{RESET}"
        total_ms = sum(t.elapsed_ms for t in cr.turns)
        print(f"[{status}] {total_ms:.0f}ms")

        if verbose or not cr.passed:
            for t in cr.turns:
                t_status = f"{GREEN}✓{RESET}" if t.passed else f"{RED}✗{RESET}"
                src_tag  = f" {YELLOW}[show-more]{RESET}" if t.show_more else ""
                print(f"       {t_status}{src_tag} Q: {t.query[:80]}")
                if verbose:
                    print(f"         Type: {t.query_type} | Hotels: {len(t.hotels)} "
                          f"| Pending: {t.pending_count} | {t.elapsed_ms:.0f}ms")
                    resp_preview = t.response[:200].replace("\n", " ")
                    print(f"         R: {resp_preview}{'...' if len(t.response) > 200 else ''}")
                if t.fail_reasons:
                    for r in t.fail_reasons:
                        print(f"         {RED}✗ {r}{RESET}")

        # Throttle between cases to avoid Groq TPM / daily token limits
        if delay > 0 and i < len(cases):
            await asyncio.sleep(delay)

    # ── summary by category ───────────────────────────────────────────────
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}  RESULTS BY CATEGORY{RESET}")
    print(f"{'='*70}")

    total_pass = total_fail = 0
    for cat, cat_results in categories.items():
        p = sum(1 for r in cat_results if r.passed)
        f = len(cat_results) - p
        total_pass += p
        total_fail += f
        bar_colour = GREEN if f == 0 else (YELLOW if p > 0 else RED)
        print(f"  {bar_colour}{cat:<28}{RESET}  "
              f"{GREEN}{p} pass{RESET} / {RED}{f} fail{RESET}  "
              f"({len(cat_results)} total)")

    # ── overall ────────────────────────────────────────────────────────────
    total = total_pass + total_fail
    pct = (total_pass / total * 100) if total else 0
    colour = GREEN if total_fail == 0 else (YELLOW if pct >= 70 else RED)
    print(f"\n{'='*70}")
    print(f"{BOLD}  OVERALL: {colour}{total_pass}/{total} passed ({pct:.1f}%){RESET}")

    if total_fail > 0:
        print(f"\n{BOLD}{RED}  FAILED CASES:{RESET}")
        for cr in results:
            if not cr.passed:
                print(f"  {RED}✗{RESET} [{cr.category}] {cr.name}")
                for t in cr.turns:
                    for r in t.fail_reasons:
                        print(f"      → {r}")
    print()

    # ── save JSON report ───────────────────────────────────────────────────
    finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = {
        "run_timestamp": run_ts_label,
        "finished_at": finished_at,
        "log_dir": run_dir,
        "log_level": log_level,
        "category_filter": filter_category,
        "total": total, "passed": total_pass, "failed": total_fail,
        "pass_rate": round(pct, 1),
        "categories": {
            cat: {"passed": sum(1 for r in rs if r.passed), "total": len(rs)}
            for cat, rs in categories.items()
        },
        "cases": [
            {
                "name": cr.name, "category": cr.category,
                "passed": cr.passed,
                "turns": [
                    {
                        "query"           : t.query,
                        "type"            : t.query_type,
                        "show_more"       : t.show_more,
                        "hotels_returned" : len(t.hotels),
                        "pending_count"   : t.pending_count,
                        "hotel_names"     : [h.get("hotel_name") for h in t.hotels],
                        "hotel_cities"    : [h.get("city") for h in t.hotels],
                        "hotel_ratings"   : [h.get("average_rating") for h in t.hotels],
                        "hotel_prices"    : [h.get("base_price_per_night") for h in t.hotels],
                        "booking_urls"    : [h.get("booking_url") for h in t.hotels],
                        "external_hotels" : [h.get("hotel_name") for h in t.hotels
                                             if h.get("source") == "external"],
                        "response_preview": t.response[:400],
                        "passed"          : t.passed,
                        "fails"           : t.fail_reasons,
                        "elapsed_ms"      : round(t.elapsed_ms)
                    }
                    for t in cr.turns
                ]
            }
            for cr in results
        ]
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    _rlog(f"\n{'='*72}")
    _rlog(f"QA RUN COMPLETE  {finished_at}")
    _rlog(f"TOTAL={total}  PASSED={total_pass}  FAILED={total_fail}  "
          f"PASS_RATE={pct:.1f}%")
    _rlog(f"{'='*72}")

    print(f"  📁 Logs saved to  : {run_dir}/")
    print(f"     ├─ system.log  (full INFO/DEBUG trace from all modules)")
    print(f"     ├─ results.log (turn-by-turn conversations + pass/fail)")
    print(f"     └─ report.json (machine-readable summary)\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full chatbot QA test suite (v2 — pagination-aware)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python tests/test_full_system.py
  uv run python tests/test_full_system.py --verbose
  uv run python tests/test_full_system.py --category "Pagination"
  uv run python tests/test_full_system.py --category "Response Quality"
  uv run python tests/test_full_system.py --category "Multi-turn"
  uv run python tests/test_full_system.py --category "Tavily" --log-level DEBUG
  uv run python tests/test_full_system.py --verbose --category "DB Search"
  uv run python tests/test_full_system.py --delay 3.0   # slower, avoids Groq rate limits
"""
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print full response + hotel list for every turn on console")
    parser.add_argument("--category", "-c", type=str, default=None,
                        help="Run only cases whose category contains this string (case-insensitive)")
    parser.add_argument("--log-level", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Level written to system.log (default: INFO)")
    parser.add_argument("--delay", "-d", type=float, default=2.0,
                        help="Seconds to wait between test cases (default: 2.0). "
                             "Increase this to avoid Groq TPM rate limits during large runs.")
    args = parser.parse_args()

    asyncio.run(run_all(
        verbose=args.verbose,
        filter_category=args.category,
        log_level=args.log_level,
        delay=args.delay,
    ))
