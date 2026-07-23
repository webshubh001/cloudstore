"""
Full S3 test: connect, upload, download, delete.
"""
import os, django, tempfile
os.environ['DJANGO_SETTINGS_MODULE'] = 'cloudstore.settings'
django.setup()

from files.utils import (
    check_s3_connection, upload_to_s3, download_from_s3,
    delete_from_s3, _get_s3_client, _get_bucket
)
from django.conf import settings

print("=" * 55)
print("S3 Connection & Upload Test")
print("=" * 55)
print("Bucket :", settings.AWS_STORAGE_BUCKET_NAME)
print("Region :", settings.AWS_S3_REGION_NAME)
print()

# 1. Connection test
print("[1] Testing bucket access...")
try:
    client = _get_s3_client()
    client.head_bucket(Bucket=_get_bucket())
    print("    PASS - Bucket reachable")
except Exception as e:
    print("    FAIL -", type(e).__name__, str(e))
    exit(1)

# 2. Upload test
TEST_KEY = "cloudstore-test/connection_test.txt"
TEST_DATA = b"CloudStore S3 connection test - safe to delete"
print()
print("[2] Uploading test file (unencrypted)...")
try:
    upload_to_s3(TEST_DATA, TEST_KEY, content_type='text/plain', encrypt=False)
    print("    PASS - Uploaded", TEST_KEY)
except Exception as e:
    print("    FAIL -", type(e).__name__, str(e))
    exit(1)

# 3. Download test
print()
print("[3] Downloading test file...")
try:
    downloaded = download_from_s3(TEST_KEY, decrypt=False)
    assert downloaded == TEST_DATA, "Content mismatch!"
    print("    PASS - Downloaded and content matches")
except Exception as e:
    print("    FAIL -", type(e).__name__, str(e))
    exit(1)

# 4. Encrypted upload/download
TEST_KEY_ENC = "cloudstore-test/connection_test_enc.bin"
print()
print("[4] Testing encrypted upload/download...")
try:
    upload_to_s3(TEST_DATA, TEST_KEY_ENC, content_type='text/plain', encrypt=True)
    decrypted = download_from_s3(TEST_KEY_ENC, decrypt=True)
    assert decrypted == TEST_DATA, "Decrypted content mismatch!"
    print("    PASS - Encrypted upload and decryption OK")
except Exception as e:
    print("    FAIL -", type(e).__name__, str(e))
    exit(1)

# 5. Cleanup
print()
print("[5] Cleaning up test files...")
delete_from_s3(TEST_KEY)
delete_from_s3(TEST_KEY_ENC)
print("    PASS - Test files deleted")

print()
print("=" * 55)
print("ALL TESTS PASSED - S3 is fully working!")
print("=" * 55)
print()
print("You can now upload files from the CloudStore web app.")
print("Storage tracking will update automatically on the dashboard.")
