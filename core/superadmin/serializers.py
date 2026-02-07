from rest_framework import serializers
from hotel.models import Hotel
from django.contrib.auth.models import User


class PartnerSerializer(serializers.ModelSerializer):
    """Serializer for partner user info"""
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']


class PendingHotelSerializer(serializers.ModelSerializer):
    """Serializer for pending hotels in admin verification queue"""
    partner = PartnerSerializer(read_only=True)
    partner_name = serializers.CharField(source='partner.get_full_name', read_only=True)
    partner_email = serializers.CharField(source='partner.email', read_only=True)
    
    class Meta:
        model = Hotel
        fields = [
            'id', 
            'hotel_name',
            'city',
            'country',
            'location',
            'base_price_per_night',
            'number_of_rooms',
            'room_type',
            'description',
            'amenities',
            'images',
            'average_rating',
            'total_ratings',
            'commission_rate',
            'created_at',
            'updated_at',
            'partner',
            'partner_name',
            'partner_email',
            'is_approved',
            'rejection_reason'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'average_rating', 'total_ratings']
