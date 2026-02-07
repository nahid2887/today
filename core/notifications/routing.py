from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/partner/(?P<user_id>\w+)/$', consumers.HotelNotificationConsumer.as_asgi()),
]
