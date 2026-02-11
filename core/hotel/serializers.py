from rest_framework import serializers
from .models import Hotel, Booking
from django.contrib.auth.models import User


class FlexibleListField(serializers.ListField):
    """Custom ListField that accepts both lists and comma-separated strings"""
    
    def to_internal_value(self, data):
        # Convert string to list if needed (for form-data)
        if isinstance(data, str):
            data = [item.strip() for item in data.split(',') if item.strip()]
        return super().to_internal_value(data)


class HotelSerializer(serializers.ModelSerializer):
    """Serializer for creating and retrieving hotels"""
    
    # Define images and amenities as list fields to handle arrays
    images = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of image URLs/paths"
    )
    amenities = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of amenities"
    )
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'hotel_name', 'location', 'city', 'country',
            'number_of_rooms', 'room_type', 'description', 'base_price_per_night',
            'images', 'amenities', 'is_approved', 'rejection_reason',
            'average_rating', 'total_ratings', 'commission_rate', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_approved', 'rejection_reason',
                           'average_rating', 'total_ratings', 
                           'created_at', 'updated_at']
    
    def validate_images(self, value):
        """Validate images array"""
        # Convert string to list if needed (for form-data)
        if isinstance(value, str):
            value = [img.strip() for img in value.split(',') if img.strip()]
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Images must be an array/list")
        if len(value) > 10:
            raise serializers.ValidationError("Maximum 10 images allowed")
        for img in value:
            if not isinstance(img, str) or len(img.strip()) == 0:
                raise serializers.ValidationError("Each image must be a non-empty string")
        return value
    
    def validate_amenities(self, value):
        """Validate amenities array"""
        # Convert string to list if needed (for form-data)
        if isinstance(value, str):
            value = [amenity.strip() for amenity in value.split(',') if amenity.strip()]
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be an array/list")
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 amenities allowed")
        for amenity in value:
            if not isinstance(amenity, str) or len(amenity.strip()) == 0:
                raise serializers.ValidationError("Each amenity must be a non-empty string")
        return value
    
    def create(self, validated_data):
        # Partner is set from request.user in the view
        return super().create(validated_data)


class HotelUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating hotel information"""
    
    # Define images and amenities as list fields to handle arrays
    images = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of image URLs/paths"
    )
    amenities = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of amenities"
    )
    
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
    
    def validate_images(self, value):
        """Validate images array"""
        # Convert string to list if needed (for form-data)
        if isinstance(value, str):
            value = [img.strip() for img in value.split(',') if img.strip()]
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Images must be an array/list")
        if len(value) > 10:
            raise serializers.ValidationError("Maximum 10 images allowed")
        for img in value:
            if not isinstance(img, str) or len(img.strip()) == 0:
                raise serializers.ValidationError("Each image must be a non-empty string")
        return value
    
    def validate_amenities(self, value):
        """Validate amenities array"""
        # Convert string to list if needed (for form-data)
        if isinstance(value, str):
            value = [amenity.strip() for amenity in value.split(',') if amenity.strip()]
        
        if not isinstance(value, list):
            raise serializers.ValidationError("Amenities must be an array/list")
        if len(value) > 20:
            raise serializers.ValidationError("Maximum 20 amenities allowed")
        for amenity in value:
            if not isinstance(amenity, str) or len(amenity.strip()) == 0:
                raise serializers.ValidationError("Each amenity must be a non-empty string")
        return value
    
    def update(self, instance, validated_data):
        """
        Update hotel and set is_approved back to 'pending' for admin review
        """
        # Update all fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Set is_approved to 'pending' when partner updates their hotel
        instance.is_approved = 'pending'
        instance.save()
        return instance


class HotelListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing hotels"""
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    
    # Define images as list field to handle arrays
    images = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of image URLs/paths"
    )
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner_name', 'hotel_name', 'city', 'country',
            'room_type', 'base_price_per_night', 'images',
            'average_rating', 'total_ratings', 'is_approved'
        ]


<<<<<<< HEAD
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
=======
class SpecialOfferSerializer(serializers.ModelSerializer):
    """Serializer for creating and managing special offers"""
    hotel_name = serializers.CharField(source='hotel.hotel_name', read_only=True)
    
    # Use FlexibleListField for special_perks to handle both JSON and form-data
    special_perks = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of special perks like ['Free breakfast', 'Late checkout', 'Spa credit']"
    )
    
    class Meta:
        model = Hotel.special_offers.rel.related_model  # SpecialOffer model
        fields = [
            'id', 'hotel', 'hotel_name', 'discount_percentage', 
            'special_perks', 'valid_until', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'hotel', 'hotel_name', 'created_at', 'updated_at']
    
    def validate_discount_percentage(self, value):
        """Ensure discount is between 1 and 100"""
        if value < 1 or value > 100:
            raise serializers.ValidationError("Discount percentage must be between 1 and 100")
        return value
    
    def validate_valid_until(self, value):
        """Ensure valid_until is a future date"""
        from django.utils import timezone
        if value < timezone.now().date():
            raise serializers.ValidationError("Valid until date must be in the future")
        return value


class SpecialOfferListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing special offers"""
    hotel_name = serializers.CharField(source='hotel.hotel_name', read_only=True)
    
    # Use FlexibleListField for special_perks to handle both JSON and form-data
    special_perks = FlexibleListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Array of special perks"
    )
    
    class Meta:
        model = Hotel.special_offers.rel.related_model  # SpecialOffer model
        fields = [
            'id', 'hotel_name', 'discount_percentage', 
            'special_perks', 'valid_until', 'is_active'
        ]


class HotelBulkSyncSerializer(serializers.ModelSerializer):
    """
    Serializer for Bulk Sync endpoint - RAG system data.
    Includes all static hotel information needed for embeddings.
    """
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    last_updated = serializers.SerializerMethodField()
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner_name', 'hotel_name', 'description', 
            'location', 'city', 'country', 
            'amenities', 'images', 'room_type',
            'number_of_rooms', 'average_rating', 'total_ratings',
            'last_updated'
        ]
    
    def get_last_updated(self, obj):
        """Return the latest update timestamp"""
        return obj.updated_at.isoformat()


class HotelRealTimeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Real-Time Detail endpoint - AI verification.
    Includes dynamic data that changes frequently.
    """
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    active_special_offers = serializers.SerializerMethodField()
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner_name', 'hotel_name',
            'base_price_per_night', 'commission_rate',
            'active_special_offers', 'is_approved',
            'updated_at'
        ]
        read_only_fields = ['id', 'partner_name', 'hotel_name', 
                           'base_price_per_night', 'commission_rate', 
                           'is_approved', 'updated_at']
    
    def get_active_special_offers(self, obj):
        """Get only active and valid special offers"""
        from django.utils import timezone
        offers = obj.special_offers.filter(
            is_active=True,
            valid_until__gte=timezone.now().date()
        )
        return [
            {
                'discount_percentage': float(offer.discount_percentage),
                'special_perks': offer.special_perks,
                'valid_until': offer.valid_until.isoformat()
            }
            for offer in offers
        ]


class HotelDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for hotel with special offers"""
    partner_name = serializers.CharField(source='partner.username', read_only=True)
    partner_email = serializers.CharField(source='partner.email', read_only=True)
    special_offers = serializers.SerializerMethodField()
    
    class Meta:
        model = Hotel
        fields = [
            'id', 'partner_name', 'partner_email',
            'hotel_name', 'location', 'city', 'country',
            'number_of_rooms', 'room_type', 'description', 'base_price_per_night',
            'images', 'amenities', 'is_approved', 'average_rating', 'total_ratings',
            'commission_rate', 'created_at', 'updated_at', 'special_offers'
        ]
    
    def get_special_offers(self, obj):
        """Get only active and valid special offers"""
        from django.utils import timezone
        offers = obj.special_offers.filter(
            is_active=True,
            valid_until__gte=timezone.now().date()
        )
        return SpecialOfferListSerializer(offers, many=True).data


>>>>>>> 25b4413610ab56532672901829a009d3cea036ca
