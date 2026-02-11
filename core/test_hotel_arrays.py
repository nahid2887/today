"""
Test script to demonstrate sending images and amenities as arrays to the Hotel API
"""

import requests
import json

# API Base URL
BASE_URL = "http://localhost:8000/api"

def test_hotel_array_data():
    """Test creating and updating hotel with array data for images and amenities"""
    
    # Step 1: Get authentication token
    print("=" * 60)
    print("STEP 1: Getting Authentication Token")
    print("=" * 60)
    
    login_data = {
        "username": "partner1",  # Use an existing partner account
        "password": "your_password"  # Replace with actual password
    }
    
    token_response = requests.post(
        f"{BASE_URL}/token/",
        data=login_data
    )
    
    if token_response.status_code != 200:
        print(f"Login failed: {token_response.text}")
        return
    
    token = token_response.json().get('access')
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print(f"✓ Token obtained: {token[:20]}...")
    
    # Step 2: Update hotel with array data
    print("\n" + "=" * 60)
    print("STEP 2: Updating Hotel with Arrays of Images and Amenities")
    print("=" * 60)
    
    hotel_update_data = {
        "hotel_name": "Luxury Grand Hotel",
        "location": "123 Main Street, Downtown",
        "city": "New York",
        "country": "USA",
        "number_of_rooms": 150,
        "room_type": "deluxe",
        "description": "A world-class luxury hotel with premium amenities",
        "base_price_per_night": 250.00,
        "commission_rate": 5.5,
        "images": [
            "https://example.com/images/hotel_exterior.jpg",
            "https://example.com/images/hotel_lobby.jpg",
            "https://example.com/images/hotel_room.jpg",
            "https://example.com/images/hotel_restaurant.jpg",
            "https://example.com/images/hotel_pool.jpg"
        ],
        "amenities": [
            "Free WiFi",
            "Swimming Pool",
            "Gym & Fitness Center",
            "Restaurant",
            "Bar & Lounge",
            "Room Service",
            "Concierge",
            "Spa & Massage",
            "Conference Halls",
            "Parking Available"
        ]
    }
    
    print("\nSending hotel update request with:")
    print(f"  - {len(hotel_update_data['images'])} images")
    print(f"  - {len(hotel_update_data['amenities'])} amenities")
    print("\nImages:")
    for img in hotel_update_data['images']:
        print(f"  • {img}")
    print("\nAmenities:")
    for amenity in hotel_update_data['amenities']:
        print(f"  • {amenity}")
    
    update_response = requests.patch(
        f"{BASE_URL}/hotel/",
        headers=headers,
        json=hotel_update_data
    )
    
    print(f"\nResponse Status: {update_response.status_code}")
    
    if update_response.status_code == 200:
        print("✓ Hotel updated successfully!")
        hotel_data = update_response.json()['hotel']
        
        print("\nUpdated Hotel Data:")
        print(f"  Hotel Name: {hotel_data['hotel_name']}")
        print(f"  Location: {hotel_data['location']}")
        print(f"  City: {hotel_data['city']}")
        print(f"  Country: {hotel_data['country']}")
        print(f"  Base Price: ${hotel_data['base_price_per_night']}")
        
        print(f"\n  Images ({len(hotel_data['images'])}):")
        for img in hotel_data['images']:
            print(f"    • {img}")
        
        print(f"\n  Amenities ({len(hotel_data['amenities'])}):")
        for amenity in hotel_data['amenities']:
            print(f"    • {amenity}")
    else:
        print(f"✗ Update failed: {update_response.text}")
        return
    
    # Step 3: Retrieve hotel and verify array data
    print("\n" + "=" * 60)
    print("STEP 3: Retrieving Hotel to Verify Array Data")
    print("=" * 60)
    
    get_response = requests.get(
        f"{BASE_URL}/hotel/",
        headers=headers
    )
    
    if get_response.status_code == 200:
        print("✓ Hotel retrieved successfully!")
        hotel_data = get_response.json()['hotel']
        
        print(f"\nRetrieved Images: {len(hotel_data['images'])} total")
        for i, img in enumerate(hotel_data['images'], 1):
            print(f"  {i}. {img}")
        
        print(f"\nRetrieved Amenities: {len(hotel_data['amenities'])} total")
        for i, amenity in enumerate(hotel_data['amenities'], 1):
            print(f"  {i}. {amenity}")
    else:
        print(f"✗ Retrieval failed: {get_response.text}")
    
    # Step 4: Test validation with invalid data
    print("\n" + "=" * 60)
    print("STEP 4: Testing Validation with Invalid Array Data")
    print("=" * 60)
    
    # Test 1: Too many images
    print("\nTest 1: Sending too many images (should fail)")
    invalid_data = {
        "images": [f"image{i}.jpg" for i in range(15)]  # More than 10 allowed
    }
    
    response = requests.patch(
        f"{BASE_URL}/hotel/",
        headers=headers,
        json=invalid_data
    )
    
    if response.status_code != 200:
        print(f"✓ Validation correctly rejected: {response.json()}")
    else:
        print("✗ Validation should have failed")
    
    # Test 2: Empty array
    print("\nTest 2: Sending empty amenities array (should pass)")
    valid_data = {
        "amenities": []  # Empty array is allowed
    }
    
    response = requests.patch(
        f"{BASE_URL}/hotel/",
        headers=headers,
        json=valid_data
    )
    
    if response.status_code == 200:
        print(f"✓ Empty arrays are accepted")
    else:
        print(f"✗ Failed: {response.json()}")
    
    print("\n" + "=" * 60)
    print("✓ All tests completed!")
    print("=" * 60)


def example_curl_commands():
    """Print example curl commands for testing"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE CURL COMMANDS")
    print("=" * 60)
    
    print("\n1. Get token:")
    print("""
    curl -X POST http://localhost:8000/api/token/ \\
      -H "Content-Type: application/json" \\
      -d '{"username":"partner1","password":"password"}'
    """)
    
    print("\n2. Update hotel with images and amenities arrays:")
    print("""
    curl -X PATCH http://localhost:8000/api/hotel/ \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "images": [
          "https://example.com/image1.jpg",
          "https://example.com/image2.jpg"
        ],
        "amenities": [
          "Free WiFi",
          "Swimming Pool",
          "Gym"
        ]
      }'
    """)
    
    print("\n3. Get hotel (includes arrays):")
    print("""
    curl -X GET http://localhost:8000/api/hotel/ \\
      -H "Authorization: Bearer YOUR_TOKEN"
    """)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("HOTEL API - ARRAY DATA TESTING")
    print("=" * 60)
    
    print("\nNote: Ensure Django server is running on http://localhost:8000")
    print("and you have a partner account created.")
    
    # Uncomment to run tests (requires running server)
    # test_hotel_array_data()
    
    # Show example curl commands
    example_curl_commands()
