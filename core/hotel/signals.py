from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from accounts.models import PartnerProfile
from .models import Hotel


@receiver(post_save, sender=PartnerProfile)
def create_hotel_for_partner(sender, instance, created, **kwargs):
    """
    Signal to automatically create a Hotel when a Partner account is created.
    This ensures every partner has a hotel associated with them.
    """
    if created:
        # Check if hotel doesn't already exist
        if not Hotel.objects.filter(partner=instance.user).exists():
            Hotel.objects.create(
                partner=instance.user,
                hotel_name=instance.property_name,
                location=instance.property_address,
                city='',
                country='',
                base_price_per_night=0.00,
                is_approved='pending'  # Auto-created hotels start as pending
            )
