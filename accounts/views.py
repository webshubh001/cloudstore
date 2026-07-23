from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, ProfileAvatarForm
from .models import UserProfile


def register_view(request):
    """Handle user registration."""
    if request.user.is_authenticated:
        return redirect('files:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to CloudStore, {user.first_name}! Your account has been created.')
            return redirect('files:dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('files:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'files:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password. Please try again.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Handle user logout."""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """View and update user profile."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action', 'update_profile')

        if action == 'update_profile':
            profile_form = ProfileUpdateForm(request.POST, instance=request.user)
            avatar_form = ProfileAvatarForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid() and avatar_form.is_valid():
                profile_form.save()
                avatar_form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('accounts:profile')
            else:
                messages.error(request, 'Please correct the errors below.')

        elif action == 'change_password':
            pwd_form = PasswordChangeForm(request.user, request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password changed successfully.')
                return redirect('accounts:profile')
            else:
                messages.error(request, 'Password change failed. Please check the form.')
            profile_form = ProfileUpdateForm(instance=request.user)
            avatar_form = ProfileAvatarForm(instance=profile)
            return render(request, 'accounts/profile.html', {
                'profile_form': profile_form,
                'avatar_form': avatar_form,
                'pwd_form': pwd_form,
                'profile': profile,
            })
    else:
        profile_form = ProfileUpdateForm(instance=request.user)
        avatar_form = ProfileAvatarForm(instance=profile)

    pwd_form = PasswordChangeForm(request.user)

    # File type statistics for the profile page
    from files.models import File
    user_files = File.objects.filter(owner=request.user, is_deleted=False)
    file_type_stats = {}
    for f in user_files:
        category = _get_file_category(f.mime_type)
        file_type_stats[category] = file_type_stats.get(category, 0) + 1

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'avatar_form': avatar_form,
        'pwd_form': pwd_form,
        'profile': profile,
        'file_type_stats': file_type_stats,
        'total_files': user_files.count(),
    })


def _get_file_category(mime_type):
    """Helper to categorize MIME types."""
    if not mime_type:
        return 'Other'
    if mime_type.startswith('image/'):
        return 'Images'
    if mime_type.startswith('video/'):
        return 'Videos'
    if mime_type.startswith('audio/'):
        return 'Audio'
    if 'pdf' in mime_type:
        return 'PDFs'
    if mime_type.startswith('text/'):
        return 'Documents'
    if 'zip' in mime_type or 'tar' in mime_type or 'compress' in mime_type:
        return 'Archives'
    if 'spreadsheet' in mime_type or 'excel' in mime_type:
        return 'Spreadsheets'
    if 'presentation' in mime_type or 'powerpoint' in mime_type:
        return 'Presentations'
    if 'word' in mime_type or 'document' in mime_type:
        return 'Documents'
    return 'Other'
