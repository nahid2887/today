from rest_framework import serializers
from .models import Hotel, Booking
from django.contrib.auth.models import User


class HotelSerializer(serializers.ModelSerializer):
    """Serializer for creating and retrieving hotels"""
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    partner_email = serializers.CharField(source='partner.email', read_only=True)
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner', 'partner_name', 'partner_email',
            'hotel_name', 'location', 'city', 'country',
            'number_of_rooms', 'room_type', 'description', 'base_price_per_night',
            'images', 'amenities', 'is_approved', 'average_rating', 'total_ratings',
            'commission_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'partner', 'partner_name', 'partner_email', 
                           'is_approved', 'average_rating', 'total_ratings', 
                           'created_at', 'updated_at']
    
    def create(self, validated_data):
        # Partner is set from request.user in the view
        return super().create(validated_data)


class HotelUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating hotel information"""
    
    class Meta:
        model = Hotel
        fields = [
            'hotel_name', 'location', 'city', 'country',
            'number_of_rooms', 'room_type', 'description', 'base_price_per_night',
            'images', 'amenities', 'commission_rate'
        ]
        extra_kwargs = {
            'hotel_name': {'required': False},
            'location': {'required': False},
            'city': {'required': False},
            'country': {'required': False},
            'base_price_per_night': {'required': False},
        }


class HotelListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing hotels"""
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner_name', 'hotel_name', 'city', 'country',
            'room_type', 'base_price_per_night', 'images',
            'average_rating', 'total_ratings', 'is_approved'
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new bookings with automatic price calculation"""
    
    class Meta:
        model = Booking
        fields = [
            'hotel', 'check_in_date', 'check_out_date', 'number_of_guests',
            'special_perks', 'special_requests'
        ]
    
    def validate(self, data):
        """Validate booking dates and hotel"""
        check_in = data['check_in_date']
        check_out = data['check_out_date']
        hotel = data['hotel']
        
        # Validate dates
        if check_out <= check_in:
            raise serializers.ValidationError("Check-out date must be after check-in date")
        
        # Check if hotel is approved
        if hotel.is_approved != 'approved':
            raise serializers.ValidationError("Hotel is not approved for booking")
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            hotel=hotel,
            status__in=['confirmed', 'pending'],
            check_in_date__lt=check_out,
            check_out_date__gt=check_in
        )
        if overlapping.exists():
            raise serializers.ValidationError("This hotel is not available for the selected dates")
        
        return data
    
    def create(self, validated_data):
        # Get the traveler from request
        traveler = self.context['request'].user
        hotel = validated_data['hotel']
        
        # Create booking with automatic price calculation
        booking = Booking(
            traveler=traveler,
            hotel=hotel,
            check_in_date=validated_data['check_in_date'],
            check_out_date=validated_data['check_out_date'],
            number_of_guests=validated_data['number_of_guests'],
            price_per_night=hotel.base_price_per_night,
            special_perks=validated_data.get('special_perks', []),
            special_requests=validated_data.get('special_requests', '')
        )
        booking.save()  # This will trigger calculate_total_price()
        return booking


class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for listing bookings with hotel details"""
    hotel_name = serializers.CharField(source='hotel.hotel_name', read_only=True)
    hotel_city = serializers.CharField(source='hotel.city', read_only=True)
    traveler_name = serializers.CharField(source='traveler.first_name', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'hotel', 'hotel_name', 'hotel_city', 'traveler_name',
            'check_in_date', 'check_out_date', 'number_of_guests',
            'number_of_nights', 'price_per_night', 'total_price',
            'final_price', 'status', 'created_at'
        ]
        read_only_fields = fields


class BookingDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single booking with all information"""
    hotel_details = HotelListSerializer(source='hotel', read_only=True)
    traveler_name = serializers.CharField(source='traveler.first_name', read_only=True)
    traveler_email = serializers.CharField(source='traveler.email', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'traveler_name', 'traveler_email', 'hotel_details',
            'check_in_date', 'check_out_date', 'number_of_guests',
            'number_of_nights', 'price_per_night', 'total_price',
            'discount_percentage', 'discount_amount', 'final_price',
            'special_perks', 'special_requests', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class BookingUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating booking details (check-in/out dates, guests, requests)"""
    
    class Meta:
        model = Booking
        fields = [
            'check_in_date', 'check_out_date', 'number_of_guests',
            'special_requests'
        ]
    
    def validate(self, data):
        """Validate updated booking dates"""
        check_in = data.get('check_in_date', self.instance.check_in_date)
        check_out = data.get('check_out_date', self.instance.check_out_date)
        
        # Validate dates
        if check_out <= check_in:
            raise serializers.ValidationError("Check-out date must be after check-in date")
        
        # Check for overlapping bookings (excluding current booking)
        hotel = self.instance.hotel
        overlapping = Booking.objects.filter(
            hotel=hotel,
            status__in=['confirmed', 'pending'],
            check_in_date__lt=check_out,
            check_out_date__gt=check_in
        ).exclude(id=self.instance.id)
        
        if overlapping.exists():
            raise serializers.ValidationError("This hotel is not available for the selected dates")
        
        return data
