from django.urls import path
from .views import HotelView, HotelUpdateView, SpecialOfferView, SpecialOfferDetailView

app_name = 'hotel'

urlpatterns = [
    path('', HotelView.as_view(), name='hotel'),  # GET and POST
    path('update/', HotelUpdateView.as_view(), name='hotel_update'),  # PATCH
    path('special-offers/', SpecialOfferView.as_view(), name='special_offers'),  # GET and POST
    path('special-offers/<int:pk>/', SpecialOfferDetailView.as_view(), name='special_offer_detail'),  # GET and PATCH
]

