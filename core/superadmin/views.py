from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from hotel.models import Hotel, Notification
from .serializers import PendingHotelSerializer
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
