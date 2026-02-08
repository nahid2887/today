from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from hotel.models import Hotel


class FavoriteHotel(models.Model):
    """Model to store favorite hotels for travelers"""
    traveler = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_hotels'
    )
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('traveler', 'hotel')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.traveler.username} - {self.hotel.hotel_name}"


class HotelRating(models.Model):
    """Model to store hotel ratings from travelers"""
    traveler = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hotel_ratings'
    )
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5"
    )
    review = models.TextField(
        blank=True,
        null=True,
        help_text="Optional review text"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('traveler', 'hotel')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.traveler.username} - {self.hotel.hotel_name} - {self.rating}/5"
