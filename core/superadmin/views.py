from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Avg
from hotel.models import Hotel, Booking, Notification
from .serializers import PendingHotelSerializer, AdminProfileSerializer, AdminProfileUpdateSerializer
from drf_spectacular.utils import extend_schema
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime


class HotelVerificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Admin to verify and manage hotel applications
    """
    serializer_class = PendingHotelSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return hotels based on approval status"""
        status_filter = self.request.query_params.get('status', 'pending')
        
        if status_filter == 'pending':
            return Hotel.objects.filter(is_approved='pending').order_by('-created_at')
        elif status_filter == 'approved':
            return Hotel.objects.filter(is_approved='approved').order_by('-created_at')
        elif status_filter == 'rejected':
            return Hotel.objects.filter(is_approved='rejected').order_by('-created_at')
        else:
            return Hotel.objects.all().order_by('-created_at')
    
    @extend_schema(
        description="Get hotel verification queue with count",
        parameters=[
            {
                'name': 'status',
                'in': 'query',
                'description': 'Filter by approval status: pending, approved, rejected',
                'schema': {'type': 'string', 'default': 'pending'}
            }
        ]
    )
    def list(self, request, *args, **kwargs):
        """
        List hotels with verification status and count
        Query params:
            - status: 'pending', 'approved', 'rejected' (default: pending)
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        hotels_data = serializer.data
        
        # Convert image paths to full URLs
        base_url = request.build_absolute_uri('/').rstrip('/')
        for hotel in hotels_data:
            if 'images' in hotel and hotel['images']:
                hotel['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel['images']]
        
        # Get recently verified/approved hotels (last 5)
        recently_approved = Hotel.objects.filter(is_approved='approved').order_by('-updated_at')[:5]
        recently_approved_serializer = self.get_serializer(recently_approved, many=True)
        recently_approved_data = recently_approved_serializer.data
        
        # Convert image paths to full URLs for recently approved
        for hotel in recently_approved_data:
            if 'images' in hotel and hotel['images']:
                hotel['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel['images']]
        
        return Response({
            'count': queryset.count(),
            'status': request.query_params.get('status', 'pending'),
            'results': hotels_data,
            'recently_verified': {
                'count': len(recently_approved_data),
                'hotels': recently_approved_data
            }
        })
    
    @extend_schema(description="Get detailed hotel information")
    def retrieve(self, request, *args, **kwargs):
        """Get detailed hotel information"""
        response = super().retrieve(request, *args, **kwargs)
        
        # Convert image paths to full URLs
        if response.data and 'images' in response.data and response.data['images']:
            base_url = request.build_absolute_uri('/').rstrip('/')
            response.data['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in response.data['images']]
        
        return response
    
    def send_websocket_notification(self, user_id, notification_type, hotel_id, hotel_name, status, reason=None, message=None):
        """
        Send WebSocket notification to partner
        """
        channel_layer = get_channel_layer()
        room_group_name = f'partner_{user_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'hotel_notification',
                'notification_type': notification_type,
                'hotel_id': hotel_id,
                'hotel_name': hotel_name,
                'status': status,
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
                'message': message or f'Hotel {notification_type}: {hotel_name}'
            }
        )
    
    @extend_schema(description="Approve a hotel")
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a pending hotel"""
        hotel = self.get_object()
        hotel.is_approved = 'approved'
        hotel.save()
        
        # Create database notification
        Notification.objects.create(
            user=hotel.partner,
            hotel=hotel,
            notification_type='hotel_approved',
            title='Hotel Approved',
            message=f'Your hotel "{hotel.hotel_name}" has been approved!',
            data={'hotel_id': hotel.id, 'hotel_name': hotel.hotel_name}
        )
        
        # Send WebSocket notification
        self.send_websocket_notification(
            user_id=hotel.partner.id,
            notification_type='hotel_approved',
            hotel_id=hotel.id,
            hotel_name=hotel.hotel_name,
            status='approved',
            message=f'Your hotel "{hotel.hotel_name}" has been approved!'
        )
        
        serializer = self.get_serializer(hotel)
        hotel_data = serializer.data
        
        # Convert image paths to full URLs
        if 'images' in hotel_data and hotel_data['images']:
            base_url = request.build_absolute_uri('/').rstrip('/')
            hotel_data['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel_data['images']]
        
        return Response({
            'message': 'Hotel approved successfully',
            'hotel': hotel_data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        description="Reject a hotel with reason",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'reason': {
                        'type': 'string',
                        'description': 'Reason for rejection'
                    }
                },
                'required': ['reason']
            }
        }
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject a pending hotel with reason
        
        Request body:
        {
            "reason": "Insufficient amenities or other reason"
        }
        """
        hotel = self.get_object()
        reason = request.data.get('reason', 'Hotel application rejected by admin')
        
        hotel.is_approved = 'rejected'
        hotel.rejection_reason = reason
        hotel.save()
        
        # Create database notification
        Notification.objects.create(
            user=hotel.partner,
            hotel=hotel,
            notification_type='hotel_rejected',
            title='Hotel Rejected',
            message=f'Your hotel "{hotel.hotel_name}" has been rejected. Reason: {reason}',
            data={
                'hotel_id': hotel.id,
                'hotel_name': hotel.hotel_name,
                'reason': reason
            }
        )
        
        # Send WebSocket notification with rejection reason
        self.send_websocket_notification(
            user_id=hotel.partner.id,
            notification_type='hotel_rejected',
            hotel_id=hotel.id,
            hotel_name=hotel.hotel_name,
            status='rejected',
            reason=reason,
            message=f'Your hotel "{hotel.hotel_name}" has been rejected. Reason: {reason}'
        )
        
        serializer = self.get_serializer(hotel)
        hotel_data = serializer.data
        
        # Convert image paths to full URLs
        if 'images' in hotel_data and hotel_data['images']:
            base_url = request.build_absolute_uri('/').rstrip('/')
            hotel_data['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel_data['images']]
        
        return Response({
            'message': 'Hotel rejected',
            'reason': reason,
            'hotel': hotel_data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(description="Get verification statistics")
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get verification queue statistics"""
        pending_count = Hotel.objects.filter(is_approved='pending').count()
        approved_count = Hotel.objects.filter(is_approved='approved').count()
        rejected_count = Hotel.objects.filter(is_approved='rejected').count()
        total_count = Hotel.objects.count()
        
        return Response({
            'pending': pending_count,
            'approved': approved_count,
            'rejected': rejected_count,
            'total': total_count
        }, status=status.HTTP_200_OK)


class ApprovedHotelsListView(APIView):
    """
    GET: List all approved hotels with count
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: PendingHotelSerializer(many=True)},
        tags=['Superadmin'],
        description="Get all approved hotels with count"
    )
    def get(self, request):
        """
        List all approved hotels with count
        Returns:
            - count: Total number of approved hotels
            - hotels: List of approved hotels
        """
        approved_hotels = Hotel.objects.filter(is_approved='approved').order_by('-created_at')
        serializer = PendingHotelSerializer(approved_hotels, many=True)
        
        hotels_data = serializer.data
        
        # Convert image paths to full URLs
        base_url = request.build_absolute_uri('/').rstrip('/')
        for hotel in hotels_data:
            if 'images' in hotel and hotel['images']:
                hotel['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel['images']]
        
        return Response({
            'count': approved_hotels.count(),
            'hotels': hotels_data
        }, status=status.HTTP_200_OK)


class ApprovedHotelDetailView(APIView):
    """
    GET: View a single approved hotel by ID
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: PendingHotelSerializer},
        tags=['Superadmin'],
        description="Get detailed information of a single approved hotel"
    )
    def get(self, request, pk):
        """
        Get detailed information of a single approved hotel
        Args:
            pk: Hotel ID
        Returns:
            - hotel: Detailed hotel information
        """
        try:
            hotel = Hotel.objects.get(id=pk, is_approved='approved')
            serializer = PendingHotelSerializer(hotel)
            
            hotel_data = serializer.data
            
            # Convert image paths to full URLs
            if 'images' in hotel_data and hotel_data['images']:
                base_url = request.build_absolute_uri('/').rstrip('/')
                hotel_data['images'] = [f"{base_url}{img}" if not img.startswith('http') else img for img in hotel_data['images']]
            
            return Response({
                'hotel': hotel_data
            }, status=status.HTTP_200_OK)
        except Hotel.DoesNotExist:
            return Response({
                'error': 'Approved hotel not found'
            }, status=status.HTTP_404_NOT_FOUND)


class AdminDashboardStatsView(APIView):
    """
    Admin dashboard statistics API endpoint
    GET /api/superadmin/dashboard/stats/
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(description="Get admin dashboard statistics")
    def get(self, request):
        """Get dashboard statistics for admin"""
        try:
            # Total Users (excluding staff)
            total_users = User.objects.filter(is_active=True, is_staff=False).count()
            
            # Total Hotels
            total_hotels = Hotel.objects.count()
            
            # Total Bookings
            total_bookings = Booking.objects.count()
            
            # Pending Verifications (pending hotels)
            pending_verifications = Hotel.objects.filter(is_approved='pending').count()
            
            # Get all approved hotels for calculations
            approved_hotels = Hotel.objects.filter(is_approved='approved')
            
            # Engagement Rate (hotels with ratings / total hotels) * 100
            hotels_with_ratings = approved_hotels.filter(total_ratings__gt=0).count()
            engagement_rate = round(
                (hotels_with_ratings / total_hotels * 100) if total_hotels > 0 else 0,
                1
            )
            
            # Active Cities (distinct cities with approved hotels)
            active_cities = approved_hotels.values('city').distinct().count()
            
            # Revenue by Commission Tier
            commission_tiers = {
                '0-3% Commission': approved_hotels.filter(commission_rate__lt=4).count(),
                '4-6% Commission': approved_hotels.filter(commission_rate__gte=4, commission_rate__lt=7).count(),
                '7-9% Commission': approved_hotels.filter(commission_rate__gte=7, commission_rate__lte=10).count(),
            }
            
            # Additional stats
            approved_hotels_count = approved_hotels.count()
            rejected_hotels_count = Hotel.objects.filter(is_approved='rejected').count()
            
            # Average hotel rating
            avg_hotel_rating = approved_hotels.aggregate(avg=Avg('average_rating'))['avg'] or 0.0
            avg_hotel_rating = round(avg_hotel_rating, 2)
            
            # Total confirmed bookings
            confirmed_bookings = Booking.objects.filter(status='confirmed').count()
            
            return Response({
                'status': 'success',
                'data': {
                    'total_users': total_users,
                    'total_hotels': total_hotels,
                    'total_bookings': total_bookings,
                    'pending_verifications': pending_verifications,
                    'engagement_rate': engagement_rate,
                    'active_cities': active_cities,
                    'approved_hotels': approved_hotels_count,
                    'rejected_hotels': rejected_hotels_count,
                    'average_hotel_rating': avg_hotel_rating,
                    'confirmed_bookings': confirmed_bookings,
                    'commission_tiers': commission_tiers,
                    'timestamp': datetime.now().isoformat()
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminProfileView(APIView):
    """
    API endpoint for superadmin to manage their own profile
    GET: Retrieve admin profile
    PATCH: Update admin profile
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(description="Get superadmin profile information")
    def get(self, request):
        """Get superadmin profile"""
        try:
            # Get current logged-in user
            user = request.user
            
            # Check if user is superuser/staff
            if not user.is_staff or not user.is_superuser:
                return Response({
                    'message': 'Only superadmin can access this endpoint',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = AdminProfileSerializer(user)
            return Response({
                'message': 'Admin profile retrieved successfully',
                'profile': serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'message': str(e),
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(description="Update superadmin profile")
    def patch(self, request):
        """Update superadmin profile"""
        try:
            # Get current logged-in user
            user = request.user
            
            # Check if user is superuser/staff
            if not user.is_staff or not user.is_superuser:
                return Response({
                    'message': 'Only superadmin can access this endpoint',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = AdminProfileUpdateSerializer(user, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'message': 'Admin profile updated successfully',
                    'profile': AdminProfileSerializer(user).data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'message': 'Validation error',
                'errors': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({
                'message': str(e),
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
