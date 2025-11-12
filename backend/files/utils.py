import hashlib
from django.conf import settings


def calculate_file_hash(file):
    """
    Calculate SHA-256 hash of a file.
    Reads file in chunks for memory efficiency.
    Returns hex digest string and resets file pointer.
    """
    sha256_hash = hashlib.sha256()

    # Read file in chunks to handle large files
    for chunk in file.chunks(chunk_size=8192):
        sha256_hash.update(chunk)

    # Reset file pointer to beginning
    file.seek(0)

    return sha256_hash.hexdigest()


def check_storage_quota(user_id, file_size, file_hash=None):
    """
    Check if adding a file would exceed user's storage quota.
    Accounts for deduplication - if file_hash already exists, no additional storage is used.

    Args:
        user_id: User identifier
        file_size: Size of file in bytes
        file_hash: Optional hash to check for duplicates

    Returns:
        tuple: (bool: quota_ok, int: current_usage, int: quota_limit)
    """
    from .models import File

    # Get storage quota from settings
    storage_quota = getattr(settings, 'STORAGE_QUOTA_PER_USER', 10 * 1024 * 1024)

    # Calculate current storage usage
    current_usage = File.get_user_storage_usage(user_id)

    # If file_hash provided, check if it's a duplicate
    if file_hash:
        duplicate_exists = File.objects.filter(
            user_id=user_id,
            file_hash=file_hash,
            is_reference=False
        ).exists()

        # If duplicate exists, no additional storage will be used
        if duplicate_exists:
            return True, current_usage, storage_quota

    # Check if adding this file would exceed quota
    potential_usage = current_usage + file_size
    quota_ok = potential_usage <= storage_quota

    return quota_ok, current_usage, storage_quota
