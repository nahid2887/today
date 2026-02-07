import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from hotel.models import Hotel


class HotelNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for hotel verification notifications
    Connection URL: ws://localhost:8000/ws/partner/{user_id}/
    """
    
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room_group_name = f'partner_{self.user_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def hotel_notification(self, event):
        """
        Send notification to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': event['notification_type'],
            'hotel_id': event['hotel_id'],
            'hotel_name': event['hotel_name'],
            'status': event['status'],
            'reason': event.get('reason', None),
            'timestamp': event['timestamp'],
            'message': event['message']
        }))
