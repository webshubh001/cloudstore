from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Folder(models.Model):
    """Hierarchical folder structure per user."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subfolders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('owner', 'name', 'parent')
        ordering = ['name']
        verbose_name = 'Folder'
        verbose_name_plural = 'Folders'

    def __str__(self):
        return self.name

    def get_full_path(self):
        """Return full path e.g. Documents/Work/Reports."""
        parts = [self.name]
        parent = self.parent
        while parent:
            parts.insert(0, parent.name)
            parent = parent.parent
        return ' / '.join(parts)

    def get_breadcrumbs(self):
        """Return list of (name, folder_id) tuples for breadcrumb navigation."""
        crumbs = [(self.name, self.pk)]
        parent = self.parent
        while parent:
            crumbs.insert(0, (parent.name, parent.pk))
            parent = parent.parent
        return crumbs

    def total_file_count(self):
        """Count all files recursively."""
        count = self.files.filter(is_deleted=False).count()
        for sub in self.subfolders.all():
            count += sub.total_file_count()
        return count


class File(models.Model):
    """Represents an uploaded file with S3 storage and encryption support."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(
        Folder,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='files'
    )
    original_name = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=512, help_text="S3 object key for current version")
    size = models.BigIntegerField(help_text="File size in bytes (original, before encryption)")
    mime_type = models.CharField(max_length=150, blank=True)
    is_encrypted = models.BooleanField(default=True)
    description = models.TextField(blank=True, max_length=500)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'File'
        verbose_name_plural = 'Files'
        indexes = [
            models.Index(fields=['owner', 'is_deleted']),
            models.Index(fields=['owner', 'folder', 'is_deleted']),
        ]

    def __str__(self):
        return self.original_name

    # ─── Size helpers ─────────────────────────────────────────────────────────
    @property
    def size_kb(self):
        return round(self.size / 1024, 1)

    @property
    def size_mb(self):
        return round(self.size / (1024 * 1024), 2)

    @property
    def size_human(self):
        """Human-readable file size."""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size_kb} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size_mb} MB"
        else:
            return f"{round(self.size / (1024**3), 2)} GB"

    # ─── File type helpers ────────────────────────────────────────────────────
    @property
    def extension(self):
        if '.' in self.original_name:
            return self.original_name.rsplit('.', 1)[-1].lower()
        return ''

    @property
    def icon_class(self):
        """Font Awesome 6 icon class based on MIME type."""
        mime = self.mime_type or ''
        ext = self.extension
        if mime.startswith('image/'):
            return 'fa-file-image'
        if mime.startswith('video/'):
            return 'fa-file-video'
        if mime.startswith('audio/'):
            return 'fa-file-audio'
        if 'pdf' in mime:
            return 'fa-file-pdf'
        if mime.startswith('text/') or ext in ('txt', 'md', 'csv', 'log'):
            return 'fa-file-lines'
        if 'zip' in mime or 'tar' in mime or 'rar' in mime or ext in ('zip', 'rar', 'tar', 'gz', '7z'):
            return 'fa-file-zipper'
        if 'spreadsheet' in mime or 'excel' in mime or ext in ('xls', 'xlsx', 'ods'):
            return 'fa-file-excel'
        if 'presentation' in mime or 'powerpoint' in mime or ext in ('ppt', 'pptx', 'odp'):
            return 'fa-file-powerpoint'
        if 'word' in mime or 'document' in mime or ext in ('doc', 'docx', 'odt'):
            return 'fa-file-word'
        if ext in ('py', 'js', 'html', 'css', 'java', 'cpp', 'c', 'ts', 'go', 'rs'):
            return 'fa-file-code'
        return 'fa-file'

    @property
    def icon_color(self):
        """Color class for file type icon."""
        mime = self.mime_type or ''
        if mime.startswith('image/'):
            return 'text-success'
        if mime.startswith('video/'):
            return 'text-danger'
        if mime.startswith('audio/'):
            return 'text-warning'
        if 'pdf' in mime:
            return 'text-danger'
        if 'zip' in mime or 'tar' in mime:
            return 'text-secondary'
        if 'spreadsheet' in mime or 'excel' in mime:
            return 'text-success'
        if 'presentation' in mime or 'powerpoint' in mime:
            return 'text-warning'
        if 'word' in mime or 'document' in mime:
            return 'text-primary'
        return 'text-info'

    def soft_delete(self):
        """Move file to trash (soft delete)."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        """Restore file from trash."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    @property
    def current_version_number(self):
        return self.versions.count() + 1

    @property
    def is_image(self):
        return self.mime_type and self.mime_type.startswith('image/')


class FileVersion(models.Model):
    """Stores historical versions of a file."""

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    s3_key = models.CharField(max_length=512)
    size = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, help_text="Optional version note")

    class Meta:
        ordering = ['-version_number']
        unique_together = ('file', 'version_number')
        verbose_name = 'File Version'

    def __str__(self):
        return f"{self.file.original_name} v{self.version_number}"

    @property
    def size_human(self):
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{round(self.size/1024, 1)} KB"
        return f"{round(self.size/(1024*1024), 2)} MB"


class FileShare(models.Model):
    """Represents a file share link with optional expiry and access control."""

    PERMISSION_VIEW = 'view'
    PERMISSION_DOWNLOAD = 'download'
    PERMISSION_CHOICES = [
        (PERMISSION_VIEW, 'View Only'),
        (PERMISSION_DOWNLOAD, 'View & Download'),
    ]

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='shares')
    shared_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shares_created')
    shared_with = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shares_received'
    )
    shared_email = models.EmailField(blank=True, help_text="Email for external sharing")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default=PERMISSION_DOWNLOAD)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'File Share'

    def __str__(self):
        return f"Share({self.file.original_name} → {self.token})"

    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    @property
    def can_download(self):
        return self.permission == self.PERMISSION_DOWNLOAD

    def increment_access(self):
        self.access_count += 1
        self.save(update_fields=['access_count'])
