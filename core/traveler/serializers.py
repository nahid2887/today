from rest_framework import serializers
from traveler.models import FavoriteHotel, HotelRating
from hotel.models import Hotel


class HotelBasicSerializer(serializers.ModelSerializer):
    """Basic Hotel serializer for displaying in favorite list"""
    class Meta:
        model = Hotel
        fields = ['id', 'hotel_name', 'location', 'city', 'country', 'base_price_per_night', 'images', 'amenities']


class FavoriteHotelSerializer(serializers.ModelSerializer):
    """Serializer for Favorite Hotel"""
    hotel = HotelBasicSerializer(read_only=True)
    hotel_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = FavoriteHotel
        fields = ['id', 'hotel', 'hotel_id', 'added_at']
        read_only_fields = ['id', 'added_at']

    def create(self, validated_data):
        """Create a favorite hotel entry"""
        hotel_id = validated_data.pop('hotel_id')
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            raise serializers.ValidationError({"hotel_id": "Hotel not found."})
        
        validated_data['hotel'] = hotel
        return super().create(validated_data)


class HotelRatingSerializer(serializers.ModelSerializer):
    """Serializer for Hotel Rating"""
    hotel_id = serializers.IntegerField(write_only=True)
    hotel_name = serializers.CharField(source='hotel.hotel_name', read_only=True)
    traveler_name = serializers.CharField(source='traveler.username', read_only=True)

    class Meta:
        model = HotelRating
        fields = ['id', 'hotel_id', 'hotel_name', 'rating', 'review', 'traveler_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'traveler_name', 'hotel_name']

    def create(self, validated_data):
        """Create a hotel rating"""
        hotel_id = validated_data.pop('hotel_id')
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            raise serializers.ValidationError({"hotel_id": "Hotel not found."})
        
        validated_data['hotel'] = hotel
        return super().create(validated_data)

    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
