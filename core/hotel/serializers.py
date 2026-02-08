from rest_framework import serializers
from .models import Hotel
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


class SpecialOfferSerializer(serializers.ModelSerializer):
    """Serializer for creating and managing special offers"""
    hotel_name = serializers.CharField(source='hotel.hotel_name', read_only=True)
    
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
    
    class Meta:
        model = Hotel.special_offers.rel.related_model  # SpecialOffer model
        fields = [
            'id', 'hotel_name', 'discount_percentage', 
            'special_perks', 'valid_until', 'is_active'
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


