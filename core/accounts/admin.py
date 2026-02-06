from django.contrib import admin
from .models import TravelerProfile, PartnerProfile, TravelerInfo, PartnerInfo

@admin.register(TravelerProfile)
class TravelerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'profile_type', 'created_at')
    search_fields = ('user__username', 'user__email')
    list_filter = ('profile_type', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'property_name', 'role', 'created_at')
    search_fields = ('user__username', 'user__email', 'property_name')
    list_filter = ('role', 'created_at', 'special_deals_offers')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Account', {
            'fields': ('user', 'profile_type')
        }),
        ('Property Information', {
            'fields': ('property_name', 'property_address', 'website_url')
        }),
        ('Contact Information', {
            'fields': ('contact_person_name', 'phone_number', 'role')
        }),
        ('Preferences', {
            'fields': ('special_deals_offers',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TravelerInfo)
class TravelerInfoAdmin(admin.ModelAdmin):
    list_display = ('title', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not TravelerInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False


@admin.register(PartnerInfo)
class PartnerInfoAdmin(admin.ModelAdmin):
    list_display = ('title', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not PartnerInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False
