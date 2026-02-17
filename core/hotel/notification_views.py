"""
API views for partner notifications
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db.models import Q
from hotel.models import Notification
import logging

logger = logging.getLogger(__name__)


class NotificationListView(APIView):
    """
    GET: List all notifications for the current user (partner)
    Query params:
      - unread_only: bool (default: false) - show only unread notifications
      - limit: int (default: 20) - number of notifications to return
      - offset: int (default: 0) - pagination offset
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Notifications'],
        description="Get list of notifications for partner",
        responses={200: dict}
    )
    def get(self, request):
        user = request.user
        unread_only = request.query_params.get('unread_only', 'false').lower() == 'true'
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))
        
        # Get notifications
        notifications = Notification.objects.filter(user=user)
        
        if unread_only:
            notifications = notifications.filter(is_read=False)
        
        total_count = notifications.count()
        unread_count = Notification.objects.filter(user=user, is_read=False).count()
        
        # Pagination
        notifications = notifications[offset:offset + limit]
        
        return Response({
            'total_count': total_count,
            'unread_count': unread_count,
            'limit': limit,
            'offset': offset,
            'results': [n.to_dict() for n in notifications]
        }, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    """
    GET: Get a specific notification
    PATCH: Mark notification as read/unread
    DELETE: Delete a notification
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Notifications'],
        description="Get a specific notification",
        responses={200: dict}
    )
    def get(self, request, notification_id):
        user = request.user
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            return Response(notification.to_dict(), status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        tags=['Notifications'],
        description="Mark notification as read/unread",
        request={'type': 'object', 'properties': {'is_read': {'type': 'boolean'}}},
        responses={200: dict}
    )
    def patch(self, request, notification_id):
        user = request.user
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            is_read = request.data.get('is_read', notification.is_read)
            notification.is_read = is_read
            notification.save()
            
            return Response(notification.to_dict(), status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        tags=['Notifications'],
        description="Delete a notification",
        responses={204: None}
    )
    def delete(self, request, notification_id):
        user = request.user
        
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Notification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class NotificationMarkAllReadView(APIView):
    """
    POST: Mark all notifications as read for the current user
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Notifications'],
        description="Mark all notifications as read",
        responses={200: dict}
    )
    def post(self, request):
        user = request.user
        
        # Update all unread notifications
        updated = Notification.objects.filter(
            user=user,
            is_read=False
        ).update(is_read=True)
        
        return Response({
            'message': f'{updated} notification(s) marked as read',
            'updated_count': updated
        }, status=status.HTTP_200_OK)
