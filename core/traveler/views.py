from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from traveler.models import FavoriteHotel
from traveler.serializers import FavoriteHotelSerializer
from django.shortcuts import get_object_or_404


class FavoriteHotelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing favorite hotels
    Endpoints:
    - POST /api/favorite-hotels/ - Add a hotel to favorites
    - GET /api/favorite-hotels/ - List all favorite hotels for the current traveler
    - DELETE /api/favorite-hotels/{id}/ - Remove a hotel from favorites
    """
    serializer_class = FavoriteHotelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get favorite hotels for the current traveler"""
        return FavoriteHotel.objects.filter(traveler=self.request.user)

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
