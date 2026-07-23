from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class UserProfile(models.Model):
    """Extended user profile with storage tracking and avatar."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, max_length=300)
    storage_quota = models.BigIntegerField(
        default=settings.DEFAULT_STORAGE_QUOTA,
        help_text="Storage quota in bytes"
    )
    storage_used = models.BigIntegerField(default=0, help_text="Bytes currently used")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile({self.user.username})"

    # ─── Storage helpers ──────────────────────────────────────────────────────
    @property
    def storage_used_bytes(self):
        return self.storage_used

    @property
    def storage_used_mb(self):
        return round(self.storage_used / (1024 * 1024), 2)

    @property
    def storage_used_gb(self):
        return round(self.storage_used / (1024 * 1024 * 1024), 3)

    @property
    def storage_quota_gb(self):
        return round(self.storage_quota / (1024 * 1024 * 1024), 1)

    @property
    def storage_used_percentage(self):
        if self.storage_quota == 0:
            return 0
        return min(round((self.storage_used / self.storage_quota) * 100, 1), 100)

    @property
    def storage_free_bytes(self):
        return max(self.storage_quota - self.storage_used, 0)

    @property
    def is_storage_full(self):
        return self.storage_used >= self.storage_quota

    def has_space_for(self, file_size_bytes: int) -> bool:
        """Check if user has enough quota for a given file size."""
        return (self.storage_used + file_size_bytes) <= self.storage_quota

    def add_usage(self, bytes_count: int):
        self.storage_used = max(0, self.storage_used + bytes_count)
        self.save(update_fields=['storage_used'])

    def subtract_usage(self, bytes_count: int):
        self.storage_used = max(0, self.storage_used - bytes_count)
        self.save(update_fields=['storage_used'])
