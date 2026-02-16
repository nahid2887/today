"""Test the specific failing tests from the 100-question suite."""
import asyncio
import main

async def test_all_fixed_bugs():
    """Test all the bugs we've fixed."""
    print("🧪 Regression Test: All Fixed Bugs\n")
    print("=" * 80)
    
    # Initialize system
    await main.initialize_system()
    orchestrator = main._orchestrator
    search = main._search_system
    
    try:
        passed = 0
        failed = 0
        
        # Original 2 bugs (invalid city, invalid price)
        print("🐛 ORIGINAL BUGS (Tests #53-54)\n")
        
        result = await orchestrator.run("hotels in Atlantis")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        if hotels == 0:
            print("✅ Test #53: hotels in Atlantis → 0 hotels (PASS)")
            passed += 1
        else:
            print(f"❌ Test #53: hotels in Atlantis → {hotels} hotels (FAIL)")
            failed += 1
        
        result = await orchestrator.run("hotels under $0")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        if hotels == 0:
            print("✅ Test #54: hotels under $0 → 0 hotels (PASS)")
            passed += 1
        else:
            print(f"❌ Test #54: hotels under $0 → {hotels} hotels (FAIL)")
            failed += 1
        
        # Invalid rating bug
        print("\n⭐ INVALID RATING BUG (Test #55)\n")
        
        result = await orchestrator.run("hotels rated 10")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        if hotels == 0:
            print("✅ Test #55: hotels rated 10 → 0 hotels (PASS)")
            passed += 1
        else:
            print(f"❌ Test #55: hotels rated 10 → {hotels} hotels (FAIL)")
            failed += 1
        
        # Conversational query bugs
        print("\n💬 CONVERSATIONAL BUGS (Tests #71-74, 79-80)\n")
        
        conversational_tests = [
            ("Test #71", "hello"),
            ("Test #72", "thank you"),
            ("Test #73", "hi there"),
            ("Test #74", "good morning"),
            ("Test #79", "thanks for your help"),
            ("Test #80", "goodbye")
        ]
        
        for test_name, query in conversational_tests:
            result = await orchestrator.run(query)
            query_type = result.get('query_type', '') or result.get('metadata', {}).get('query_type', '')
            hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
            
            if query_type == 'normal_chat' and hotels == 0:
                print(f"✅ {test_name}: '{query}' → normal_chat, 0 hotels (PASS)")
                passed += 1
            else:
                print(f"❌ {test_name}: '{query}' → {query_type}, {hotels} hotels (FAIL)")
                failed += 1
        
        # Bonus: Valid queries still work
        print("\n✅ SANITY CHECK (Valid queries still work)\n")
        
        result = await orchestrator.run("hotels in Miami")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        if hotels > 0:
            print(f"✅ Valid query: hotels in Miami → {hotels} hotels (PASS)")
            passed += 1
        else:
            print(f"❌ Valid query: hotels in Miami → {hotels} hotels (FAIL)")
            failed += 1
        
        result = await orchestrator.run("hotels under $200")
        hotels = len(result.get('hotels', []) or result.get('recommended_hotels', []))
        if hotels > 0:
            print(f"✅ Valid query: hotels under $200 → {hotels} hotels (PASS)")
            passed += 1
        else:
            print(f"❌ Valid query: hotels under $200 → {hotels} hotels (FAIL)")
            failed += 1
        
        print("\n" + "=" * 80)
        print(f"\n📊 FINAL RESULTS: {passed}/{passed+failed} tests passed")
        
        if failed == 0:
            print("🎉 ALL BUGS FIXED! System is now production-ready!")
            return 0
        else:
            print(f"❌ {failed} tests still failing")
            return 1
            
    finally:
        await search.close()

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(test_all_fixed_bugs())
    sys.exit(exit_code)
