"""
Test script for Special Offers API endpoints
Run this after creating a partner user and hotel
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://0.0.0.0:8000"

# Test credentials - Replace with actual partner credentials
PARTNER_EMAIL = "partner@example.com"
PARTNER_PASSWORD = "password123"

def login_partner():
    """Login and get JWT token"""
    url = f"{BASE_URL}/api/accounts/login/"
    data = {
        "email": PARTNER_EMAIL,
        "password": PARTNER_PASSWORD
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

def create_special_offer(token):
    """Test creating a special offer"""
    url = f"{BASE_URL}/api/hotel/special-offers/"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Calculate a future date (30 days from now)
    valid_until = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    data = {
        "discount_percentage": 20.00,
        "special_perks": ["Free breakfast", "Late checkout", "Spa credit $50"],
        "valid_until": valid_until,
        "is_active": True
    }
    
    response = requests.post(url, json=data, headers=headers)
    print(f"\n1. CREATE SPECIAL OFFER")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 201:
        return response.json().get('offer', {}).get('id')
    return None

def list_special_offers(token):
    """Test listing special offers"""
    url = f"{BASE_URL}/api/hotel/special-offers/"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    print(f"\n2. LIST SPECIAL OFFERS")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def get_special_offer(token, offer_id):
    """Test getting a specific special offer"""
    url = f"{BASE_URL}/api/hotel/special-offers/{offer_id}/"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    print(f"\n3. GET SPECIFIC OFFER (ID: {offer_id})")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def update_special_offer(token, offer_id):
    """Test updating a special offer"""
    url = f"{BASE_URL}/api/hotel/special-offers/{offer_id}/"
    headers = {"Authorization": f"Bearer {token}"}
    
    data = {
        "discount_percentage": 25.00,
        "special_perks": ["Free breakfast", "Late checkout", "Spa credit $100", "Airport transfer"]
    }
    
    response = requests.patch(url, json=data, headers=headers)
    print(f"\n4. UPDATE SPECIAL OFFER (ID: {offer_id})")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def main():
    print("=" * 60)
    print("SPECIAL OFFERS API TEST")
    print("=" * 60)
    
    # Login
    token = login_partner()
    if not token:
        print("\n✗ Cannot proceed without authentication token")
        return
    
    # Create special offer
    offer_id = create_special_offer(token)
    
    # List all offers
    list_special_offers(token)
    
    if offer_id:
        # Get specific offer
        get_special_offer(token, offer_id)
        
        # Update offer
        update_special_offer(token, offer_id)
        
        # List again to see changes
        print("\n5. LIST OFFERS AFTER UPDATE")
        list_special_offers(token)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    main()
