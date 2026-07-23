from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile


class ProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ('avatar', 'bio', 'storage_quota', 'storage_used')
    readonly_fields = ('storage_used',)


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_storage_used')

    def get_storage_used(self, obj):
        try:
            return f"{obj.profile.storage_used_mb} MB / {obj.profile.storage_quota_gb} GB"
        except UserProfile.DoesNotExist:
            return "No profile"
    get_storage_used.short_description = 'Storage Used'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'storage_used_mb', 'storage_quota_gb', 'storage_used_percentage', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('storage_used', 'created_at', 'updated_at')

    def storage_used_mb(self, obj):
        return f"{obj.storage_used_mb} MB"
    storage_used_mb.short_description = 'Used'

    def storage_quota_gb(self, obj):
        return f"{obj.storage_quota_gb} GB"
    storage_quota_gb.short_description = 'Quota'

    def storage_used_percentage(self, obj):
        return f"{obj.storage_used_percentage}%"
    storage_used_percentage.short_description = '% Used'
