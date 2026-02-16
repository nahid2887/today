"""Quick test for the two bug fixes: conversational queries and invalid ratings."""
import asyncio
import main

async def test_fixes():
    """Test conversational query detection and invalid rating handling."""
    print("🧪 Testing Bug Fixes: Conversational Queries + Invalid Ratings\n")
    print("=" * 80)
    
    # Initialize system
    await main.initialize_system()
    orchestrator = main._orchestrator
    
    try:
        # Test conversational queries (should NOT return hotels)
        conversational_queries = [
            "hello",
            "hi there", 
            "thank you",
            "thanks for your help",
            "goodbye",
            "good morning"
        ]
        
        print("🗣️  CONVERSATIONAL QUERY TESTS\n")
        conv_passed = 0
        for query in conversational_queries:
            result = await orchestrator.run(query)
            # Query type is in metadata
            query_type = result.get('query_type', '') or result.get('metadata', {}).get('query_type', '')
            hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
            
            # Should be NORMAL_CHAT and return 0 hotels
            passed = query_type == 'normal_chat' and hotels == 0
            conv_passed += passed
            
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status} | \"{query}\"")
            print(f"       Type: {query_type}, Hotels: {hotels}")
            if not passed:
                print(f"       Expected: normal_chat with 0 hotels")
        
        print(f"\nConversational: {conv_passed}/{len(conversational_queries)} passed\n")
        print("=" * 80)
        
        # Test invalid rating (should return 0 hotels)
        print("\n⭐ INVALID RATING TEST\n")
        result = await orchestrator.run("hotels rated 10")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        
        rating_passed = hotels == 0
        status = "✅ PASS" if rating_passed else "❌ FAIL"
        
        print(f"{status} | \"hotels rated 10\"")
        print(f"       Hotels: {hotels}")
        print(f"       Expected: 0 hotels (rating 10 > 5 is invalid)")
        
        print("\n" + "=" * 80)
        
        # Summary
        total_passed = conv_passed + rating_passed
        total_tests = len(conversational_queries) + 1
        
        print(f"\n📊 SUMMARY: {total_passed}/{total_tests} tests passed")
        
        if total_passed == total_tests:
            print("✅ All fixes working correctly!")
            return 0
        else:
            print("❌ Some tests still failing")
            return 1
            
    finally:
        await main._search_system.close()

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(test_fixes())
    sys.exit(exit_code)
