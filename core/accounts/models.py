from django.db import models
from django.contrib.auth.models import User
import random
from django.utils import timezone
from datetime import timedelta

class TravelerProfile(models.Model):
    PROFILE_TYPE_CHOICES = [
        ('traveler', 'Traveler'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='traveler_profile')
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPE_CHOICES, default='traveler')
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.profile_type}"


class PartnerProfile(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Property Owner'),
        ('manager', 'Property Manager'),
        ('admin', 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='partner_profile')
    profile_type = models.CharField(max_length=20, default='partner')
    
    # Step 1: Property Info
    property_name = models.CharField(max_length=255)
    property_address = models.TextField()
    website_url = models.URLField(blank=True, null=True)
    
    # Step 2: Contact & Setup
    contact_person_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    special_deals_offers = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='partner_profiles/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Partner - {self.property_name}"


class PasswordResetOTP(models.Model):
    """Model to store OTP for password reset"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_otp')
    otp = models.CharField(max_length=6)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"{self.email} - OTP"

    def is_valid(self):
        """Check if OTP is still valid"""
        return timezone.now() < self.expires_at and not self.is_verified

    @staticmethod
    def generate_otp():
        """Generate a 6-digit OTP"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])


class TravelerInfo(models.Model):
    """Static information for travelers - Singleton model"""
    title = models.CharField(max_length=255, default="Welcome Travelers!")
    description = models.TextField(default="Discover amazing destinations and experiences.")
    terms_and_conditions = models.TextField(blank=True, null=True)
    privacy_policy = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Traveler Information"
        verbose_name_plural = "Traveler Information"

    def __str__(self):
        return "Traveler Info"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (Singleton pattern)"""
        if not self.pk and TravelerInfo.objects.exists():
            raise ValueError("Only one TravelerInfo instance is allowed")
        return super().save(*args, **kwargs)


class PartnerInfo(models.Model):
    """Static information for partners - Singleton model"""
    title = models.CharField(max_length=255, default="Welcome Partners!")
    description = models.TextField(default="Join our network of trusted hospitality partners.")
    terms_and_conditions = models.TextField(blank=True, null=True)
    privacy_policy = models.TextField(blank=True, null=True)
    commission_info = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Partner Information"
        verbose_name_plural = "Partner Information"

    def __str__(self):
        return "Partner Info"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (Singleton pattern)"""
        if not self.pk and PartnerInfo.objects.exists():
            raise ValueError("Only one PartnerInfo instance is allowed")
        return super().save(*args, **kwargs)
