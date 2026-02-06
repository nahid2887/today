from django.contrib import admin
from .models import Hotel


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
