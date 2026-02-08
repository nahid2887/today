from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Hotel(models.Model):
    """Hotel model - One hotel per partner user"""
    
    ROOM_TYPE_CHOICES = [
        ('standard', 'Standard'),
        ('deluxe', 'Deluxe'),
        ('suite', 'Suite'),
        ('presidential', 'Presidential'),
    ]
    
    # Relationship with Partner
    partner = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='hotel',
        help_text="Partner user who owns this hotel"
    )
    
    # Hotel Information (from image)
    hotel_name = models.CharField(max_length=255, help_text="Name of the hotel")
    location = models.CharField(max_length=500, help_text="Specific location/address")
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    number_of_rooms = models.PositiveIntegerField(default=1, help_text="Total number of rooms")
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default='standard')
    description = models.TextField(blank=True, null=True, help_text="Hotel description")
    base_price_per_night = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Base price per night in USD"
    )
    
    # Property Images (multiple images support)
    images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs/paths for the hotel property"
    )
    
    # Amenities (as JSON or separate fields)
    amenities = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of amenities like ['Free WiFi', 'Pool', 'Gym', 'Restaurant']"
    )
    
    # Approval and Rating
    is_approved = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending',
        help_text="Admin approval status"
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for hotel rejection"
    )
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(5.00)],
        help_text="Average rating from travelers (0.00 to 5.00)"
    )
    total_ratings = models.PositiveIntegerField(
        default=0,
        help_text="Total number of ratings received"
    )
    
    # Commission Settings
    commission_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=5.00,
        validators=[MinValueValidator(1.00), MaxValueValidator(10.00)],
        help_text="Commission rate percentage (1.00% to 10.00%)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Hotel"
        verbose_name_plural = "Hotels"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.hotel_name} - {self.city}, {self.country}"
    
    def update_rating(self, new_rating):
        """
        Update average rating when a new rating is added
        Args:
            new_rating: Rating value from 1 to 5
        """
        total_sum = (self.average_rating * self.total_ratings) + new_rating
        self.total_ratings += 1
        self.average_rating = round(total_sum / self.total_ratings, 2)
        self.save()


class SpecialOffer(models.Model):
    """Special promotional offers for hotels"""
    
    # Relationship with Hotel
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='special_offers',
        help_text="Hotel this offer belongs to"
    )
    
    # Offer Details
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(1.00), MaxValueValidator(100.00)],
        help_text="Discount percentage (1.00% to 100.00%)"
    )
    
    special_perks = models.JSONField(
        default=list,
        blank=True,
        help_text="List of special perks like ['Free breakfast', 'Late checkout', 'Spa credit $50']"
    )
    
    # Validity
    valid_until = models.DateField(
        help_text="Offer valid until this date"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this offer is currently active"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Special Offer"
        verbose_name_plural = "Special Offers"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.hotel.hotel_name} - {self.discount_percentage}% off (Valid until {self.valid_until})"
    
    def is_valid(self):
        """Check if offer is still valid"""
        from django.utils import timezone
        return self.is_active and self.valid_until >= timezone.now().date()
