from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Hotel, SpecialOffer
from .serializers import (
    HotelSerializer, HotelUpdateSerializer, HotelListSerializer,
    SpecialOfferSerializer, SpecialOfferListSerializer, HotelDetailSerializer
)


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


class SpecialOfferView(APIView):
    """
    POST: Create a special offer (Partner only, for their hotel)
    GET: List special offers
         - Partners: Get all their hotel's offers
         - Others: Get all active offers for approved hotels
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: SpecialOfferListSerializer(many=True)},
        tags=['Special Offers'],
        description="List special offers - Partners see all their offers, others see active offers"
    )
    def get(self, request):
        user = request.user
        
        # Check if user is a partner
        if hasattr(user, 'partner_profile'):
            # Partner gets all their hotel's offers
            try:
                hotel = Hotel.objects.get(partner=user)
                offers = SpecialOffer.objects.filter(hotel=hotel)
                serializer = SpecialOfferListSerializer(offers, many=True)
                return Response({
                    'message': f'{offers.count()} special offers found',
                    'offers': serializer.data
                }, status=status.HTTP_200_OK)
            except Hotel.DoesNotExist:
                return Response({
                    'message': 'No hotel found. Create your hotel first.',
                    'offers': []
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Others get active offers for approved hotels only
            from django.utils import timezone
            offers = SpecialOffer.objects.filter(
                hotel__is_approved='approved',
                is_active=True,
                valid_until__gte=timezone.now().date()
            )
            serializer = SpecialOfferListSerializer(offers, many=True)
            return Response({
                'message': f'{offers.count()} active special offers found',
                'offers': serializer.data
            }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=SpecialOfferSerializer,
        responses={201: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Create a special offer (Partner only)"
    )
    def post(self, request):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can create special offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found. Create a hotel first.'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SpecialOfferSerializer(data=request.data)
        
        if serializer.is_valid():
            # Set the hotel to the partner's hotel
            offer = serializer.save(hotel=hotel)
            
            return Response({
                'message': 'Special offer created successfully',
                'offer': SpecialOfferSerializer(offer).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SpecialOfferDetailView(APIView):
    """
    GET: Retrieve a specific special offer
    PATCH: Update a special offer (Partner only, their own offers)
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Get a specific special offer by ID"
    )
    def get(self, request, pk):
        try:
            offer = SpecialOffer.objects.get(pk=pk)
            
            # Check permissions
            user = request.user
            if hasattr(user, 'partner_profile'):
                # Partner can view their own offers
                try:
                    hotel = Hotel.objects.get(partner=user)
                    if offer.hotel != hotel:
                        return Response({
                            'error': 'You can only view your own hotel offers'
                        }, status=status.HTTP_403_FORBIDDEN)
                except Hotel.DoesNotExist:
                    return Response({
                        'error': 'No hotel found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # Others can only view active offers for approved hotels
                if not (offer.is_active and offer.hotel.is_approved == 'approved'):
                    return Response({
                        'error': 'Offer not found or not available'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = SpecialOfferSerializer(offer)
            return Response({
                'message': 'Special offer retrieved successfully',
                'offer': serializer.data
            }, status=status.HTTP_200_OK)
            
        except SpecialOffer.DoesNotExist:
            return Response({
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        request=SpecialOfferSerializer,
        responses={200: SpecialOfferSerializer},
        tags=['Special Offers'],
        description="Update a special offer (Partner only)"
    )
    def patch(self, request, pk):
        user = request.user
        
        # Check if user is a partner
        if not hasattr(user, 'partner_profile'):
            return Response({
                'error': 'Only partners can update special offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get partner's hotel
        try:
            hotel = Hotel.objects.get(partner=user)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'No hotel found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get the offer
        try:
            offer = SpecialOffer.objects.get(pk=pk)
        except SpecialOffer.DoesNotExist:
            return Response({
                'error': 'Special offer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify ownership
        if offer.hotel != hotel:
            return Response({
                'error': 'You can only update your own hotel offers'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = SpecialOfferSerializer(offer, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response({
                'message': 'Special offer updated successfully',
                'offer': SpecialOfferSerializer(offer).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HotelDetailView(APIView):
    """
    GET: Retrieve detailed hotel information with special offers
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: HotelDetailSerializer},
        tags=['Hotel'],
        description="Get detailed hotel information including active special offers"
    )
    def get(self, request, pk):
        """
        Get hotel details with active special offers
        Only approved hotels are visible to non-partners
        """
        try:
            hotel = Hotel.objects.get(pk=pk)
            
            # Check if user is the hotel owner or if hotel is approved
            user = request.user
            is_owner = hasattr(user, 'partner_profile') and hotel.partner == user
            
            if not is_owner and hotel.is_approved != 'approved':
                return Response({
                    'error': 'Hotel not found or not available'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = HotelDetailSerializer(hotel)
            return Response({
                'message': 'Hotel details retrieved successfully',
                'hotel': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Hotel.DoesNotExist:
            return Response({
                'error': 'Hotel not found'
            }, status=status.HTTP_404_NOT_FOUND)


