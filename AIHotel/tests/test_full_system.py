"""
=============================================================================
FULL SYSTEM QA TEST SUITE
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
  - Multi-turn conversation threads
  - Boundary / stress tests

Run from the AIHotel directory:
    uv run python tests/test_full_system.py
    uv run python tests/test_full_system.py --verbose        (show full responses on console)
    uv run python tests/test_full_system.py --category "DB Search"
    uv run python tests/test_full_system.py --log-level DEBUG (capture DEBUG logs to file)

All runs automatically save to tests/logs/<timestamp>/:
    system.log   — full INFO/DEBUG logs from every subsystem
    results.log  — human-readable turn-by-turn results
    report.json  — machine-readable pass/fail report
=============================================================================
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import TravelOrchestrator
from core.integrated_search import IntegratedHotelSearch


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
           assertions: Dict) -> Tuple[bool, List[str]]:
    """
    Evaluate a single set of assertions against a turn result.

    Supported assertion keys:
      type_is          str   — expected query_type value
      response_contains list[str]  — all substrings must appear in response (case-insensitive)
      response_excludes list[str]  — none of these substrings may appear
      min_hotels       int   — at least N hotels returned
      max_hotels       int   — at most N hotels returned
      exact_hotels     int   — exactly N hotels
      hotel_city       str   — all returned hotels must have this city
      has_external     bool  — at least one hotel has source=="external"
      no_external      bool  — no hotel has source=="external"
      hotel_min_rating float — all returned hotels must have average_rating >= this
      hotel_max_rating float — all returned hotels must have average_rating <= this
      hotel_price_asc  bool  — prices must be non-decreasing (sorted cheapest first)
    """
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
        low = [h.get("hotel_name") for h in hotels
               if (h.get("average_rating") or 0) < assertions["hotel_min_rating"]]
        if low:
            fails.append(f"Hotels below min_rating {assertions['hotel_min_rating']}: {low}")

    if "hotel_max_rating" in assertions:
        high = [h.get("hotel_name") for h in hotels
                if (h.get("average_rating") or 0) > assertions["hotel_max_rating"]]
        if high:
            fails.append(f"Hotels above max_rating {assertions['hotel_max_rating']}: {high}")

    if assertions.get("hotel_price_asc"):
        prices = [h.get("base_price_per_night") for h in hotels
                  if h.get("base_price_per_night") is not None]
        if prices != sorted(prices):
            fails.append(f"Hotels not sorted cheapest-first: {prices}")

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
                            "response_contains": ["hello", "help", "assist"]}},
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
            {"query": "hotels in guildford",
             "assertions": {"type_is": "hotel_search", "min_hotels": 1,
                            "no_external": True}},
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
             "assertions": {"type_is": "hotel_search",
                            "hotel_min_rating": 9.0, "has_external": True}},
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
            {"query": "hotels in atlantis",
             "assertions": {"type_is": "hotel_search",
                            "response_contains": ["perth"]}},
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

    _rlog(f"\n{'='*72}")
    _rlog(f"TEST CASE : {case['name']}")
    _rlog(f"CATEGORY  : {case['category']}")
    _rlog(f"TURNS     : {len(case['turns'])}")
    _rlog(f"STARTED   : {datetime.now().strftime('%H:%M:%S')}")
    _rlog(f"{'='*72}")

    for turn_idx, turn_def in enumerate(case["turns"], 1):
        query = turn_def["query"]
        assertions = turn_def.get("assertions", {})

        _rlog(f"\n  TURN {turn_idx}")
        _rlog(f"  Query      : {query}")

        t0 = time.monotonic()
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

        elapsed = (time.monotonic() - t0) * 1000

        response    = raw.get("natural_language_response", "")
        hotels      = raw.get("recommended_hotels", [])
        qtype       = raw.get("metadata", {}).get("query_type", "unknown")
        last_hotels = raw.get("last_hotels", hotels)
        shown_ids   = raw.get("shown_hotel_ids", shown_ids)

        # Update conversation history
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response})

        passed, fails = _check(response, hotels, qtype, assertions)

        # ── Log turn details ─────────────────────────────────────────────
        _rlog(f"  Type       : {qtype}")
        _rlog(f"  Hotels     : {len(hotels)}")
        _rlog(f"  Elapsed    : {elapsed:.0f} ms")
        _rlog(f"  Response   : {response[:500]}{'…' if len(response)>500 else ''}")
        if hotels:
            for h in hotels:
                src   = " [EXTERNAL]" if h.get("source") == "external" else ""
                price = f"${h.get('base_price_per_night'):.0f}" if h.get("base_price_per_night") else "N/A"
                _rlog(f"    Hotel: {h.get('hotel_name')}{src}  "
                      f"city={h.get('city')}  rating={h.get('average_rating')}  price={price}")
        _rlog(f"  Assertions : {'PASS' if passed else 'FAIL'}")
        if fails:
            for f_msg in fails:
                _rlog(f"    ✗ {f_msg}")
        # ─────────────────────────────────────────────────────────────────

        tr = TurnResult(
            query=query, response=response,
            hotels=hotels, query_type=qtype,
            elapsed_ms=elapsed, passed=passed,
            fail_reasons=fails,
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
                print(f"       {t_status} Q: {t.query[:80]}")
                if verbose:
                    print(f"         Type: {t.query_type} | Hotels: {len(t.hotels)} | {t.elapsed_ms:.0f}ms")
                    # Truncate long responses
                    resp_preview = t.response[:200].replace("\n", " ")
                    print(f"         R: {resp_preview}{'…' if len(t.response) > 200 else ''}")
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
                        "query": t.query,
                        "type": t.query_type,
                        "hotels_returned": len(t.hotels),
                        "hotel_names": [h.get("hotel_name") for h in t.hotels],
                        "hotel_cities": [h.get("city") for h in t.hotels],
                        "hotel_ratings": [h.get("average_rating") for h in t.hotels],
                        "hotel_prices": [h.get("base_price_per_night") for h in t.hotels],
                        "external_hotels": [h.get("hotel_name") for h in t.hotels
                                            if h.get("source") == "external"],
                        "response_preview": t.response[:300],
                        "passed": t.passed,
                        "fails": t.fail_reasons,
                        "elapsed_ms": round(t.elapsed_ms)
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
        description="Full chatbot QA test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python tests/test_full_system.py
  uv run python tests/test_full_system.py --verbose
  uv run python tests/test_full_system.py --category "Multi-turn"
  uv run python tests/test_full_system.py --category "Tavily" --log-level DEBUG
  uv run python tests/test_full_system.py --verbose --category "DB Search"
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
