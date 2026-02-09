from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import PartnerProfile
from hotel.models import Hotel, SpecialOffer
from datetime import timedelta
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Populate database with 20 fake approved partner and hotel records'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to populate database with fake data...'))
        
        hotel_data = [
            {
                'name': 'Grand Plaza Hotel',
                'location': '123 Main St, Downtown',
                'city': 'New York',
                'country': 'USA',
                'description': 'Luxury 5-star hotel in the heart of Manhattan with world-class amenities.',
                'price': 250.00,
                'amenities': ['Free WiFi', 'Pool', 'Gym', 'Restaurant', 'Bar', 'Spa'],
                'rooms': 150,
                'room_type': 'suite'
            },
            {
                'name': 'Sunset Beach Resort',
                'location': '456 Beach Blvd, Coastal Area',
                'city': 'Miami',
                'country': 'USA',
                'description': 'Beautiful beachfront resort with stunning ocean views and water sports.',
                'price': 180.00,
                'amenities': ['Beach Access', 'Pool', 'Water Sports', 'Restaurant', 'Bar'],
                'rooms': 200,
                'room_type': 'deluxe'
            },
            {
                'name': 'Mountain View Lodge',
                'location': '789 Alpine Drive',
                'city': 'Denver',
                'country': 'USA',
                'description': 'Cozy mountain lodge perfect for outdoor enthusiasts and nature lovers.',
                'price': 120.00,
                'amenities': ['Hiking', 'Fireplace', 'Restaurant', 'Ski Access', 'Hot Tub'],
                'rooms': 80,
                'room_type': 'standard'
            },
            {
                'name': 'Historic Downtown Inn',
                'location': '321 Heritage Lane',
                'city': 'Boston',
                'country': 'USA',
                'description': 'Charming historic hotel with colonial architecture and modern comfort.',
                'price': 140.00,
                'amenities': ['WiFi', 'Restaurant', 'Bar', 'Meeting Rooms', 'Parking'],
                'rooms': 120,
                'room_type': 'deluxe'
            },
            {
                'name': 'Tech Park Hotel',
                'location': '999 Silicon Valley Road',
                'city': 'San Francisco',
                'country': 'USA',
                'description': 'Modern business hotel with high-speed internet and business center.',
                'price': 200.00,
                'amenities': ['High-Speed WiFi', 'Business Center', 'Gym', 'Restaurant', 'Conference Rooms'],
                'rooms': 175,
                'room_type': 'suite'
            },
            {
                'name': 'Garden Boutique Hotel',
                'location': '555 Flower Street',
                'city': 'Portland',
                'country': 'USA',
                'description': 'Intimate boutique hotel with beautiful gardens and personalized service.',
                'price': 130.00,
                'amenities': ['Gardens', 'WiFi', 'Restaurant', 'Bar', 'Spa'],
                'rooms': 60,
                'room_type': 'deluxe'
            },
            {
                'name': 'Desert Oasis Resort',
                'location': '777 Sand Dune Road',
                'city': 'Phoenix',
                'country': 'USA',
                'description': 'Luxurious desert resort with golf course and spa facilities.',
                'price': 210.00,
                'amenities': ['Golf Course', 'Spa', 'Pool', 'Restaurant', 'Bar', 'Tennis Courts'],
                'rooms': 250,
                'room_type': 'presidential'
            },
            {
                'name': 'Urban Loft Hotel',
                'location': '222 Arts District',
                'city': 'Los Angeles',
                'country': 'USA',
                'description': 'Trendy urban hotel in the Arts District with rooftop lounge.',
                'price': 170.00,
                'amenities': ['Rooftop Lounge', 'WiFi', 'Gym', 'Restaurant', 'Art Gallery'],
                'rooms': 140,
                'room_type': 'deluxe'
            },
            {
                'name': 'Waterfront Mansion Hotel',
                'location': '888 Harbor View Drive',
                'city': 'San Diego',
                'country': 'USA',
                'description': 'Elegant waterfront hotel with private beach and yacht club access.',
                'price': 230.00,
                'amenities': ['Private Beach', 'Yacht Club', 'Pool', 'Restaurant', 'Spa', 'Marina'],
                'rooms': 160,
                'room_type': 'suite'
            },
            {
                'name': 'Campus Hotel',
                'location': '444 University Avenue',
                'city': 'Chicago',
                'country': 'USA',
                'description': 'Contemporary hotel near universities and cultural attractions.',
                'price': 110.00,
                'amenities': ['WiFi', 'Restaurant', 'Gym', 'Library', 'Study Lounge'],
                'rooms': 100,
                'room_type': 'standard'
            },
            {
                'name': 'Caribbean Escape Resort',
                'location': '333 Tropical Lane',
                'city': 'Miami Beach',
                'country': 'USA',
                'description': 'Tropical paradise with all-inclusive amenities and water activities.',
                'price': 190.00,
                'amenities': ['All-Inclusive', 'Beach', 'Water Sports', 'Pool', 'Restaurant', 'Bar'],
                'rooms': 220,
                'room_type': 'deluxe'
            },
            {
                'name': 'Historic Castle Inn',
                'location': '111 Medieval Street',
                'city': 'Philadelphia',
                'country': 'USA',
                'description': 'Unique castle-themed hotel with period furniture and historical charm.',
                'price': 135.00,
                'amenities': ['Historic Tours', 'Restaurant', 'Bar', 'WiFi', 'Events'],
                'rooms': 75,
                'room_type': 'deluxe'
            },
            {
                'name': 'Lakeside Cottage Resort',
                'location': '666 Lake Shore Drive',
                'city': 'Seattle',
                'country': 'USA',
                'description': 'Peaceful lakeside cottages with nature trails and fishing facilities.',
                'price': 125.00,
                'amenities': ['Lake Access', 'Fishing', 'Hiking Trails', 'Restaurant', 'Cabins'],
                'rooms': 90,
                'room_type': 'standard'
            },
            {
                'name': 'Downtown Metroplex',
                'location': '999 Business Plaza',
                'city': 'Houston',
                'country': 'USA',
                'description': 'Large business hotel with multiple restaurants and convention facilities.',
                'price': 155.00,
                'amenities': ['Convention Center', 'Multiple Restaurants', 'Gym', 'Pool', 'Parking'],
                'rooms': 300,
                'room_type': 'suite'
            },
            {
                'name': 'Vineyard Estate Hotel',
                'location': '555 Wine Country Road',
                'city': 'Napa Valley',
                'country': 'USA',
                'description': 'Elegant hotel on vineyard grounds with wine tasting and tours.',
                'price': 195.00,
                'amenities': ['Wine Tasting', 'Vineyard Tours', 'Spa', 'Restaurant', 'Bar'],
                'rooms': 110,
                'room_type': 'deluxe'
            },
            {
                'name': 'Historic French Quarter Inn',
                'location': '888 Bourbon Street',
                'city': 'New Orleans',
                'country': 'USA',
                'description': 'Charming French Quarter hotel with balconies and live music venue.',
                'price': 150.00,
                'amenities': ['Live Music', 'Balconies', 'Restaurant', 'Bar', 'Historical Tours'],
                'rooms': 95,
                'room_type': 'deluxe'
            },
            {
                'name': 'Mountain Peak Resort',
                'location': '222 Summit Ridge Road',
                'city': 'Aspen',
                'country': 'USA',
                'description': 'Premium ski resort with luxury accommodations and après-ski activities.',
                'price': 300.00,
                'amenities': ['Ski Access', 'Hot Tub', 'Restaurant', 'Bar', 'Spa', 'Fireplace'],
                'rooms': 130,
                'room_type': 'presidential'
            },
            {
                'name': 'Corporate Suites Building',
                'location': '777 Commerce Drive',
                'city': 'Dallas',
                'country': 'USA',
                'description': 'Extended stay hotel perfect for business travelers with full kitchens.',
                'price': 120.00,
                'amenities': ['Full Kitchen', 'Laundry', 'WiFi', 'Gym', 'Market'],
                'rooms': 180,
                'room_type': 'suite'
            },
            {
                'name': 'Artist Lofts Hotel',
                'location': '333 Creative Boulevard',
                'city': 'Nashville',
                'country': 'USA',
                'description': 'Eclectic artist-themed hotel with live performances and art gallery.',
                'price': 125.00,
                'amenities': ['Live Performances', 'Art Gallery', 'Restaurant', 'Music Lounge', 'WiFi'],
                'rooms': 85,
                'room_type': 'deluxe'
            },
            {
                'name': 'Lakefront Grand Hotel',
                'location': '444 Water View Drive',
                'city': 'Minneapolis',
                'country': 'USA',
                'description': 'Grand hotel on the lake with scenic views and water activities.',
                'price': 160.00,
                'amenities': ['Lake View', 'Water Sports', 'Restaurant', 'Gym', 'Spa'],
                'rooms': 200,
                'room_type': 'suite'
            }
        ]
        
        created_count = 0
        
        for i, hotel_info in enumerate(hotel_data, 1):
            # Create partner user
            username = f'partner_{i}'
            email = f'partner{i}@example.com'
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(f'User {username} already exists, skipping...')
                continue
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='testpass123',
                first_name=f'Partner{i}',
                last_name='User'
            )
            
            # Create partner profile
            partner_profile = PartnerProfile.objects.create(
                user=user,
                property_name=hotel_info['name'],
                property_address=hotel_info['location'],
                contact_person_name=f'Manager {i}',
                phone_number=f'+1-555-{1000+i:04d}',
                role='owner'
            )
            
            # Get or create hotel (signal should create it, but we'll get it)
            hotel = Hotel.objects.get(partner=user)
            
            # Update hotel with detailed information and set as approved
            hotel.hotel_name = hotel_info['name']
            hotel.location = hotel_info['location']
            hotel.city = hotel_info['city']
            hotel.country = hotel_info['country']
            hotel.description = hotel_info['description']
            hotel.base_price_per_night = hotel_info['price']
            hotel.number_of_rooms = hotel_info['rooms']
            hotel.room_type = hotel_info['room_type']
            hotel.amenities = hotel_info['amenities']
            hotel.is_approved = 'approved'  # Set as approved
            hotel.average_rating = round(random.uniform(3.5, 5.0), 2)
            hotel.total_ratings = random.randint(10, 500)
            hotel.commission_rate = round(random.uniform(2.0, 8.0), 2)
            hotel.save()
            
            # Create 1-3 special offers for each hotel
            num_offers = random.randint(1, 3)
            for j in range(num_offers):
                discount = random.choice([10, 15, 20, 25, 30])
                valid_until = timezone.now().date() + timedelta(days=random.randint(30, 180))
                
                perks = random.choice([
                    ['Free breakfast', 'Late checkout'],
                    ['Free parking', 'Spa credit $50'],
                    ['Free airport transfer', 'Room upgrade'],
                    ['Complimentary WiFi', 'Happy hour drinks'],
                    ['Free fitness center', 'Free coffee'],
                ])
                
                SpecialOffer.objects.create(
                    hotel=hotel,
                    discount_percentage=discount,
                    special_perks=perks,
                    valid_until=valid_until,
                    is_active=True
                )
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created partner {username} with hotel "{hotel_info["name"]}" (Approved)'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully created {created_count} fake partners and approved hotels!'
        ))
