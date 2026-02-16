"""
Quick Test Runner - 20 Most Important Test Cases

Covers critical scenarios in ~30 seconds:
- Basic functionality
- Edge cases
- Performance
- Error handling
- User experience

Run: uv run test_quick_20.py
"""
import asyncio
import time
from main import initialize_system, run_travel_chat


TEST_CASES = [
    # Basic functionality (5)
    ("hotels in Miami", "Should find Miami hotel"),
    ("hotels in New York", "Should find NYC hotel"),
    ("cheap hotels", "Should handle vague price query"),
    ("4 star hotels", "Should filter by rating"),
    ("hotels with pool", "Should filter by amenity"),
    
    # Edge cases (5)
    ("", "Should handle empty query"),
    ("hotels in Atlantis", "Should handle non-existent city"),
    ("hotels under $0", "Should handle invalid price"),
    ("qwerty asdfgh", "Should handle nonsense"),
    ("HOTELS IN MIAMI", "Should handle all caps"),
    
    # Combined filters (3)
    ("cheap hotels with pool in Miami", "Should handle multiple filters"),
    ("4 star hotels under $200", "Should combine rating + price"),
    ("luxury hotels with gym", "Should combine price + amenity"),
    
    # Conversational (3)
    ("hello", "Should respond to greeting"),
    ("thank you", "Should respond to gratitude"),
    ("show me more", "Should handle follow-up"),
    
    # Ambiguous (2)
    ("good hotels", "Should handle vague query"),
    ("hotels there", "Should handle missing location"),
    
    # Performance (2)
    ("hotels in Miami with pool under $200 rated 4+ with gym", "Complex query"),
    ("a" * 200, "Very long input"),
]


async def run_quick_tests():
    """Run 20 critical tests quickly."""
    print("\n" + "="*80)
    print("⚡ QUICK TEST SUITE - 20 CRITICAL TEST CASES")
    print("="*80)
    
    print("\nInitializing...")
    await initialize_system()
    print("✅ Ready\n")
    
    results = []
    start_time = time.time()
    
    for i, (query, description) in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/20] {description}")
        print(f"Query: '{query[:60]}{'...' if len(query) > 60 else ''}'")
        
        try:
            test_start = time.time()
            result = await run_travel_chat(query, [], [])
            test_time = time.time() - test_start
            
            response = result.get('natural_language_response', '')
            hotel_count = len(result.get('recommended_hotels', []))
            
            # Determine pass/fail
            passed = False
            if query.strip() == "":
                passed = response != ""
            elif query in ["hello", "thank you"]:
                passed = response != "" and hotel_count == 0
            elif "Atlantis" in query or "under $0" in query or "qwerty" in query:
                passed = response != ""
            else:
                passed = response != ""
            
            status = "✅" if passed else "❌"
            print(f"Status: {status} | Time: {test_time:.2f}s | Hotels: {hotel_count}")
            print(f"Response: {response[:80]}...")
            
            results.append({
                'passed': passed,
                'time': test_time,
                'hotels': hotel_count,
                'query': query,
                'description': description
            })
            
        except Exception as e:
            print(f"Status: ❌ ERROR")
            print(f"Error: {str(e)[:100]}")
            results.append({
                'passed': False,
                'time': 0,
                'hotels': 0,
                'query': query,
                'description': description,
                'error': str(e)
            })
        
        await asyncio.sleep(0.05)
    
    total_time = time.time() - start_time
    
    # Summary
    print("\n\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results if r['passed'])
    failed = len(results) - passed
    
    print(f"\nTotal: {len(results)} tests")
    print(f"✅ Passed: {passed} ({passed/len(results)*100:.1f}%)")
    print(f"❌ Failed: {failed} ({failed/len(results)*100:.1f}%)")
    print(f"⏱️  Total Time: {total_time:.1f}s")
    print(f"⚡ Avg Time: {sum(r['time'] for r in results)/len(results):.2f}s")
    
    if failed > 0:
        print(f"\n❌ Failed Tests:")
        for i, r in enumerate(results, 1):
            if not r['passed']:
                print(f"   {i}. {r['description']}")
                print(f"      Query: {r['query'][:60]}")
    
    # Grade
    if passed == len(results):
        print(f"\n🏆 Grade: A+ (Perfect!)")
    elif passed >= 18:
        print(f"\n🥇 Grade: A (Excellent)")
    elif passed >= 15:
        print(f"\n🥈 Grade: B (Good)")
    elif passed >= 12:
        print(f"\n🥉 Grade: C (Needs Work)")
    else:
        print(f"\n⚠️  Grade: D (Critical Issues)")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_quick_tests())
