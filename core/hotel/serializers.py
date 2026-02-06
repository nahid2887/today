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
