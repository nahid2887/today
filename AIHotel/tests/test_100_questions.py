"""
100 Question Test Suite - SQA & Customer Perspective

Tests cover:
- Normal user queries
- Edge cases
- Invalid inputs
- Ambiguous queries
- Corner cases
- Performance scenarios
- Data validation
- User experience issues

Run: uv run test_100_questions.py
"""
import asyncio
import time
from typing import Dict, Any, List
from main import initialize_system, run_travel_chat, get_database_statistics


# Test categories with questions
TEST_SUITE = {
    "🎯 BASIC HOTEL SEARCH (10 tests)": [
        "hotels in Miami",
        "show me hotels in New York",
        "find hotels in San Francisco",
        "I need a hotel in Chicago",
        "search hotels in Los Angeles",
        "hotels near Boston",
        "find me a place to stay in Seattle",
        "accommodation in Denver",
        "where can I stay in Portland",
        "hotels available in Dallas",
    ],
    
    "💰 PRICE FILTERING (10 tests)": [
        "cheap hotels in Miami",
        "luxury hotels in New York",
        "hotels under $100",
        "hotels under $200 in San Francisco",
        "expensive hotels in Los Angeles",
        "budget hotels in Chicago",
        "hotels less than $150",
        "affordable hotels in Boston",
        "hotels under 100 dollars",
        "hotels between $100 and $200",  # Range query
    ],
    
    "⭐ RATING FILTERING (10 tests)": [
        "4 star hotels in Miami",
        "5 star hotels",
        "highly rated hotels in New York",
        "best hotels in San Francisco",
        "top rated hotels",
        "4.5+ rated hotels",
        "hotels with good reviews",
        "4.5 star and above",
        "hotels rated 4 or higher",
        "excellent hotels in Chicago",
    ],
    
    "🏊 AMENITY FILTERING (10 tests)": [
        "hotels with pool",
        "hotels with gym in Miami",
        "hotels with wifi",
        "hotels with spa and pool",
        "hotels with restaurant",
        "hotels with parking",
        "hotels with free breakfast",  # Not in DB
        "hotels with beach access",
        "hotels with bar",
        "hotels with conference rooms",
    ],
    
    "🔀 COMBINED FILTERS (10 tests)": [
        "cheap hotels with pool in Miami",
        "4 star hotels under $200",
        "luxury hotels with spa",
        "highly rated budget hotels",
        "hotels with gym under $150",
        "5 star hotels with pool and restaurant",
        "best cheap hotels in New York",
        "affordable 4+ rated hotels with wifi",
        "luxury hotels in San Francisco with beach access",
        "top rated hotels under $250 with parking",
    ],
    
    "❌ INVALID/EDGE CASES (10 tests)": [
        "",  # Empty query
        "    ",  # Whitespace only
        "hotels in Atlantis",  # Non-existent city
        "hotels under $0",  # Invalid price
        "hotels rated 10",  # Invalid rating
        "qwerty asdfgh",  # Random text
        "hotels in",  # Incomplete query
        "show me",  # Too vague
        "!!!###$$$",  # Special characters only
        "hotels" * 50,  # Very long query
    ],
    
    "🌍 LOCATION VARIANTS (10 tests)": [
        "hotels in miami beach",  # City variant
        "hotels near miami",
        "hotels in SF",  # Abbreviation
        "hotels in san fran",  # Informal name
        "hotels in NYC",  # Abbreviation
        "hotels in new orleans",  # Multi-word city
        "hotels in las vegas",
        "hotels in LA",  # Abbreviation
        "hotels in napa valley",  # Multi-word
        "hotels in phoenix arizona",  # City + state
    ],
    
    "💬 CONVERSATIONAL QUERIES (10 tests)": [
        "hello",
        "thank you",
        "hi there",
        "good morning",
        "can you help me?",
        "what can you do?",
        "I'm looking for a hotel",
        "I need help finding accommodation",
        "thanks for your help",
        "goodbye",
    ],
    
    "🔢 BOUNDARY TESTING (10 tests)": [
        "hotels rated 5.0",  # Max rating
        "hotels rated 0",  # Min rating
        "hotels under $1",  # Very low price
        "hotels under $10000",  # Very high price
        "show me 1 hotel",  # Min limit
        "show me 100 hotels",  # High limit
        "hotels with 0 stars",
        "free hotels",  # $0 price
        "hotels rated exactly 4.5",
        "hotels priced at $200",  # Exact price
    ],
    
    "🤔 AMBIGUOUS QUERIES (10 tests)": [
        "good hotels",  # Vague
        "nice place",  # Very vague
        "somewhere to stay",  # Generic
        "find me something",  # No details
        "hotels there",  # Missing location
        "best deal",  # Ambiguous criteria
        "popular hotels",  # Vague metric
        "recommended hotels",  # No criteria
        "hotels please",  # Minimal info
        "I want a hotel",  # No specifics
    ],
}

# Additional special test cases
SPECIAL_TESTS = {
    "🐛 BUG HUNTING (10 tests)": [
        "hotels in Miami with Pool",  # Case sensitivity
        "HOTELS IN NEW YORK",  # All caps
        "hotels   in   miami",  # Multiple spaces
        "hotel in miami",  # Singular vs plural
        "hotels in miami.",  # Punctuation
        "Hotels In Miami!",  # Mixed case + punctuation
        "show hotels, miami",  # Wrong syntax
        "miami hotels",  # Reverse order
        "hotels @ miami",  # Special char
        "hotels in miami??",  # Multiple question marks
    ],
    
    "🔄 FOLLOW-UP QUERIES (10 tests)": [
        "show me more",
        "what else do you have",
        "any other options",
        "cheaper ones",
        "better rated ones",
        "with more amenities",
        "in a different city",
        "similar hotels",
        "show me the first one again",
        "I want to see more expensive hotels",
    ],
    
    "❓ QUESTION FORMATS (10 tests)": [
        "what hotels are in miami?",
        "can you show me hotels?",
        "do you have hotels in miami?",
        "are there hotels with pool?",
        "which hotels are cheap?",
        "where can i find hotels?",
        "how much are hotels in miami?",
        "why are hotels expensive?",
        "when can i book?",
        "who has the best hotels?",
    ],
    
    "🔢 NUMBER FORMATS (10 tests)": [
        "hotels under 200 dollars",
        "hotels under $200",
        "hotels under 200",
        "hotels under two hundred dollars",
        "hotels at $200",
        "hotels for 200 per night",
        "hotels costing $200",
        "200 dollar hotels",
        "$200 hotels",
        "hotels - $200",
    ],
    
    "⚡ PERFORMANCE TESTS (5 tests)": [
        "hotels",  # Minimal query
        "hotels in Miami with pool under $200 rated 4+ with gym and spa and restaurant and parking",  # Complex
        "a" * 500,  # Very long input
        "hotels " + "in Miami " * 20,  # Repeated phrases
        "show me all available luxury 5 star hotels with pool gym spa restaurant bar parking wifi beach access in Miami Florida under $300 per night",  # Super detailed
    ],
    
    "🚫 NEGATIVE QUERIES (5 tests)": [
        "hotels without pool",
        "hotels not in Miami",
        "cheap but not bad hotels",
        "hotels excluding New York",
        "hotels that don't have gym",
    ],
}


class TestResult:
    def __init__(self, query: str, category: str, test_num: int):
        self.query = query
        self.category = category
        self.test_num = test_num
        self.response = ""
        self.hotel_count = 0
        self.execution_time = 0.0
        self.error = None
        self.passed = False
        
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        result = f"\n{'='*80}\n"
        result += f"Test #{self.test_num} [{self.category}] {status}\n"
        result += f"{'='*80}\n"
        result += f"Query: '{self.query}'\n"
        result += f"Time: {self.execution_time:.3f}s\n"
        
        if self.error:
            result += f"Error: {self.error}\n"
        else:
            result += f"Hotels Found: {self.hotel_count}\n"
            result += f"Response Preview: {self.response[:200]}...\n" if len(self.response) > 200 else f"Response: {self.response}\n"
        
        return result


async def run_test(query: str, category: str, test_num: int, history: List = None) -> TestResult:
    """Run a single test query."""
    result = TestResult(query, category, test_num)
    
    try:
        start_time = time.time()
        
        response = await run_travel_chat(
            query=query,
            history=history or [],
            shown_hotel_ids=[]
        )
        
        result.execution_time = time.time() - start_time
        result.response = response.get('natural_language_response', '')
        result.hotel_count = len(response.get('recommended_hotels', []))
        
        # Determine pass/fail
        if query.strip() == "":
            # Empty query should handle gracefully
            result.passed = result.response != "" and result.error is None
        elif query.strip() in ["hello", "hi there", "good morning", "thank you", "thanks for your help", "goodbye"]:
            # Conversational queries should get response without hotels
            result.passed = result.response != "" and result.hotel_count == 0
        elif "in Atlantis" in query or "hotels under $0" in query or "hotels rated 10" in query:
            # Invalid queries should handle gracefully
            result.passed = result.response != "" and result.hotel_count == 0
        elif "qwerty asdfgh" in query or query == "!!!###$$$":
            # Nonsense queries should handle gracefully
            result.passed = result.response != ""
        else:
            # Normal queries should return response
            result.passed = result.response != ""
            
    except Exception as e:
        result.error = str(e)
        result.passed = False
    
    return result


async def run_all_tests():
    """Run all 100+ tests."""
    print("\n" + "="*80)
    print("🧪 HOTEL SEARCH SYSTEM - 100 QUESTION TEST SUITE")
    print("="*80)
    print("\nInitializing system...")
    
    await initialize_system()
    
    stats = await get_database_statistics()
    print(f"\n✅ System Ready")
    print(f"📊 Database: {stats['total_hotels']} hotels, {stats['total_cities']} cities")
    print(f"💰 Price Range: ${stats['min_price']:.0f} - ${stats['max_price']:.0f}")
    print(f"⭐ Avg Rating: {stats['avg_rating']:.2f}")
    
    results = []
    test_num = 1
    history = []
    
    # Run main test suite
    for category, questions in TEST_SUITE.items():
        print(f"\n\n{'='*80}")
        print(f"{category}")
        print(f"{'='*80}")
        
        for query in questions:
            result = await run_test(query, category, test_num, history)
            results.append(result)
            
            # Print result
            print(result)
            
            # Update history for conversational context (keep last 5)
            if result.response:
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": result.response})
                if len(history) > 10:
                    history = history[-10:]
            
            test_num += 1
            
            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)
    
    # Run special tests
    for category, questions in SPECIAL_TESTS.items():
        print(f"\n\n{'='*80}")
        print(f"{category}")
        print(f"{'='*80}")
        
        for query in questions:
            result = await run_test(query, category, test_num, history)
            results.append(result)
            print(result)
            test_num += 1
            await asyncio.sleep(0.1)
    
    # Generate summary report
    print("\n\n" + "="*80)
    print("📊 TEST SUMMARY REPORT")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.passed)
    failed_tests = total_tests - passed_tests
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"❌ Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    
    # Performance stats
    avg_time = sum(r.execution_time for r in results) / len(results)
    max_time = max(r.execution_time for r in results)
    min_time = min(r.execution_time for r in results)
    
    print(f"\n⚡ Performance:")
    print(f"   Average: {avg_time:.3f}s")
    print(f"   Fastest: {min_time:.3f}s")
    print(f"   Slowest: {max_time:.3f}s")
    
    # Hotel finding stats
    queries_with_hotels = [r for r in results if r.hotel_count > 0]
    print(f"\n🏨 Hotel Results:")
    print(f"   Queries returning hotels: {len(queries_with_hotels)}/{total_tests}")
    if queries_with_hotels:
        print(f"   Avg hotels per query: {sum(r.hotel_count for r in queries_with_hotels)/len(queries_with_hotels):.1f}")
    
    # Failed test details
    if failed_tests > 0:
        print(f"\n❌ Failed Tests Details:")
        for r in results:
            if not r.passed:
                print(f"\n   Test #{r.test_num}: {r.query[:50]}")
                print(f"   Category: {r.category}")
                if r.error:
                    print(f"   Error: {r.error[:100]}")
                else:
                    print(f"   Response: {r.response[:100]}")
    
    # Category breakdown
    print(f"\n📈 Results by Category:")
    categories = {}
    for r in results:
        cat = r.category
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r.passed:
            categories[cat]["passed"] += 1
    
    for cat, stats in categories.items():
        pass_rate = stats["passed"] / stats["total"] * 100
        status = "✅" if pass_rate == 100 else "⚠️" if pass_rate >= 70 else "❌"
        print(f"   {status} {cat}: {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if failed_tests > 10:
        print("   🔴 High failure rate - system needs significant improvements")
    elif failed_tests > 5:
        print("   🟡 Moderate failures - review failed cases and improve handling")
    else:
        print("   🟢 Good performance - minor improvements needed")
    
    if avg_time > 1.0:
        print("   ⚡ Performance optimization recommended (avg > 1s)")
    
    empty_result_rate = sum(1 for r in results if r.hotel_count == 0 and "hotel" in r.query.lower()) / total_tests * 100
    if empty_result_rate > 30:
        print(f"   🔍 {empty_result_rate:.1f}% queries return no hotels - improve search algorithm")
    
    print("\n" + "="*80)
    print("✅ Testing Complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
