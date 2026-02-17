#!/usr/bin/env python3
"""
Quick test script to verify the fixes.
Tests:
1. Dhaka city search (should find 3 hotels)
2. Price filter without city (should search globally)
"""
import asyncio
from core.integrated_search import IntegratedHotelSearch
import os

async def test_dhaka():
    """Test 1: Dhaka search"""
    print("=" * 60)
    print("TEST 1: Searching for hotels in Dhaka")
    print("=" * 60)
    
    search = IntegratedHotelSearch(use_vector_ranking=False)
    await search.connect()
    
    results, metadata = await search.search(
        query="hotels in dhaka",
        limit=10,
        include_metadata=True
    )
    
    print(f"✓ Found {len(results)} hotels")
    for hotel in results:
        print(f"  - {hotel.hotel_name} (${hotel.base_price_per_night}/night)")
    print()

async def test_price_global():
    """Test 2: Price search without city - should search globally"""
    print("=" * 60)
    print("TEST 2: Hotels over $200 (should search all cities)")
    print("=" * 60)
    
    search = IntegratedHotelSearch(use_vector_ranking=False)
    await search.connect()
    
    results, metadata = await search.search(
        query="hotels over 200 dollars",
        limit=10,
        include_metadata=True
    )
    
    print(f"✓ Found {len(results)} hotels")
    filters = metadata.get('filters', {})
    city_filter = filters.get('city', 'ALL CITIES')
    print(f"  City filter: {city_filter}")
    
    for hotel in results[:5]:
        print(f"  - {hotel.hotel_name} in {hotel.city} (${hotel.base_price_per_night}/night)")
    print()

async def main():
    try:
        await test_dhaka()
        await test_price_global()
        print("=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
