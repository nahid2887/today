from django.urls import path
from .views import (
    HotelView,
    HotelDetailView,
    SpecialOfferView,
    SpecialOfferDetailView,
    # Booking - Traveler
    BookingCreateView,
    BookingListView,
    BookingDetailView,
    # Booking - Partner Manager
    PartnerBookingsView,
    # Analytics
    PartnerAnalyticsView,
    PartnerDashboardView,
    # AI System
    HotelBulkSyncView,
    HotelRealTimeDetailView,
    # Image Upload
    HotelImageUploadView,
    # Payouts
    PayoutCreateView,
    PayoutCompleteView,
    PayoutListView
)
from .notification_views import (
    NotificationListView,
    NotificationDetailView,
    NotificationMarkAllReadView
)

app_name = 'hotel'

urlpatterns = [
    # ========== PARTNER HOTEL MANAGEMENT ==========
    path('', HotelView.as_view(), name='hotel'),  # GET and PATCH
    path('<int:pk>/', HotelDetailView.as_view(), name='hotel_detail'),  # GET hotel details with offers
    path('upload-image/', HotelImageUploadView.as_view(), name='upload_image'),  # POST - Upload image
    
    # ========== SPECIAL OFFERS ==========
    path('special-offers/', SpecialOfferView.as_view(), name='special_offers'),  # GET and POST
    path('special-offers/<int:pk>/', SpecialOfferDetailView.as_view(), name='special_offer_detail'),  # GET and PATCH
    
    # ========== TRAVELER BOOKING ENDPOINTS ==========
    path('bookings/create/', BookingCreateView.as_view(), name='booking_create'),  # POST - Create booking
    path('bookings/', BookingListView.as_view(), name='booking_list'),  # GET - Traveler's bookings
    path('bookings/<int:booking_id>/', BookingDetailView.as_view(), name='booking_detail'),  # GET/PATCH/DELETE
    
    # ========== PARTNER BOOKING MANAGEMENT ==========
    # Single unified endpoint for hotel managers to see all bookings for their hotel
    path('manager/bookings/', PartnerBookingsView.as_view(), name='partner_bookings'),  # GET - Hotel manager's bookings
    
    # ========== PARTNER ANALYTICS ==========
    path('manager/analytics/', PartnerAnalyticsView.as_view(), name='partner_analytics'),  # GET - Hotel analytics & metrics
    path('manager/dashboard/', PartnerDashboardView.as_view(), name='partner_dashboard'),  # GET - Dashboard data (independent page)
    
    # ========== NOTIFICATIONS ==========
    path('notifications/', NotificationListView.as_view(), name='notifications_list'),  # GET - List notifications
    path('notifications/<int:notification_id>/', NotificationDetailView.as_view(), name='notification_detail'),  # GET/PATCH/DELETE
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='mark_all_read'),  # POST - Mark all as read
    
    # ========== AI SYSTEM ENDPOINTS ==========
    path('sync/', HotelBulkSyncView.as_view(), name='hotel_bulk_sync'),  # GET - Bulk sync for RAG
    path('ai/details/<int:hotel_id>/', HotelRealTimeDetailView.as_view(), name='hotel_realtime_detail'),  # GET - Real-time details
    
    # ========== PAYOUT ENDPOINTS ==========
    path('payouts/create/', PayoutCreateView.as_view(), name='payout_create'),  # POST - Create payout link
    path('payouts/', PayoutListView.as_view(), name='payout_list'),  # GET - List partner payouts
    path('payouts/<int:pk>/complete/', PayoutCompleteView.as_view(), name='payout_complete'),  # GET - Complete payout
]



