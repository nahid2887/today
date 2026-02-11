from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HotelVerificationViewSet, ApprovedHotelsListView, ApprovedHotelDetailView

router = DefaultRouter()
router.register(r'hotels', HotelVerificationViewSet, basename='hotel-verification')

app_name = 'superadmin'

urlpatterns = [
    path('', include(router.urls)),
    path('approved-hotels/', ApprovedHotelsListView.as_view(), name='approved-hotels-list'),
    path('approved-hotels/<int:pk>/', ApprovedHotelDetailView.as_view(), name='approved-hotel-detail'),
]
