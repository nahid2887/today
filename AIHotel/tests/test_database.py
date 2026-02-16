"""Test database connection and NL-to-SQL system."""
import asyncio
import sys
sys.path.insert(0, '.')

# Import database module directly
import asyncpg


async def test_connection():
    """Test PostgreSQL connection."""
    print("🔌 Testing PostgreSQL Connection...")
    
    try:
        # Connect directly
        conn = await asyncpg.connect(
            host="10.10.13.27",
            port=5433,
            database="hotel_db",
            user="hotel_user",
            password="hotel_pass"
        )
        
        print("✅ Connected successfully!\n")
        
        # Test query
        print("📊 Database Statistics:")
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_hotels,
                AVG(average_rating) as avg_rating,
                COUNT(DISTINCT city) as total_cities,
                MIN(base_price_per_night) as min_price,
                MAX(base_price_per_night) as max_price
            FROM hotel_hotel
            WHERE is_approved = 'approved'
        """)
        
        for key, value in dict(stats).items():
            print(f"  {key}: {value}")
        
        # Get cities
        print("\n🌆 Available Cities:")
        cities = await conn.fetch("""
            SELECT DISTINCT city 
            FROM hotel_hotel 
            WHERE city IS NOT NULL AND city != '' AND is_approved = 'approved'
            ORDER BY city
            LIMIT 20
        """)
        
        city_list = [row['city'] for row in cities]
        print(f"  {', '.join(city_list)}")
        
        # Test Miami query
        print("\n🔍 Testing Query (Miami hotels):")
        hotels = await conn.fetch("""
            SELECT hotel_name, base_price_per_night, average_rating, amenities
            FROM hotel_hotel
            WHERE LOWER(city) = LOWER($1) AND is_approved = 'approved'
            ORDER BY average_rating DESC
            LIMIT 3
        """, "Miami")
        
        for h in hotels:
            price = f"${float(h['base_price_per_night']):.2f}" if h['base_price_per_night'] else "N/A"
            # Handle JSONB amenities (comes as JSON string)
            import json
            amenities_list = json.loads(h['amenities']) if h['amenities'] else []
            amenities = ', '.join(amenities_list[:3]) if amenities_list else 'None'
            print(f"  • {h['hotel_name']}")
            print(f"    Price: {price}/night | Rating: ⭐{h['average_rating']}")
            print(f"    Amenities: {amenities}")
        
        # Test rating filter
        print("\n⭐ Testing Rating Filter (4.5+ rated):")
        high_rated = await conn.fetch("""
            SELECT hotel_name, city, average_rating, total_ratings
            FROM hotel_hotel
            WHERE average_rating >= $1 AND is_approved = 'approved'
            ORDER BY average_rating DESC, total_ratings DESC
            LIMIT 5
        """, 4.5)
        
        for h in high_rated:
            print(f"  • {h['hotel_name']} ({h['city']}) - ⭐{h['average_rating']} ({h['total_ratings']} reviews)")
        
        # Test price filter
        print("\n💰 Testing Price Filter (under $200):")
        budget = await conn.fetch("""
            SELECT hotel_name, city, base_price_per_night, average_rating
            FROM hotel_hotel
            WHERE base_price_per_night <= $1 AND is_approved = 'approved'
            ORDER BY average_rating DESC
            LIMIT 5
        """, 200)
        
        for h in budget:
            price = f"${float(h['base_price_per_night']):.2f}" if h['base_price_per_night'] else "N/A"
            print(f"  • {h['hotel_name']} ({h['city']}) - {price}/night - ⭐{h['average_rating']}")
        
        # Test amenity filter (JSONB contains)
        print("\n🏊 Testing Amenity Filter (with Pool):")
        with_pool = await conn.fetch("""
            SELECT hotel_name, city, average_rating, amenities
            FROM hotel_hotel
            WHERE amenities @> $1::jsonb AND is_approved = 'approved'
            ORDER BY average_rating DESC
            LIMIT 5
        """, '["Pool"]')
        
        for h in with_pool:
            print(f"  • {h['hotel_name']} ({h['city']}) - ⭐{h['average_rating']}")
        
        await conn.close()
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_connection())
