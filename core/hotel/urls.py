from django.urls import path
from .views import HotelView, HotelUpdateView

app_name = 'hotel'

urlpatterns = [
    path('', HotelView.as_view(), name='hotel'),  # GET and POST
    path('update/', HotelUpdateView.as_view(), name='hotel_update'),  # PATCH
]
