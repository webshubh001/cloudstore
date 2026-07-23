from django import forms
from django.forms.widgets import Input
from django.utils import timezone
from .models import Folder, File, FileShare


class MultipleFileInput(Input):
    """
    A minimal file input widget that supports the 'multiple' attribute.
    Django's built-in FileInput/ClearableFileInput raise ValueError for multiple=True,
    so we subclass Input directly to bypass that restriction.
    """
    input_type = 'file'
    needs_multipart_form = True
    allow_multiple_selected = True  # Django 4.2+ hook (if present)

    def __init__(self, attrs=None):
        default_attrs = {'class': 'form-control', 'multiple': True, 'id': 'fileInputModal'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


class FolderCreateForm(forms.ModelForm):
    """Form to create a new folder."""

    class Meta:
        model = Folder
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Folder name',
                'autofocus': True,
            })
        }


class FileUploadForm(forms.Form):
    """Handles file upload with optional folder and description."""

    files = forms.FileField(
        widget=MultipleFileInput(),
        label='Select Files',
    )
    description = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description...',
        })
    )
    encrypt = forms.BooleanField(
        required=False,
        initial=True,
        label='Encrypt file (recommended)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


class FileRenameForm(forms.ModelForm):
    """Rename a file."""

    class Meta:
        model = File
        fields = ['original_name', 'description']
        widgets = {
            'original_name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'original_name': 'File Name',
            'description': 'Description',
        }


class FileShareForm(forms.ModelForm):
    """Create a share link for a file."""

    expires_in_hours = forms.ChoiceField(
        choices=[
            ('', 'Never expires'),
            ('1', '1 hour'),
            ('24', '24 hours'),
            ('72', '3 days'),
            ('168', '7 days'),
            ('720', '30 days'),
        ],
        required=False,
        label='Expiry',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = FileShare
        fields = ['permission', 'shared_email']
        widgets = {
            'permission': forms.Select(attrs={'class': 'form-select'}),
            'shared_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional: enter email to track who it was shared with',
            }),
        }
        labels = {
            'permission': 'Access Level',
            'shared_email': 'Share with (email)',
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        hours = self.cleaned_data.get('expires_in_hours')
        if hours:
            from datetime import timedelta
            instance.expires_at = timezone.now() + timedelta(hours=int(hours))
        else:
            instance.expires_at = None
        if commit:
            instance.save()
        return instance


class FileSearchForm(forms.Form):
    """Search files by query, type, and date range."""

    q = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search files and folders...',
            'id': 'searchInput',
        })
    )
    file_type = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All types'),
            ('image', 'Images'),
            ('video', 'Videos'),
            ('audio', 'Audio'),
            ('pdf', 'PDFs'),
            ('text', 'Documents'),
            ('zip', 'Archives'),
        ],
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
    )
