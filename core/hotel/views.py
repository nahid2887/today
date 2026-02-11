from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from .models import Hotel, Booking
from .serializers import (
    HotelSerializer, HotelUpdateSerializer, HotelListSerializer,
    BookingCreateSerializer, BookingListSerializer, BookingDetailSerializer,
    BookingUpdateSerializer
)
from datetime import datetime, timedelta
from django.utils import timezone


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


class BookingCreateView(APIView):
    """
    POST: Create a new hotel booking (Travelers only)
    Automatically calculates price based on hotel price per night and number of nights
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request=BookingCreateSerializer,
        responses={201: BookingDetailSerializer},
        tags=['Hotel Booking'],
        description="Create a new hotel booking with automatic price calculation"
    )
    def post(self, request):
        user = request.user
        
        # Check if user is a traveler
        if not hasattr(user, 'traveler_profile'):
            return Response({
                'error': 'Only travelers can make bookings'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = BookingCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            booking = serializer.save()
            
            return Response({
                'message': 'Booking created successfully',
                'booking': BookingDetailSerializer(booking).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookingListView(APIView):
    """
    GET: List all bookings for the current traveler
    Travelers see their own bookings, admins see all bookings
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='status',
                description='Filter by booking status: pending, confirmed, cancelled, completed',
                required=False,
                type=str,
                enum=['pending', 'confirmed', 'cancelled', 'completed']
            ),
        ],
        responses={200: BookingListSerializer(many=True)},
        tags=['Hotel Booking'],
        description="List bookings - Travelers see their own, admins see all"
    )
    def get(self, request):
        user = request.user
        status_filter = request.query_params.get('status', None)
        
        # Get bookings
        if user.is_superuser or user.is_staff:
            # Admin sees all bookings
            bookings = Booking.objects.all().order_by('-created_at')
        else:
            # Traveler sees only their bookings
            if not hasattr(user, 'traveler_profile'):
                return Response({
                    'error': 'Only travelers can view bookings'
                }, status=status.HTTP_403_FORBIDDEN)
            bookings = Booking.objects.filter(traveler=user).order_by('-created_at')
        
        # Apply status filter
        if status_filter:
            bookings = bookings.filter(status=status_filter)
        
        total_count = bookings.count()
        serializer = BookingListSerializer(bookings, many=True)
        
        return Response({
            'message': f'{total_count} booking(s) found',
            'total_count': total_count,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class BookingDetailView(APIView):
    """
    GET: Retrieve detailed information about a specific booking
    PATCH: Update booking (check-in/out dates, guests, requests) - allowed up to 24 hours before check-in
    DELETE: Cancel booking - allowed up to 24 hours before check-in
    Travelers can view/edit/cancel their own bookings, admins can view all
    """
    permission_classes = [IsAuthenticated]
    
    def check_24_hour_rule(self, booking):
        """Check if booking can be edited/cancelled (24 hours before check-in)"""
        check_in = booking.check_in_date
        now = timezone.now().date()
        
        # Calculate hours until check-in
        time_until_checkin = check_in - now
        
        # If less than 24 hours (1 day), cannot modify
        if time_until_checkin.days < 1:
            return False, f"Cannot modify booking within 24 hours of check-in. Your check-in is on {check_in}"
        
        return True, "OK"
    
    @extend_schema(
        responses={200: BookingDetailSerializer},
        tags=['Hotel Booking'],
        description="Get detailed information about a specific booking"
    )
    def get(self, request, booking_id):
        user = request.user
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permissions
        if not (user.is_superuser or user.is_staff or booking.traveler == user):
            return Response({
                'error': 'You do not have permission to view this booking'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = BookingDetailSerializer(booking)
        
        return Response({
            'message': 'Booking details retrieved successfully',
            'booking': serializer.data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=BookingUpdateSerializer,
        responses={200: BookingDetailSerializer},
        tags=['Hotel Booking'],
        description="Update booking details (check-in/out dates, guests, requests) - allowed up to 24 hours before check-in"
    )
    def patch(self, request, booking_id):
        user = request.user
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is the traveler or admin
        if not (user.is_superuser or user.is_staff or booking.traveler == user):
            return Response({
                'error': 'You do not have permission to edit this booking'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check 24-hour rule
        can_modify, message = self.check_24_hour_rule(booking)
        if not can_modify:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Only traveler can edit their own booking (not admin)
        if not user.is_superuser and not user.is_staff and booking.traveler == user:
            pass  # Allow traveler to edit their booking
        elif user.is_superuser or user.is_staff:
            pass  # Allow admin to edit
        else:
            return Response({
                'error': 'You cannot edit this booking'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = BookingUpdateSerializer(
            booking,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Return updated booking details
            return Response({
                'message': 'Booking updated successfully',
                'booking': BookingDetailSerializer(booking).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        responses={200: OpenApiResponse(description="Booking cancelled successfully")},
        tags=['Hotel Booking'],
        description="Cancel booking - allowed up to 24 hours before check-in"
    )
    def delete(self, request, booking_id):
        user = request.user
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user is the traveler or admin
        if not (user.is_superuser or user.is_staff or booking.traveler == user):
            return Response({
                'error': 'You do not have permission to cancel this booking'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check 24-hour rule
        can_modify, message = self.check_24_hour_rule(booking)
        if not can_modify:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if booking is already cancelled or completed
        if booking.status in ['cancelled', 'completed']:
            return Response({
                'error': f'Cannot cancel a {booking.status} booking'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        booking_id_to_return = booking.id
        hotel_name = booking.hotel.hotel_name
        check_in = booking.check_in_date
        
        # Set status to cancelled instead of deleting
        booking.status = 'cancelled'
        booking.save()
        
        return Response({
            'message': 'Booking cancelled successfully',
            'cancelled_booking': {
                'id': booking_id_to_return,
                'hotel': hotel_name,
                'check_in_date': check_in,
                'status': 'cancelled'
            }
        }, status=status.HTTP_200_OK)
