import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'cloudstore.settings'
django.setup()

from files.models import File
from accounts.models import UserProfile
from django.db.models import Sum
from django.contrib.auth.models import User

print("=" * 55)
print("Storage Audit")
print("=" * 55)

for u in User.objects.all():
    files_qs = File.objects.filter(owner=u, is_deleted=False).exclude(s3_key='pending')
    file_count = files_qs.count()
    total_size = files_qs.aggregate(t=Sum('size'))['t'] or 0
    profile, _ = UserProfile.objects.get_or_create(user=u)
    print(f"User       : {u.username}")
    print(f"Files      : {file_count}")
    print(f"Real size  : {total_size} bytes  ({round(total_size/1024/1024, 3)} MB)")
    print(f"DB counter : {profile.storage_used} bytes")
    print(f"Out of sync: {'YES - will fix on next dashboard load' if profile.storage_used != total_size else 'No'}")
    print()
