"""
Test Bug Fixes for Priority Issues
"""
import asyncio
import sys
import time
sys.path.insert(0, '.')

from core.integrated_search import IntegratedHotelSearch


async def test_priority_1_price_rating_conflict():
    """
    Priority 1: Test price/rating parsing bug fix
    Query: "hotels under $200 rated 4+"
    Should extract: max_price=200, min_rating=4.0
    Should NOT treat 200 as rating
    """
    print("=" * 80)
    print("🐛 PRIORITY 1: Price/Rating Parsing Bug Fix")
    print("=" * 80)
    
    search = IntegratedHotelSearch(use_vector_ranking=False)
    await search.connect()
    
    test_queries = [
        "hotels under $200 rated 4+",
        "hotels in Miami with pool under $200 rated 4+ with gym and spa",
        "$200 hotels rated 4.5+",
        "rated 4+ hotels under 200 dollars",
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        
        # Extract filters
        filters = search._extract_simple_filters(query)
        
        print(f"   Filters extracted:")
        print(f"      Max Price: {filters.get('max_price')}")
        print(f"      Min Rating: {filters.get('min_rating')}")
        print(f"      Invalid Input: {filters.get('_invalid_input', False)}")
        
        # Try actual search
        results = await search.search(query, limit=5)
        print(f"   ✅ Results: {len(results)} hotels found")
        
        if filters.get('_invalid_input'):
            print(f"   ❌ FAIL: Query marked as invalid: {filters.get('_invalid_reason')}")
        elif filters.get('max_price') == 200 and filters.get('min_rating') == 4.0:
            print(f"   ✅ PASS: Correctly parsed price and rating")
        else:
            print(f"   ⚠️  WARNING: Unexpected filter values")
    
    await search.close()
    print()


async def test_priority_2_negation_support():
    """
    Priority 2: Test negation/exclusion support
    Queries: "hotels not in Miami", "hotels excluding NYC"
    Should exclude specified cities
    """
    print("=" * 80)
    print("🐛 PRIORITY 2: Negation/Exclusion Support")
    print("=" * 80)
    
    search = IntegratedHotelSearch(use_vector_ranking=False)
    await search.connect()
    
    test_queries = [
        ("hotels not in Miami", "Miami"),
        ("hotels excluding New York", "New York"),
        ("hotels without pool", "Pool"),
        ("hotels that don't have gym", "Gym"),
    ]
    
    for query, excluded_item in test_queries:
        print(f"\n📝 Query: '{query}'")
        print(f"   Should exclude: {excluded_item}")
        
        # Extract filters
        filters = search._extract_simple_filters(query)
        
        print(f"   Filters extracted:")
        print(f"      Exclude City: {filters.get('exclude_city')}")
        print(f"      Exclude Amenities: {filters.get('exclude_amenities')}")
        
        # Try actual search
        results = await search.search(query, limit=5)
        print(f"   Results: {len(results)} hotels")
        
        # Verify exclusion worked
        if excluded_item in ["Miami", "New York"]:
            has_excluded = any(
                r.city.lower() == excluded_item.lower() 
                for r in results
            )
            if has_excluded:
                print(f"   ❌ FAIL: Found hotels in excluded city '{excluded_item}'")
                for r in results:
                    print(f"      - {r.hotel_name} in {r.city}")
            else:
                print(f"   ✅ PASS: No hotels from '{excluded_item}'")
                if results:
                    for r in results[:3]:
                        print(f"      - {r.hotel_name} in {r.city}")
        
        elif excluded_item in ["Pool", "Gym"]:
            has_excluded = any(
                excluded_item in r.amenities 
                for r in results
            )
            if has_excluded:
                print(f"   ❌ FAIL: Found hotels with excluded amenity '{excluded_item}'")
            else:
                print(f"   ✅ PASS: No hotels with '{excluded_item}'")
    
    await search.close()
    print()


async def test_priority_3_performance():
    """
    Priority 3: Test performance with embedding cache
    Run same query multiple times - should be faster on 2nd+ runs
    """
    print("=" * 80)
    print("⚡ PRIORITY 3: Performance Optimization (Embedding Cache)")
    print("=" * 80)
    
    search = IntegratedHotelSearch(use_vector_ranking=True)
    await search.connect()
    
    query = "luxury hotels with spa and pool"
    runs = 3
    times = []
    
    print(f"\n📝 Query: '{query}'")
    print(f"   Running {runs} times to test caching...\n")
    
    for i in range(runs):
        start = time.time()
        results = await search.search(query, limit=10)
        elapsed = time.time() - start
        times.append(elapsed)
        
        cache_size = len(search._embedding_cache) if search._embedding_cache else 0
        print(f"   Run {i+1}: {elapsed:.3f}s ({len(results)} hotels, cache: {cache_size} entries)")
    
    print(f"\n   📊 Performance Analysis:")
    print(f"      First run:  {times[0]:.3f}s (cold cache)")
    if len(times) > 1:
        avg_subsequent = sum(times[1:]) / len(times[1:])
        print(f"      Avg cached: {avg_subsequent:.3f}s")
        speedup = (times[0] - avg_subsequent) / times[0] * 100
        print(f"      Speedup:    {speedup:.1f}% faster with cache")
        
        if avg_subsequent < times[0]:
            print(f"   ✅ PASS: Cache improves performance")
        else:
            print(f"   ⚠️  WARNING: No performance improvement detected")
    
    await search.close()
    print()


async def main():
    """Run all bug fix tests."""
    print("\n" + "=" * 80)
    print("🧪 BUG FIX VALIDATION TESTS")
    print("=" * 80)
    print()
    
    # Test each priority fix
    await test_priority_1_price_rating_conflict()
    await test_priority_2_negation_support()
    await test_priority_3_performance()
    
    print("=" * 80)
    print("✅ ALL BUG FIX TESTS COMPLETE")
    print("=" * 80)
    print()


if __name__ == "__main__":
    asyncio.run(main())
