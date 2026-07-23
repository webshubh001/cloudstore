from django.urls import path
from . import views

app_name = 'files'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # File listing
    path('files/', views.file_list, name='file_list'),
    path('files/folder/<int:folder_id>/', views.file_list, name='file_list_folder'),

    # Folder management
    path('folders/create/', views.folder_create, name='folder_create'),
    path('folders/create/<int:parent_id>/', views.folder_create, name='folder_create_in'),
    path('folders/<int:folder_id>/delete/', views.folder_delete, name='folder_delete'),

    # File upload
    path('upload/', views.file_upload, name='file_upload'),
    path('upload/<int:folder_id>/', views.file_upload, name='file_upload_folder'),

    # File operations
    path('files/<int:file_id>/download/', views.file_download, name='file_download'),
    path('files/<int:file_id>/delete/', views.file_delete, name='file_delete'),
    path('files/<int:file_id>/rename/', views.file_rename, name='file_rename'),

    # Trash
    path('trash/', views.trash_view, name='trash'),
    path('trash/<int:file_id>/restore/', views.restore_file, name='restore_file'),
    path('trash/empty/', views.empty_trash, name='empty_trash'),
    path('trash/<int:file_id>/delete-permanent/', views.permanent_delete, name='permanent_delete'),

    # File sharing
    path('files/<int:file_id>/share/', views.share_file, name='share_file'),
    path('shares/<int:share_id>/revoke/', views.revoke_share, name='revoke_share'),
    path('share/<uuid:token>/', views.shared_download, name='shared_download'),

    # Search
    path('search/', views.search_files, name='search'),

    # Version history
    path('files/<int:file_id>/versions/', views.version_history, name='version_history'),
    path('files/<int:file_id>/versions/<int:version_id>/restore/', views.restore_version, name='restore_version'),
    path('files/<int:file_id>/versions/<int:version_id>/download/', views.download_version, name='download_version'),

    # Storage stats API
    path('api/storage-stats/', views.storage_stats_api, name='storage_stats_api'),
]
