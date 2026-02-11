"""
Script to create test approved hotels for testing the superadmin approved hotels API
"""
from django.contrib.auth.models import User
from hotel.models import Hotel
from accounts.models import PartnerProfile

# Get or create a partner user
try:
    partner = PartnerProfile.objects.first()
    if not partner:
        print("No partner found. Creating a test partner...")
        user = User.objects.create_user(
            username='testpartner',
            email='partner@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Partner'
        )
        partner = PartnerProfile.objects.create(
            user=user,
            phone_number='+1234567890',
            business_name='Test Hotel Business'
        )
    else:
        user = partner.user
    
    print(f"Using partner: {user.username} ({user.email})")
    
    # Check if partner already has a hotel
    existing_hotel = Hotel.objects.filter(partner=user).first()
    if existing_hotel:
        print(f"\nPartner already has a hotel: {existing_hotel.hotel_name}")
        print(f"Current status: {existing_hotel.is_approved}")
        
        # Approve it if not already approved
        if existing_hotel.is_approved != 'approved':
            existing_hotel.is_approved = 'approved'
            existing_hotel.save()
            print(f"✅ Hotel '{existing_hotel.hotel_name}' has been APPROVED!")
        else:
            print(f"✅ Hotel is already approved")
    else:
        # Create a new hotel
        hotel = Hotel.objects.create(
            partner=user,
            hotel_name='Grand Paradise Resort',
            location='123 Beach Boulevard, Miami Beach',
            city='Miami',
            country='USA',
            number_of_rooms=150,
            room_type='deluxe',
            description='Luxury beachfront resort with stunning ocean views, world-class amenities, and exceptional service.',
            base_price_per_night=299.99,
            images=['hotel1.jpg', 'hotel2.jpg', 'hotel3.jpg'],
            amenities=['Free WiFi', 'Swimming Pool', 'Gym', 'Restaurant', 'Spa', 'Beach Access', 'Room Service'],
            commission_rate=5.00,
            is_approved='approved',  # Directly approve it
            average_rating=4.75,
            total_ratings=250
        )
        print(f"\n✅ Created and APPROVED hotel: {hotel.hotel_name}")
    
    # Show statistics
    total_hotels = Hotel.objects.count()
    approved_hotels = Hotel.objects.filter(is_approved='approved').count()
    pending_hotels = Hotel.objects.filter(is_approved='pending').count()
    
    print(f"\n📊 Database Statistics:")
    print(f"   Total hotels: {total_hotels}")
    print(f"   Approved hotels: {approved_hotels}")
    print(f"   Pending hotels: {pending_hotels}")
    
    print(f"\n✅ You can now test the API at: http://localhost:8000/api/superadmin/approved-hotels/")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
