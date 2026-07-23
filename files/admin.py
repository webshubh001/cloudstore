from django.contrib import admin
from .models import Folder, File, FileVersion, FileShare


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'parent', 'created_at', 'total_file_count')
    search_fields = ('name', 'owner__username')
    list_filter = ('created_at',)
    raw_id_fields = ('owner', 'parent')

    def total_file_count(self, obj):
        return obj.total_file_count()
    total_file_count.short_description = 'Files'


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'owner', 'folder', 'size_human', 'mime_type', 'is_encrypted', 'is_deleted', 'created_at')
    search_fields = ('original_name', 'owner__username')
    list_filter = ('is_encrypted', 'is_deleted', 'mime_type', 'created_at')
    raw_id_fields = ('owner', 'folder')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 's3_key')

    def size_human(self, obj):
        return obj.size_human
    size_human.short_description = 'Size'

    actions = ['restore_files']

    def restore_files(self, request, queryset):
        queryset.update(is_deleted=False, deleted_at=None)
        self.message_user(request, f'{queryset.count()} file(s) restored.')
    restore_files.short_description = 'Restore selected files from trash'


@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = ('file', 'version_number', 'size_human', 'created_at')
    search_fields = ('file__original_name',)
    raw_id_fields = ('file',)
    readonly_fields = ('created_at',)

    def size_human(self, obj):
        return obj.size_human
    size_human.short_description = 'Size'


@admin.register(FileShare)
class FileShareAdmin(admin.ModelAdmin):
    list_display = ('file', 'shared_by', 'permission', 'is_active', 'is_expired', 'access_count', 'created_at')
    search_fields = ('file__original_name', 'shared_by__username', 'shared_email')
    list_filter = ('permission', 'is_active', 'created_at')
    raw_id_fields = ('file', 'shared_by', 'shared_with')
    readonly_fields = ('token', 'access_count', 'created_at')

    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'
