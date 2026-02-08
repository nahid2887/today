from django.db import models
from django.contrib.auth.models import User
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
