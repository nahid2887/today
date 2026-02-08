from django.urls import path, include
from rest_framework.routers import DefaultRouter
from traveler.views import FavoriteHotelViewSet, HotelRatingViewSet

router = DefaultRouter()
router.register(r'favorite-hotels', FavoriteHotelViewSet, basename='favorite-hotel')
router.register(r'hotel-ratings', HotelRatingViewSet, basename='hotel-rating')

urlpatterns = [
    path('', include(router.urls)),
]
