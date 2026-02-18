"""
WebSocket handlers for partner notifications
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from hotel.models import Hotel, Notification
import logging

logger = logging.getLogger(__name__)


class PartnerNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for partner hotel approval notifications
    Connect: ws://localhost:8000/ws/partner/{user_id}/
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'partner_{self.user_id}'
        
        # Verify user exists and is a partner
        user = await self.get_user(self.user_id)
        if not user:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"Partner {self.user_id} connected")
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to notification service',
            'user_id': self.user_id
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"Partner {self.user_id} disconnected")
    
    async def hotel_notification(self, event):
        """Receive hotel notification message from group - handles approve/reject"""
        notification_type = event.get('notification_type', 'unknown')
        
        message_data = {
            'type': notification_type,
            'hotel_id': event.get('hotel_id'),
            'hotel_name': event.get('hotel_name'),
            'status': event.get('status'),
            'timestamp': event.get('timestamp'),
            'message': event.get('message')
        }
        
        # Add reason if rejection
        if notification_type == 'hotel_rejected' and event.get('reason'):
            message_data['reason'] = event['reason']
        
        await self.send(text_data=json.dumps(message_data))
    
    async def hotel_approved(self, event):
        """Legacy: Receive hotel approval message from group"""
        await self.hotel_notification(event)
    
    async def hotel_rejected(self, event):
        """Legacy: Receive hotel rejection message from group"""
        await self.hotel_notification(event)
    
    async def notification_update(self, event):
        """Generic notification update"""
        await self.send(text_data=json.dumps({
            'type': event['notification_type'],
            'data': event['data'],
            'timestamp': event.get('timestamp')
        }))
    
    @database_sync_to_async
    def get_user(self, user_id):
        """Get user from database"""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_recent_notifications(self):
        """Get recent notifications for the partner"""
        try:
            if hasattr(Notification, 'objects'):
                notifications = Notification.objects.filter(
                    user_id=self.user_id
                ).order_by('-created_at')[:10]
                
                return [self.serialize_notification(n) for n in notifications]
            
            return []
        except Exception as e:
            logger.error(f"Error getting notifications: {e}", exc_info=True)
            return []
    
    def serialize_notification(self, notification):
        """Serialize notification object"""
        return {
            'id': notification.id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'data': notification.data,
            'read': notification.is_read,
            'timestamp': notification.created_at.isoformat()
        }
