from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from traveler.models import FavoriteHotel, HotelRating
from traveler.serializers import FavoriteHotelSerializer, HotelRatingSerializer
from hotel.models import Hotel
from django.shortcuts import get_object_or_404


class FavoriteHotelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing favorite hotels
    Endpoints:
    - POST /api/traveler/favorite-hotels/ - Add a hotel to favorites
    - GET /api/traveler/favorite-hotels/ - List all favorite hotels for the current traveler
    - DELETE /api/traveler/favorite-hotels/{id}/ - Remove a hotel from favorites
    """
    serializer_class = FavoriteHotelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get favorite hotels for the current traveler"""
        return FavoriteHotel.objects.filter(traveler=self.request.user)
    
    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Add a hotel to favorites"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if already in favorites
        hotel_id = request.data.get('hotel_id')
        existing = FavoriteHotel.objects.filter(
            traveler=request.user,
            hotel_id=hotel_id
        ).first()
        
        if existing:
            return Response(
                {"detail": "This hotel is already in your favorites."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add traveler to the serializer
        serializer.validated_data['traveler'] = request.user
        self.perform_create(serializer)
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        """Remove a hotel from favorites"""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": "Hotel removed from favorites."},
            status=status.HTTP_204_NO_CONTENT
        )


class HotelRatingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing hotel ratings
    Endpoint:
    - POST /api/traveler/hotel-ratings/ - Submit/update hotel rating
    """
    serializer_class = HotelRatingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get ratings submitted by the current traveler"""
        return HotelRating.objects.filter(traveler=self.request.user)

    def create(self, request, *args, **kwargs):
        """Submit or update a hotel rating"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        hotel_id = request.data.get('hotel_id')
        rating_value = float(request.data.get('rating', 0))
        
        # Validate hotel exists
        try:
            hotel = Hotel.objects.get(id=hotel_id)
        except Hotel.DoesNotExist:
            return Response(
                {"detail": "Hotel not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if traveler already rated this hotel
        existing_rating = HotelRating.objects.filter(
            traveler=request.user,
            hotel_id=hotel_id
        ).first()
        
        if existing_rating:
            # Update existing rating
            old_rating = float(existing_rating.rating)
            existing_rating.rating = rating_value
            existing_rating.review = request.data.get('review', existing_rating.review)
            existing_rating.save()
            
            # Recalculate hotel rating
            all_ratings = HotelRating.objects.filter(hotel=hotel)
            if all_ratings.exists():
                total_sum = sum(float(r.rating) for r in all_ratings)
                hotel.average_rating = round(total_sum / all_ratings.count(), 2)
                hotel.total_ratings = all_ratings.count()
                hotel.save()
            
            return Response(
                {
                    "detail": "Rating updated successfully.",
                    "rating": HotelRatingSerializer(existing_rating).data,
                    "hotel_new_average_rating": float(hotel.average_rating)
                },
                status=status.HTTP_200_OK
            )
        
        # Create new rating
        serializer.validated_data['traveler'] = request.user
        new_rating = serializer.save()
        
        # Update hotel rating
        hotel.update_rating(rating_value)
        
        return Response(
            {
                "detail": "Rating submitted successfully.",
                "rating": HotelRatingSerializer(new_rating).data,
                "hotel_new_average_rating": float(hotel.average_rating)
            },
            status=status.HTTP_201_CREATED
        )
