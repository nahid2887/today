from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Hotel
from .serializers import HotelSerializer, HotelUpdateSerializer, HotelListSerializer


class HotelView(APIView):
    """
    POST: Create a hotel (Partner only, one hotel per partner)
    GET: Retrieve hotel(s)
         - Partners: Get their own hotel
         - Others: Get all approved hotels
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: HotelListSerializer(many=True)},
        tags=['Hotel'],
        description="Get hotels - Partners get their own, others get approved hotels"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if hasattr(user, 'partner_profile'):
            # Partner gets their own hotel
            try:
                hotel = Hotel.objects.get(partner=user)
                serializer = HotelSerializer(hotel)
                return Response({
                    'message': 'Hotel retrieved successfully',
                    'hotel': serializer.data
                }, status=status.HTTP_200_OK)
            except Hotel.DoesNotExist:
                return Response({
                    'message': 'No hotel found. Create your hotel first.',
                    'hotel': None
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Travelers and admins get all approved hotels
            hotels = Hotel.objects.filter(is_approved=True)
            serializer = HotelListSerializer(hotels, many=True)
            return Response({
                'message': f'{hotels.count()} approved hotels found',
                'hotels': serializer.data
            }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=HotelSerializer,
        responses={201: HotelSerializer},
        tags=['Hotel'],
        description="Create a hotel (Partner only, one hotel per partner)"
    )
    def post(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can create hotels'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if partner already has a hotel
        if Hotel.objects.filter(partner=user).exists():
            return Response({
                'error': 'You already have a hotel. Use PATCH to update it.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = HotelSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set the partner to the current user
            hotel = serializer.save(partner=user)
            
            return Response({
                'message': 'Hotel created successfully. Waiting for admin approval.',
                'hotel': HotelSerializer(hotel).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HotelUpdateView(APIView):
    """
    PATCH: Update hotel (Partner can update their own hotel)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request=HotelUpdateSerializer,
        responses={200: HotelSerializer},
        tags=['Hotel'],
        description="Update hotel information (Partner updates their own hotel)"
    )
    def patch(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can update hotels'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found. Create a hotel first.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = HotelUpdateSerializer(hotel, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            # Return full hotel data
            return Response({
                'message': 'Hotel updated successfully',
                'hotel': HotelSerializer(hotel).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
