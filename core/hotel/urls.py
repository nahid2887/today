from django.urls import path
from .views import (
    HotelView, HotelUpdateView,
    BookingCreateView, BookingListView, BookingDetailView
)

app_name = 'hotel'

urlpatterns = [
    path('', HotelView.as_view(), name='hotel'),  # GET and POST
    path('update/', HotelUpdateView.as_view(), name='hotel_update'),  # PATCH
    
    # Hotel Booking Endpoints (3 APIs)
    path('bookings/create/', BookingCreateView.as_view(), name='booking_create'),  # POST
    path('bookings/', BookingListView.as_view(), name='booking_list'),  # GET list
    path('bookings/<int:booking_id>/', BookingDetailView.as_view(), name='booking_detail'),  # GET single
]
