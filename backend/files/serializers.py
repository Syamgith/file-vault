from rest_framework import serializers
from .models import File

class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ['id', 'file', 'original_filename', 'file_type', 'size', 'uploaded_at',
                  'user_id', 'file_hash', 'reference_count', 'is_reference', 'original_file']
        read_only_fields = ['id', 'uploaded_at', 'user_id', 'file_hash', 'reference_count',
                            'is_reference', 'original_file'] 