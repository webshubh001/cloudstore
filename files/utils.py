"""
Utility functions for AWS S3 operations and file encryption.

Encryption: Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).
Files are encrypted server-side before upload to S3 and decrypted on download.
"""

import io
import logging
import mimetypes
import os
from typing import Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── Encryption Helpers ───────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption key."""
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_file(data: bytes) -> bytes:
    """Encrypt file bytes using Fernet (AES-128-CBC + HMAC-SHA256)."""
    f = _get_fernet()
    return f.encrypt(data)


def decrypt_file(data: bytes) -> bytes:
    """Decrypt Fernet-encrypted file bytes."""
    f = _get_fernet()
    try:
        return f.decrypt(data)
    except InvalidToken as e:
        logger.error("Decryption failed — invalid token or wrong key.")
        raise ValueError("Failed to decrypt file. The file may be corrupted or the key is incorrect.") from e


# ─── S3 Client ───────────────────────────────────────────────────────────────

def _get_s3_client():
    """Return a configured boto3 S3 client."""
    return boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
    )


def _get_bucket() -> str:
    """Return the configured S3 bucket name."""
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    if not bucket:
        raise ValueError("AWS_STORAGE_BUCKET_NAME is not configured.")
    return bucket


# ─── S3 Operations ───────────────────────────────────────────────────────────

def upload_to_s3(
    file_data: bytes,
    s3_key: str,
    content_type: str = 'application/octet-stream',
    encrypt: bool = True,
) -> Tuple[str, int]:
    """
    Upload file to S3, optionally encrypting first.

    Returns:
        (s3_key, size_of_original_data)
    """
    original_size = len(file_data)

    if encrypt:
        upload_data = encrypt_file(file_data)
        upload_content_type = 'application/octet-stream'
    else:
        upload_data = file_data
        upload_content_type = content_type

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=_get_bucket(),
            Key=s3_key,
            Body=upload_data,
            ContentType=upload_content_type,
            ServerSideEncryption='AES256',  # Additional S3-level encryption
        )
        logger.info(f"Uploaded to S3: {s3_key} ({original_size} bytes)")
        return s3_key, original_size

    except NoCredentialsError:
        logger.error("AWS credentials not found.")
        raise ValueError("AWS credentials are not configured correctly.")
    except ClientError as e:
        logger.error(f"S3 upload failed for {s3_key}: {e}")
        raise


def download_from_s3(s3_key: str, decrypt: bool = True) -> bytes:
    """
    Download file from S3, optionally decrypting.

    Returns raw bytes of the (decrypted) file.
    """
    try:
        client = _get_s3_client()
        response = client.get_object(Bucket=_get_bucket(), Key=s3_key)
        data = response['Body'].read()

        if decrypt:
            data = decrypt_file(data)

        logger.info(f"Downloaded from S3: {s3_key}")
        return data

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            logger.error(f"S3 key not found: {s3_key}")
            raise FileNotFoundError(f"File not found in S3: {s3_key}")
        logger.error(f"S3 download failed for {s3_key}: {e}")
        raise


def delete_from_s3(s3_key: str) -> bool:
    """Delete an object from S3. Returns True on success."""
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=_get_bucket(), Key=s3_key)
        logger.info(f"Deleted from S3: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"S3 delete failed for {s3_key}: {e}")
        return False


def get_presigned_url(s3_key: str, expires_in: int = 3600, filename: str = '') -> str:
    """
    Generate a presigned S3 URL for direct (unencrypted) download.
    Note: For encrypted files, use download_from_s3() instead.
    Returns the presigned URL string.
    """
    try:
        client = _get_s3_client()
        params = {'Bucket': _get_bucket(), 'Key': s3_key}
        if filename:
            params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'

        url = client.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL for {s3_key}: {e}")
        raise


def copy_s3_object(source_key: str, dest_key: str) -> bool:
    """Copy an S3 object within the same bucket (for version management)."""
    try:
        client = _get_s3_client()
        client.copy_object(
            Bucket=_get_bucket(),
            CopySource={'Bucket': _get_bucket(), 'Key': source_key},
            Key=dest_key,
        )
        logger.info(f"Copied S3 object: {source_key} → {dest_key}")
        return True
    except ClientError as e:
        logger.error(f"S3 copy failed {source_key} → {dest_key}: {e}")
        return False


def check_s3_connection() -> bool:
    """Test S3 connectivity. Returns True if successful."""
    try:
        client = _get_s3_client()
        client.head_bucket(Bucket=_get_bucket())
        return True
    except Exception:
        return False


# ─── S3 Key Generators ────────────────────────────────────────────────────────

def make_s3_key(user_id: int, file_id: int, filename: str, version: int = 0) -> str:
    """
    Generate a structured S3 key for a file.

    Format: users/{user_id}/files/{file_id}/v{version}/{filename}
    """
    safe_filename = filename.replace(' ', '_')
    if version > 0:
        return f"users/{user_id}/files/{file_id}/v{version}/{safe_filename}"
    return f"users/{user_id}/files/{file_id}/{safe_filename}"


# ─── MIME Type Detection ─────────────────────────────────────────────────────

def detect_mime_type(filename: str, file_data: Optional[bytes] = None) -> str:
    """Detect MIME type from filename, falling back to generic binary."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or 'application/octet-stream'


# ─── Storage Statistics ───────────────────────────────────────────────────────

def get_storage_breakdown(user) -> dict:
    """
    Return storage breakdown by file type for a user.
    Returns dict with category names and byte totals.
    """
    from files.models import File

    files = File.objects.filter(owner=user, is_deleted=False).exclude(s3_key='pending').values('mime_type', 'size')

    breakdown = {
        'Images': 0,
        'Videos': 0,
        'Audio': 0,
        'Documents': 0,
        'Archives': 0,
        'Other': 0,
    }

    for f in files:
        mime = f['mime_type'] or ''
        size = f['size']
        if mime.startswith('image/'):
            breakdown['Images'] += size
        elif mime.startswith('video/'):
            breakdown['Videos'] += size
        elif mime.startswith('audio/'):
            breakdown['Audio'] += size
        elif 'pdf' in mime or 'word' in mime or 'document' in mime or mime.startswith('text/'):
            breakdown['Documents'] += size
        elif 'zip' in mime or 'tar' in mime or 'compress' in mime:
            breakdown['Archives'] += size
        else:
            breakdown['Other'] += size

    return breakdown


def format_bytes(num_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 ** 2:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 ** 3:
        return f"{num_bytes / (1024**2):.2f} MB"
    return f"{num_bytes / (1024**3):.2f} GB"
