from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HotelVerificationViewSet

router = DefaultRouter()
router.register(r'hotels', HotelVerificationViewSet, basename='hotel-verification')

app_name = 'superadmin'

urlpatterns = [
    path('', include(router.urls)),
]
