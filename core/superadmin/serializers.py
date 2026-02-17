from rest_framework import serializers
from hotel.models import Hotel
from django.contrib.auth.models import User


class PartnerSerializer(serializers.ModelSerializer):
    """Serializer for partner user info"""
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email']


class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for admin/superadmin profile"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'is_staff',
            'is_superuser',
            'date_joined'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'is_staff', 'is_superuser']
    
    def get_full_name(self, obj):
        """Get full name from first_name and last_name"""
        if obj.first_name and obj.last_name:
            return f"{obj.first_name} {obj.last_name}"
        return obj.username


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating admin profile"""
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']
    
    def update(self, instance, validated_data):
        """Update user profile"""
        instance.email = validated_data.get('email', instance.email)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()
        return instance


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
