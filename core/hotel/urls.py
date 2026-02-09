from django.urls import path
from .views import (
    HotelView, SpecialOfferView, SpecialOfferDetailView, HotelDetailView,
    HotelBulkSyncView, HotelRealTimeDetailView, HotelImageUploadView
)

app_name = 'hotel'

urlpatterns = [
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
]


