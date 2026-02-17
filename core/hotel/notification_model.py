"""
Notification model for hotel status updates
"""
from django.db import models
from django.contrib.auth.models import User
from hotel.models import Hotel
import json


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
