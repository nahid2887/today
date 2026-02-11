from django.urls import path
from .views import (
<<<<<<< HEAD
    HotelView, HotelUpdateView,
    BookingCreateView, BookingListView, BookingDetailView
=======
    HotelView, SpecialOfferView, SpecialOfferDetailView, HotelDetailView,
    HotelBulkSyncView, HotelRealTimeDetailView, HotelImageUploadView
>>>>>>> 25b4413610ab56532672901829a009d3cea036ca
)

app_name = 'hotel'

urlpatterns = [
<<<<<<< HEAD
    path('', HotelView.as_view(), name='hotel'),  # GET and POST
    path('update/', HotelUpdateView.as_view(), name='hotel_update'),  # PATCH
    
    # Hotel Booking Endpoints (3 APIs)
    path('bookings/create/', BookingCreateView.as_view(), name='booking_create'),  # POST
    path('bookings/', BookingListView.as_view(), name='booking_list'),  # GET list
    path('bookings/<int:booking_id>/', BookingDetailView.as_view(), name='booking_detail'),  # GET single
=======
    # Partner Hotel Management
    path('', HotelView.as_view(), name='hotel'),  # GET and PATCH only
    path('<int:pk>/', HotelDetailView.as_view(), name='hotel_detail'),  # GET hotel details with offers
    
    # Image Upload
    path('upload-image/', HotelImageUploadView.as_view(), name='upload_image'),  # POST - Upload image file
    
    # Special Offers
    path('special-offers/', SpecialOfferView.as_view(), name='special_offers'),  # GET and POST
    path('special-offers/<int:pk>/', SpecialOfferDetailView.as_view(), name='special_offer_detail'),  # GET and PATCH
    
    # AI System Endpoints
    path('sync/', HotelBulkSyncView.as_view(), name='hotel_bulk_sync'),  # GET - Bulk sync for RAG
    path('ai/details/<int:hotel_id>/', HotelRealTimeDetailView.as_view(), name='hotel_realtime_detail'),  # GET - Real-time details
>>>>>>> 25b4413610ab56532672901829a009d3cea036ca
]


