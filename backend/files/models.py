from django.db import models
import uuid
import os

def file_upload_path(instance, filename):
    """Generate file path for new file upload"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('uploads', filename)

class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to=file_upload_path)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    user_id = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    reference_count = models.IntegerField(default=1)
    is_reference = models.BooleanField(default=False)
    original_file = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='references')

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['user_id', 'file_hash']),
            models.Index(fields=['uploaded_at']),
            models.Index(fields=['file_type']),
        ]

    def __str__(self):
        return self.original_filename

    @staticmethod
    def get_user_storage_usage(user_id):
        """
        Calculate total storage used by a user (accounting for deduplication)
        Only counts original files, not references
        """
        total = sum(
            f.size for f in File.objects.filter(user_id=user_id, is_reference=False)
        )
        return total
