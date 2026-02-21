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


class Booking(models.Model):
    """Hotel booking model - Travelers can book hotels with automatic price calculation"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    # Relationships
    traveler = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hotel_bookings',
        help_text="Traveler who made the booking"
    )
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text="Hotel being booked"
    )
    
    # Booking Dates
    check_in_date = models.DateField(help_text="Check-in date")
    check_out_date = models.DateField(help_text="Check-out date")
    
    # Guest Information
    number_of_guests = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Number of guests"
    )
    
    # Pricing (auto-calculated)
    price_per_night = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per night from hotel"
    )
    number_of_nights = models.PositiveIntegerField(
        default=1,
        help_text="Number of nights"
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total price for the booking"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Discount percentage if any"
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Discount amount in currency"
    )
    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Final price after discount"
    )
    
    # Special Perks/Amenities
    special_perks = models.JSONField(
        default=list,
        blank=True,
        help_text="List of special perks included ['Free parking', 'Welcome cocktail', 'Late checkout']"
    )
    
    # Booking Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Booking status"
    )
    
    # Notes
    special_requests = models.TextField(
        blank=True,
        null=True,
        help_text="Special requests from the traveler"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Hotel Booking"
        verbose_name_plural = "Hotel Bookings"
        ordering = ['-created_at']
    

    def __str__(self):
        return f"{self.traveler.username} - {self.hotel.hotel_name} ({self.check_in_date} to {self.check_out_date})"
    
    def calculate_total_price(self):
        """Calculate total price based on number of nights and price per night"""
        from datetime import datetime
        check_in = datetime.strptime(str(self.check_in_date), '%Y-%m-%d').date() if isinstance(self.check_in_date, str) else self.check_in_date
        check_out = datetime.strptime(str(self.check_out_date), '%Y-%m-%d').date() if isinstance(self.check_out_date, str) else self.check_out_date
        
        nights = (check_out - check_in).days
        self.number_of_nights = max(nights, 1)
        self.total_price = self.price_per_night * self.number_of_nights
        
        # Calculate discount
        if self.discount_percentage > 0:
            self.discount_amount = (self.total_price * self.discount_percentage) / 100
            self.final_price = self.total_price - self.discount_amount
        else:
            self.discount_amount = 0
            self.final_price = self.total_price
    
    def save(self, *args, **kwargs):
        """Override save to calculate pricing"""
        self.calculate_total_price()
        super().save(*args, **kwargs)


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


class Notification(models.Model):
    """
    Store notifications for partners about their hotel approvals/rejections
    """
    NOTIFICATION_TYPES = [
        ('hotel_approved', 'Hotel Approved'),
        ('hotel_rejected', 'Hotel Rejected'),
        ('hotel_pending', 'Hotel Under Review'),
        ('booking_received', 'New Booking'),
        ('booking_cancelled', 'Booking Cancelled'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, null=True, blank=True)
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Store additional data
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_read']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title}"
    
    def to_dict(self):
        """Convert to dictionary for JSON response"""
        return {
            'id': self.id,
            'type': self.notification_type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'hotel_id': self.hotel_id,
            'read': self.is_read,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class Payout(models.Model):
    """Model to manage partner payouts"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    partner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payouts')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='payouts', null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Payout amount in USD")
    currency = models.CharField(max_length=3, default='USD')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Stripe Integration
    stripe_payout_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    payout_url = models.URLField(blank=True, null=True, help_text="Link for partner to complete payout")
    
    # Bank Account Info
    bank_account_last4 = models.CharField(max_length=4, blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['partner', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payout ${self.amount} - {self.partner.username} ({self.status})"
