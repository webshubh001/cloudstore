import json
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import (
    HttpResponse, JsonResponse, Http404, StreamingHttpResponse
)
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q, Sum
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives

from .models import Folder, File, FileVersion, FileShare
from .forms import (
    FolderCreateForm, FileUploadForm, FileRenameForm,
    FileShareForm, FileSearchForm
)
from .utils import (
    upload_to_s3, download_from_s3, delete_from_s3,
    make_s3_key, detect_mime_type, get_storage_breakdown, format_bytes,
    copy_s3_object,
)
from accounts.models import UserProfile

logger = logging.getLogger(__name__)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Main dashboard with storage stats, recent files, quick actions."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # ── Auto-sync storage_used from actual file sizes ──────────────────────
    # This ensures the storage display is always accurate, regardless of
    # whether the counter got out of sync (e.g. from failed uploads).
    actual_used = File.objects.filter(
        owner=request.user, is_deleted=False
    ).exclude(s3_key='pending').aggregate(total=Sum('size'))['total'] or 0

    if profile.storage_used != actual_used:
        profile.storage_used = actual_used
        profile.save(update_fields=['storage_used'])
    # ──────────────────────────────────────────────────────────────────────

    recent_files = File.objects.filter(
        owner=request.user, is_deleted=False
    ).exclude(s3_key='pending').select_related('folder').order_by('-updated_at')[:8]

    root_folders = Folder.objects.filter(
        owner=request.user, parent=None
    ).order_by('name')

    total_files = File.objects.filter(
        owner=request.user, is_deleted=False
    ).exclude(s3_key='pending').count()
    total_folders = Folder.objects.filter(owner=request.user).count()
    trash_count = File.objects.filter(owner=request.user, is_deleted=True).count()
    shared_count = FileShare.objects.filter(shared_by=request.user, is_active=True).count()

    storage_breakdown = get_storage_breakdown(request.user)
    breakdown_json = json.dumps({k: format_bytes(v) for k, v in storage_breakdown.items()})
    breakdown_bytes_json = json.dumps(list(storage_breakdown.values()))
    breakdown_labels_json = json.dumps(list(storage_breakdown.keys()))

    return render(request, 'files/dashboard.html', {
        'profile': profile,
        'recent_files': recent_files,
        'root_folders': root_folders,
        'total_files': total_files,
        'total_folders': total_folders,
        'trash_count': trash_count,
        'shared_count': shared_count,
        'storage_breakdown': storage_breakdown,
        'breakdown_json': breakdown_json,
        'breakdown_bytes_json': breakdown_bytes_json,
        'breakdown_labels_json': breakdown_labels_json,
        'format_bytes': format_bytes,
    })



# ─── File Listing ─────────────────────────────────────────────────────────────

@login_required
def file_list(request, folder_id=None):
    """List files and subfolders in a directory."""
    current_folder = None
    breadcrumbs = []

    if folder_id:
        current_folder = get_object_or_404(Folder, pk=folder_id, owner=request.user)
        breadcrumbs = current_folder.get_breadcrumbs()

    files = File.objects.filter(
        owner=request.user,
        folder=current_folder,
        is_deleted=False
    ).order_by('-created_at')

    subfolders = Folder.objects.filter(
        owner=request.user,
        parent=current_folder
    ).order_by('name')

    # Sorting
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['original_name', '-original_name', '-created_at', 'created_at', '-size', 'size']
    if sort_by in valid_sorts:
        files = files.order_by(sort_by)

    folder_form = FolderCreateForm()
    upload_form = FileUploadForm()

    return render(request, 'files/file_list.html', {
        'files': files,
        'subfolders': subfolders,
        'current_folder': current_folder,
        'breadcrumbs': breadcrumbs,
        'folder_form': folder_form,
        'upload_form': upload_form,
        'sort_by': sort_by,
    })


# ─── Folder Operations ────────────────────────────────────────────────────────

@login_required
@require_POST
def folder_create(request, parent_id=None):
    """Create a new folder."""
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, pk=parent_id, owner=request.user)

    form = FolderCreateForm(request.POST)
    if form.is_valid():
        folder = form.save(commit=False)
        folder.owner = request.user
        folder.parent = parent
        try:
            folder.save()
            messages.success(request, f'Folder "{folder.name}" created.')
        except Exception:
            messages.error(request, f'A folder named "{folder.name}" already exists here.')
    else:
        messages.error(request, 'Invalid folder name.')

    if parent_id:
        return redirect('files:file_list_folder', folder_id=parent_id)
    return redirect('files:file_list')


@login_required
def folder_delete(request, folder_id):
    """Delete a folder and all its contents."""
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user)
    parent_id = folder.parent_id

    if request.method == 'POST':
        # Recursively delete all files in this folder from S3
        _delete_folder_recursive(folder, request.user)
        folder_name = folder.name
        folder.delete()
        messages.success(request, f'Folder "{folder_name}" deleted.')

        if parent_id:
            return redirect('files:file_list_folder', folder_id=parent_id)
        return redirect('files:file_list')

    return render(request, 'files/confirm_delete_folder.html', {'folder': folder})


def _delete_folder_recursive(folder, user):
    """Recursively delete all S3 objects and update storage stats."""
    profile = user.profile
    for f in folder.files.all():
        try:
            delete_from_s3(f.s3_key)
            for version in f.versions.all():
                delete_from_s3(version.s3_key)
            profile.subtract_usage(f.size)
        except Exception as e:
            logger.error(f"Error deleting S3 object during folder delete: {e}")
    for sub in folder.subfolders.all():
        _delete_folder_recursive(sub, user)


# ─── File Upload ──────────────────────────────────────────────────────────────

@login_required
def file_upload(request, folder_id=None):
    """Upload one or more files to S3."""
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, pk=folder_id, owner=request.user)

    if request.method == 'POST':
        uploaded_files = request.FILES.getlist('files')
        description = request.POST.get('description', '')
        encrypt = request.POST.get('encrypt', 'on') == 'on'

        if not uploaded_files:
            messages.error(request, 'No files were selected.')
            return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        success_count = 0
        error_count = 0

        for uploaded_file in uploaded_files:
            try:
                file_data = uploaded_file.read()
                file_size = len(file_data)
                filename = uploaded_file.name

                # Quota check
                if not profile.has_space_for(file_size):
                    messages.error(
                        request,
                        f'Storage quota exceeded. Cannot upload "{filename}". '
                        f'Free up space or upgrade your plan.'
                    )
                    error_count += 1
                    continue

                # Size limit check
                if file_size > settings.MAX_UPLOAD_SIZE:
                    messages.error(request, f'File "{filename}" exceeds 100 MB limit.')
                    error_count += 1
                    continue

                mime_type = detect_mime_type(filename, file_data)

                # Check for existing file with same name → versioning
                existing = File.objects.filter(
                    owner=request.user,
                    folder=current_folder,
                    original_name=filename,
                    is_deleted=False
                ).first()

                if existing:
                    # Save current as a version
                    version_num = existing.versions.count() + 1
                    version_key = make_s3_key(
                        request.user.id, existing.id, filename, version=version_num
                    )
                    copy_s3_object(existing.s3_key, version_key)
                    FileVersion.objects.create(
                        file=existing,
                        version_number=version_num,
                        s3_key=version_key,
                        size=existing.size,
                    )
                    # Upload new version
                    new_key = make_s3_key(request.user.id, existing.id, filename)
                    upload_to_s3(file_data, new_key, mime_type, encrypt=encrypt)

                    # Update storage usage difference
                    size_diff = file_size - existing.size
                    profile.add_usage(size_diff)

                    existing.s3_key = new_key
                    existing.size = file_size
                    existing.mime_type = mime_type
                    existing.is_encrypted = encrypt
                    existing.description = description
                    existing.save()
                    success_count += 1

                else:
                    # Create new File record with a temp key first (need ID).
                    # Wrap in a transaction so the DB record is rolled back
                    # if the S3 upload fails, avoiding orphan 'pending' records.
                    try:
                        with transaction.atomic():
                            file_obj = File.objects.create(
                                owner=request.user,
                                folder=current_folder,
                                original_name=filename,
                                s3_key='pending',  # temp placeholder until S3 key known
                                size=file_size,
                                mime_type=mime_type,
                                is_encrypted=encrypt,
                                description=description,
                            )

                            s3_key = make_s3_key(request.user.id, file_obj.id, filename)
                            upload_to_s3(file_data, s3_key, mime_type, encrypt=encrypt)

                            file_obj.s3_key = s3_key
                            file_obj.save(update_fields=['s3_key'])

                        profile.add_usage(file_size)
                        success_count += 1
                    except Exception as upload_err:
                        # transaction.atomic() already rolled back the DB record
                        raise upload_err

            except Exception as e:
                logger.error(f"Upload error for {uploaded_file.name}: {e}")
                messages.error(request, f'Failed to upload "{uploaded_file.name}": {str(e)}')
                error_count += 1

        if success_count > 0:
            messages.success(request, f'Successfully uploaded {success_count} file(s).')

    if folder_id:
        return redirect('files:file_list_folder', folder_id=folder_id)
    return redirect('files:file_list')


# ─── File Download ────────────────────────────────────────────────────────────

@login_required
def file_download(request, file_id):
    """Download a file, decrypting from S3 if needed."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)

    # Guard against orphan records whose upload never completed
    if file_obj.s3_key == 'pending':
        messages.error(
            request,
            f'"{file_obj.original_name}" was not uploaded successfully and cannot be downloaded. '
            'Please delete it and try uploading again.'
        )
        return redirect('files:file_list')

    try:
        file_data = download_from_s3(file_obj.s3_key, decrypt=file_obj.is_encrypted)
    except FileNotFoundError:
        messages.error(request, 'File not found in storage. It may have been deleted.')
        return redirect('files:file_list')
    except Exception as e:
        logger.error(f"Download error for file {file_id}: {e}")
        messages.error(request, f'Download failed: {str(e)}')
        return redirect('files:file_list')

    response = HttpResponse(file_data, content_type=file_obj.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{file_obj.original_name}"'
    response['Content-Length'] = len(file_data)
    return response


# ─── File Delete (Soft) ───────────────────────────────────────────────────────

@login_required
def file_delete(request, file_id):
    """Soft-delete a file (move to trash)."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)
    folder_id = file_obj.folder_id

    file_obj.soft_delete()
    messages.success(request, f'"{file_obj.original_name}" moved to trash.')

    if folder_id:
        return redirect('files:file_list_folder', folder_id=folder_id)
    return redirect('files:file_list')


# ─── Trash ────────────────────────────────────────────────────────────────────

@login_required
def trash_view(request):
    """Show deleted files."""
    deleted_files = File.objects.filter(
        owner=request.user, is_deleted=True
    ).order_by('-deleted_at')

    return render(request, 'files/trash.html', {'deleted_files': deleted_files})


@login_required
def restore_file(request, file_id):
    """Restore a file from trash."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=True)
    file_obj.restore()
    messages.success(request, f'"{file_obj.original_name}" restored successfully.')
    return redirect('files:trash')


@login_required
@require_POST
def empty_trash(request):
    """Permanently delete all trashed files."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    deleted_files = File.objects.filter(owner=request.user, is_deleted=True)

    count = 0
    for f in deleted_files:
        try:
            delete_from_s3(f.s3_key)
            for version in f.versions.all():
                delete_from_s3(version.s3_key)
            profile.subtract_usage(f.size)
            f.delete()
            count += 1
        except Exception as e:
            logger.error(f"Error permanently deleting file {f.id}: {e}")

    messages.success(request, f'Trash emptied. {count} file(s) permanently deleted.')
    return redirect('files:trash')


@login_required
@require_POST
def permanent_delete(request, file_id):
    """Permanently delete a single trashed file."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=True)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    try:
        delete_from_s3(file_obj.s3_key)
        for version in file_obj.versions.all():
            delete_from_s3(version.s3_key)
        profile.subtract_usage(file_obj.size)
        file_obj.delete()
        messages.success(request, 'File permanently deleted.')
    except Exception as e:
        logger.error(f"Permanent delete error for {file_id}: {e}")
        messages.error(request, 'Failed to delete file from storage.')

    return redirect('files:trash')


# ─── File Rename ─────────────────────────────────────────────────────────────

@login_required
def file_rename(request, file_id):
    """Rename a file or update its description."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)

    if request.method == 'POST':
        form = FileRenameForm(request.POST, instance=file_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'File renamed to "{file_obj.original_name}".')
        else:
            messages.error(request, 'Invalid file name.')
    return redirect(request.META.get('HTTP_REFERER', 'files:file_list'))


# ─── File Sharing ─────────────────────────────────────────────────────────────

@login_required
def share_file(request, file_id):
    """Create a share link for a file."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)
    existing_shares = FileShare.objects.filter(file=file_obj, shared_by=request.user)

    if request.method == 'POST':
        form = FileShareForm(request.POST)
        if form.is_valid():
            share = form.save(commit=False)
            share.file = file_obj
            share.shared_by = request.user
            share.save()
            share_url = request.build_absolute_uri(
                f'/share/{share.token}/'
            )
            
            # Send email if address is provided
            if share.shared_email:
                try:
                    sender_name = request.user.get_full_name() or request.user.username
                    expiry_str = (
                        share.expires_at.strftime('%d %b %Y, %I:%M %p')
                        if share.expires_at else 'Never'
                    )
                    permission_label = 'View & Download' if share.can_download else 'View Only'

                    # ── Plain-text fallback ──────────────────────────────────
                    plain_body = (
                        f"{sender_name} shared a file with you via CloudStore.\n\n"
                        f"File: {file_obj.original_name}\n"
                        f"Access: {permission_label}\n"
                        f"Expires: {expiry_str}\n\n"
                        f"Open link: {share_url}\n\n"
                        f"— CloudStore Team"
                    )

                    # ── HTML email body ──────────────────────────────────────
                    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f4f7; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 560px; margin: 40px auto; background: #fff; border-radius: 12px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.08); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #7c3aed, #a855f7); padding: 32px 40px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }}
    .header p {{ color: rgba(255,255,255,0.85); margin: 6px 0 0; font-size: 14px; }}
    .body {{ padding: 36px 40px; }}
    .greeting {{ font-size: 16px; color: #374151; margin-bottom: 16px; }}
    .file-card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px;
                  padding: 20px 24px; margin-bottom: 28px; display: flex; align-items: center; gap: 16px; }}
    .file-icon {{ font-size: 36px; }}
    .file-name {{ font-weight: 700; font-size: 16px; color: #111827; margin: 0 0 4px; }}
    .file-meta {{ font-size: 13px; color: #6b7280; margin: 0; }}
    .btn {{ display: block; background: linear-gradient(135deg, #7c3aed, #a855f7); color: #fff !important;
            text-decoration: none; text-align: center; padding: 14px 32px; border-radius: 8px;
            font-weight: 600; font-size: 15px; margin-bottom: 24px; }}
    .info-row {{ display: flex; justify-content: space-between; font-size: 13px;
                 color: #6b7280; border-top: 1px solid #f3f4f6; padding-top: 20px; }}
    .footer {{ background: #f9fafb; text-align: center; padding: 16px; font-size: 12px; color: #9ca3af; }}
  </style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>☁️ CloudStore</h1>
    <p>Secure Cloud File Sharing</p>
  </div>
  <div class="body">
    <p class="greeting">Hi there,</p>
    <p style="color:#374151;font-size:15px;">
      <strong>{sender_name}</strong> has shared a file with you on <strong>CloudStore</strong>.
    </p>
    <div class="file-card">
      <div class="file-icon">📄</div>
      <div>
        <p class="file-name">{file_obj.original_name}</p>
        <p class="file-meta">Access: {permission_label} &nbsp;|&nbsp; Expires: {expiry_str}</p>
      </div>
    </div>
    <a href="{share_url}" class="btn">🔗 Open Shared File</a>
    <div class="info-row">
      <span>Shared by: <strong>{sender_name}</strong></span>
      <span>Expires: <strong>{expiry_str}</strong></span>
    </div>
  </div>
  <div class="footer">
    You received this because someone shared a CloudStore file with you.<br>
    If you did not expect this, you can safely ignore this email.
  </div>
</div>
</body>
</html>"""

                    subject = f"{sender_name} shared \"{file_obj.original_name}\" with you - CloudStore"
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=plain_body,
                        from_email=f"CloudStore <{settings.EMAIL_HOST_USER}>",
                        to=[share.shared_email],
                    )
                    email.attach_alternative(html_body, 'text/html')
                    email.send(fail_silently=False)
                    messages.success(request, f'Share link created and emailed to {share.shared_email}!')

                except Exception as e:
                    import smtplib
                    err_str = str(e)
                    logger.error(f"Error sending share email to {share.shared_email}: {e}")
                    if isinstance(e, smtplib.SMTPAuthenticationError):
                        messages.warning(
                            request,
                            'Share link created ✓, but email could not be sent — '
                            'Gmail requires an App Password. Go to your Google Account → '
                            'Security → 2-Step Verification → App Passwords and paste it '
                            'in EMAIL_HOST_PASSWORD in your .env file.'
                        )
                    else:
                        messages.warning(
                            request,
                            f'Share link created ✓, but email delivery failed: {err_str}'
                        )
            else:
                messages.success(request, 'Share link created!')
                
            return render(request, 'files/share_file.html', {
                'file': file_obj,
                'form': FileShareForm(),
                'existing_shares': existing_shares,
                'new_share': share,
                'share_url': share_url,
            })
        else:
            messages.error(request, 'Invalid share settings.')
    else:
        form = FileShareForm()

    return render(request, 'files/share_file.html', {
        'file': file_obj,
        'form': form,
        'existing_shares': existing_shares,
    })


@login_required
@require_POST
def revoke_share(request, share_id):
    """Revoke a file share link."""
    share = get_object_or_404(FileShare, pk=share_id, shared_by=request.user)
    share.is_active = False
    share.save(update_fields=['is_active'])
    messages.success(request, 'Share link revoked.')
    return redirect('files:share_file', file_id=share.file_id)


def shared_download(request, token):
    """Public view: download/preview a file via share token."""
    share = get_object_or_404(FileShare, token=token, is_active=True)

    if share.is_expired:
        return render(request, 'files/shared_expired.html', {'share': share})

    share.increment_access()
    file_obj = share.file

    if request.method == 'POST' and share.can_download:
        # Download the file
        try:
            file_data = download_from_s3(file_obj.s3_key, decrypt=file_obj.is_encrypted)
        except Exception as e:
            logger.error(f"Shared download error for token {token}: {e}")
            return render(request, 'files/shared_expired.html', {'error': str(e)})

        response = HttpResponse(file_data, content_type=file_obj.mime_type or 'application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_obj.original_name}"'
        return response

    return render(request, 'files/shared_download.html', {
        'share': share,
        'file': file_obj,
    })


# ─── Search ───────────────────────────────────────────────────────────────────

@login_required
def search_files(request):
    """Search files by name, type, and date."""
    form = FileSearchForm(request.GET)
    results = File.objects.none()
    query = ''

    if form.is_valid():
        query = form.cleaned_data.get('q', '')
        file_type = form.cleaned_data.get('file_type', '')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        results = File.objects.filter(owner=request.user, is_deleted=False)

        if query:
            results = results.filter(
                Q(original_name__icontains=query) |
                Q(description__icontains=query)
            )

        if file_type:
            results = results.filter(mime_type__icontains=file_type)

        if date_from:
            results = results.filter(created_at__date__gte=date_from)

        if date_to:
            results = results.filter(created_at__date__lte=date_to)

        results = results.select_related('folder').order_by('-created_at')

    return render(request, 'files/search_results.html', {
        'form': form,
        'results': results,
        'query': query,
        'result_count': results.count() if query else 0,
    })


# ─── Version History ──────────────────────────────────────────────────────────

@login_required
def version_history(request, file_id):
    """View all versions of a file."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user)
    versions = file_obj.versions.order_by('-version_number')

    return render(request, 'files/version_history.html', {
        'file': file_obj,
        'versions': versions,
    })


@login_required
@require_POST
def restore_version(request, file_id, version_id):
    """Restore a file to a specific historical version."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user)
    version = get_object_or_404(FileVersion, pk=version_id, file=file_obj)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Save current as a new version first
    current_version_num = file_obj.versions.count() + 1
    current_archive_key = make_s3_key(
        request.user.id, file_obj.id, file_obj.original_name, version=current_version_num
    )
    copy_s3_object(file_obj.s3_key, current_archive_key)
    FileVersion.objects.create(
        file=file_obj,
        version_number=current_version_num,
        s3_key=current_archive_key,
        size=file_obj.size,
        note=f"Auto-saved before restoring v{version.version_number}",
    )

    # Download the old version data and re-upload as current
    try:
        old_data = download_from_s3(version.s3_key, decrypt=file_obj.is_encrypted)
        new_key = make_s3_key(request.user.id, file_obj.id, file_obj.original_name)
        upload_to_s3(old_data, new_key, file_obj.mime_type, encrypt=file_obj.is_encrypted)

        # Update storage usage
        size_diff = len(old_data) - file_obj.size
        profile.add_usage(size_diff)

        file_obj.s3_key = new_key
        file_obj.size = len(old_data)
        file_obj.save(update_fields=['s3_key', 'size'])

        messages.success(request, f'File restored to version {version.version_number}.')
    except Exception as e:
        logger.error(f"Version restore error: {e}")
        messages.error(request, f'Failed to restore version: {str(e)}')

    return redirect('files:version_history', file_id=file_id)


@login_required
def download_version(request, file_id, version_id):
    """Download a specific file version."""
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user)
    version = get_object_or_404(FileVersion, pk=version_id, file=file_obj)

    try:
        file_data = download_from_s3(version.s3_key, decrypt=file_obj.is_encrypted)
    except Exception as e:
        messages.error(request, f'Failed to download version: {str(e)}')
        return redirect('files:version_history', file_id=file_id)

    name_parts = file_obj.original_name.rsplit('.', 1)
    versioned_name = f"{name_parts[0]}_v{version.version_number}.{name_parts[1]}" if len(name_parts) == 2 else f"{file_obj.original_name}_v{version.version_number}"

    response = HttpResponse(file_data, content_type=file_obj.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{versioned_name}"'
    return response


# ─── Storage Stats API ────────────────────────────────────────────────────────

@login_required
def storage_stats_api(request):
    """AJAX endpoint returning storage stats as JSON for charts."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Always recalculate from actual file sizes so charts are live-accurate
    actual_used = File.objects.filter(
        owner=request.user, is_deleted=False
    ).exclude(s3_key='pending').aggregate(total=Sum('size'))['total'] or 0

    if profile.storage_used != actual_used:
        profile.storage_used = actual_used
        profile.save(update_fields=['storage_used'])

    breakdown = get_storage_breakdown(request.user)

    return JsonResponse({
        'storage_used': profile.storage_used,
        'storage_quota': profile.storage_quota,
        'storage_used_percentage': profile.storage_used_percentage,
        'storage_free': profile.storage_free_bytes,
        'storage_used_human': format_bytes(profile.storage_used),
        'storage_quota_human': format_bytes(profile.storage_quota),
        'breakdown': {k: {'bytes': v, 'human': format_bytes(v)} for k, v in breakdown.items()},
    })
