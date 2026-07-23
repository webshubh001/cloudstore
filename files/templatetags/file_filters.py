from django import template

register = template.Library()


@register.filter
def format_bytes(num_bytes):
    """Convert bytes to human-readable size string."""
    try:
        num_bytes = int(num_bytes)
    except (ValueError, TypeError):
        return "0 B"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 ** 2:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 ** 3:
        return f"{num_bytes / (1024**2):.2f} MB"
    return f"{num_bytes / (1024**3):.2f} GB"


@register.filter
def percentage(value, total):
    """Calculate percentage of value out of total."""
    try:
        return min(round((int(value) / int(total)) * 100, 1), 100)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def mime_to_icon(mime_type):
    """Return Font Awesome icon class for a MIME type."""
    if not mime_type:
        return 'fa-file'
    if mime_type.startswith('image/'):
        return 'fa-file-image'
    if mime_type.startswith('video/'):
        return 'fa-file-video'
    if mime_type.startswith('audio/'):
        return 'fa-file-audio'
    if 'pdf' in mime_type:
        return 'fa-file-pdf'
    if mime_type.startswith('text/'):
        return 'fa-file-lines'
    if 'zip' in mime_type or 'tar' in mime_type:
        return 'fa-file-zipper'
    if 'spreadsheet' in mime_type or 'excel' in mime_type:
        return 'fa-file-excel'
    if 'presentation' in mime_type or 'powerpoint' in mime_type:
        return 'fa-file-powerpoint'
    if 'word' in mime_type or 'document' in mime_type:
        return 'fa-file-word'
    return 'fa-file'


@register.filter
def subtract(value, arg):
    """Subtract arg from value."""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0


@register.simple_tag
def get_file_count(folder):
    """Return total file count for a folder."""
    return folder.total_file_count()
