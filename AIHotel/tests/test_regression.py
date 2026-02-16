"""Test the two specific failing tests from the 100-question suite."""
import asyncio
import main
from agents.orchestrator import TravelOrchestrator

async def test_failing_cases():
    """Test the two cases that failed in the 100-question test suite."""
    print("🧪 Re-testing Previously Failed Tests from Suite\n")
    print("=" * 80)
    
    # Initialize system
    await main.initialize_system()
    search = main._search_system
    orchestrator = main._orchestrator
    
    try:
        # Test #53: hotels in Atlantis
        print("Test #53: ❌ INVALID/EDGE CASES - 'hotels in Atlantis'")
        result1 = await orchestrator.run("hotels in Atlantis")
        hotels1 = len(result1.get('hotels', []) or result1.get('recommended_hotels', []))
        response1 = result1.get('response', result1.get('natural_language_response', ''))[:100]
        
        # Should return 0 hotels (invalid city)
        passed1 = hotels1 == 0
        print(f"Hotels Found: {hotels1}")
        print(f"Response: {response1}")
        print(f"Expected: 0 hotels (invalid city)")
        print(f"Status: {'✅ PASS' if passed1 else '❌ FAIL'}")
        print()
        
        # Test #54: hotels under $0
        print("Test #54: ❌ INVALID/EDGE CASES - 'hotels under $0'")
        result2 = await orchestrator.run("hotels under $0")
        hotels2 = len(result2.get('hotels', []) or result2.get('recommended_hotels', []))
        response2 = result2.get('response', result2.get('natural_language_response', ''))[:100]
        
        # Should return 0 hotels (invalid price)
        passed2 = hotels2 == 0
        print(f"Hotels Found: {hotels2}")
        print(f"Response: {response2}")
        print(f"Expected: 0 hotels (invalid price)")
        print(f"Status: {'✅ PASS' if passed2 else '❌ FAIL'}")
        print()
        
        # Bonus: Test a valid query to ensure we didn't break normal functionality
        print("Bonus Test: Valid Query - 'hotels in Miami under $250'")
        result3 = await orchestrator.run("hotels in Miami under $250")
        hotels3 = len(result3.get('hotels', []) or result3.get('recommended_hotels', []))
        
        passed3 = hotels3 > 0
        print(f"Hotels Found: {hotels3}")
        print(f"Expected: > 0 hotels (valid query)")
        print(f"Status: {'✅ PASS' if passed3 else '❌ FAIL'}")
        print()
        
        print("=" * 80)
        total_passed = sum([passed1, passed2, passed3])
        print(f"Overall: {total_passed}/3 tests passed")
        
        if total_passed == 3:
            print("✅ All previously failing tests now pass!")
            print("✅ Normal functionality still works!")
            return 0
        else:
            print("❌ Some tests still failing")
            return 1
            
    finally:
        await search.close()

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(test_failing_cases())
    sys.exit(exit_code)
