from django.urls import path, include
from rest_framework.routers import DefaultRouter
from traveler.views import FavoriteHotelViewSet

router = DefaultRouter()
router.register(r'favorite-hotels', FavoriteHotelViewSet, basename='favorite-hotel')

urlpatterns = [
    path('', include(router.urls)),
]
