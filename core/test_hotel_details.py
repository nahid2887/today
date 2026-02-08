"""
Test script for Hotel Details API with Special Offers
This endpoint allows travelers to view hotel details along with active special offers
"""

import requests
import json

BASE_URL = "http://0.0.0.0:8000"

# Test credentials - Replace with actual credentials
USER_EMAIL = "traveler@example.com"
USER_PASSWORD = "password123"

def login_user():
    """Login and get JWT token"""
    url = f"{BASE_URL}/api/accounts/login/"
    data = {
        "email": USER_EMAIL,
        "password": USER_PASSWORD
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        token = response.json().get('access')
        print("✓ Login successful")
        return token
    else:
        print(f"✗ Login failed: {response.status_code}")
        print(response.json())
        return None

def get_hotel_details(token, hotel_id):
    """Test getting hotel details with special offers"""
    url = f"{BASE_URL}/api/hotel/{hotel_id}/"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    print(f"\nGET HOTEL DETAILS (ID: {hotel_id})")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    return response.json()

def list_all_hotels(token):
    """Get list of all approved hotels"""
    url = f"{BASE_URL}/api/hotel/"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    print(f"\nLIST ALL HOTELS")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        hotels = response.json().get('hotels', [])
        print(f"Found {len(hotels)} hotels")
        for hotel in hotels:
            print(f"  - ID: {hotel['id']}, Name: {hotel['hotel_name']}, City: {hotel['city']}")
        return hotels
    return []

def main():
    print("=" * 60)
    print("HOTEL DETAILS WITH SPECIAL OFFERS API TEST")
    print("=" * 60)
    
    # Login
    token = login_user()
    if not token:
        print("\n✗ Cannot proceed without authentication token")
        return
    
    # List all hotels to get IDs
    hotels = list_all_hotels(token)
    
    if hotels:
        # Get details of first hotel
        hotel_id = hotels[0]['id']
        hotel_details = get_hotel_details(token, hotel_id)
        
        # Display special offers if any
        if hotel_details.get('hotel'):
            offers = hotel_details['hotel'].get('special_offers', [])
            print(f"\n{'='*60}")
            print(f"SPECIAL OFFERS FOR {hotel_details['hotel']['hotel_name']}")
            print(f"{'='*60}")
            if offers:
                for offer in offers:
                    print(f"\n  Discount: {offer['discount_percentage']}%")
                    print(f"  Valid Until: {offer['valid_until']}")
                    print(f"  Perks: {', '.join(offer['special_perks'])}")
            else:
                print("  No active special offers at this time")
    else:
        print("\n✗ No hotels found. Please create a hotel first.")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    main()
