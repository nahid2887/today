from django.contrib import admin
from .models import Hotel, SpecialOffer


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('hotel_name', 'city', 'country', 'partner', 'is_approved', 'average_rating', 'created_at')
    list_filter = ('is_approved', 'room_type', 'city', 'country', 'created_at')
    search_fields = ('hotel_name', 'city', 'country', 'partner__username', 'partner__email')
    readonly_fields = ('created_at', 'updated_at', 'total_ratings', 'average_rating')
    
    fieldsets = (
        ('Partner Information', {
            'fields': ('partner',)
        }),
        ('Hotel Details', {
            'fields': ('hotel_name', 'location', 'city', 'country')
        }),
        ('Room Information', {
            'fields': ('number_of_rooms', 'room_type', 'base_price_per_night', 'description')
        }),
        ('Property Images', {
            'fields': ('images',),
            'classes': ('collapse',)
        }),
        ('Amenities', {
            'fields': ('amenities',)
        }),
        ('Approval & Rating', {
            'fields': ('is_approved', 'average_rating', 'total_ratings', 'commission_rate')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow adding through API
        return request.user.is_superuser


@admin.register(SpecialOffer)
class SpecialOfferAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'discount_percentage', 'valid_until', 'is_active', 'created_at')
    list_filter = ('is_active', 'valid_until', 'created_at')
    search_fields = ('hotel__hotel_name', 'hotel__partner__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Hotel Information', {
            'fields': ('hotel',)
        }),
        ('Offer Details', {
            'fields': ('discount_percentage', 'special_perks', 'valid_until', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

