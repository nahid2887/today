"""
WebSocket URL routing for Django Channels
"""
from django.urls import re_path
from core.consumers import PartnerNotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/partner/(?P<user_id>\w+)/$', PartnerNotificationConsumer.as_asgi()),
]
