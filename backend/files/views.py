from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import File
from .serializers import FileSerializer
from .utils import calculate_file_hash, check_storage_quota
from django.utils import timezone
from datetime import datetime
import os

# Create your views here.

class FileViewSet(viewsets.ModelViewSet):
    queryset = File.objects.all()
    serializer_class = FileSerializer

    def list(self, request, *args, **kwargs):
        """List files with search and filter support"""
        try:
            return super().list(request, *args, **kwargs)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        """Filter files by user_id and apply search/filter parameters"""
        user_id = self.request.headers.get('UserId')
        if not user_id:
            return File.objects.none()

        queryset = File.objects.filter(user_id=user_id)

        # Step 2: Search by filename (case-insensitive partial match)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(original_filename__icontains=search)

        # Step 3: Filter by file_type (exact MIME type match)
        file_type = self.request.query_params.get('file_type')
        if file_type:
            queryset = queryset.filter(file_type=file_type)

        # Step 4: Filter by size range with validation
        min_size = self.request.query_params.get('min_size')
        max_size = self.request.query_params.get('max_size')
        min_size_int = None
        max_size_int = None

        if min_size:
            try:
                min_size_int = int(min_size)
                if min_size_int < 0:
                    raise ValueError("min_size must be a positive integer")
                queryset = queryset.filter(size__gte=min_size_int)
            except ValueError as e:
                raise ValueError(f"Invalid min_size parameter: {str(e)}")

        if max_size:
            try:
                max_size_int = int(max_size)
                if max_size_int < 0:
                    raise ValueError("max_size must be a positive integer")
                queryset = queryset.filter(size__lte=max_size_int)
            except ValueError as e:
                raise ValueError(f"Invalid max_size parameter: {str(e)}")

        # Validate min_size < max_size
        if min_size_int is not None and max_size_int is not None:
            if min_size_int > max_size_int:
                raise ValueError("min_size must be less than or equal to max_size")

        # Step 5: Filter by date range with validation
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                queryset = queryset.filter(uploaded_at__gte=start_dt)
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Invalid start_date parameter: must be ISO 8601 format")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                queryset = queryset.filter(uploaded_at__lte=end_dt)
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Invalid end_date parameter: must be ISO 8601 format")

        # Validate start_date < end_date
        if start_dt is not None and end_dt is not None:
            if start_dt > end_dt:
                raise ValueError("start_date must be before or equal to end_date")

        return queryset

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Extract user_id from headers
        user_id = request.headers.get('UserId')
        if not user_id:
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate file hash
        file_hash = calculate_file_hash(file_obj)

        # Check storage quota before proceeding
        quota_ok, current_usage, quota_limit = check_storage_quota(
            user_id, file_obj.size, file_hash
        )

        if not quota_ok:
            return Response(
                {'error': 'Storage Quota Exceeded'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Check for duplicate file with same hash and user_id
        existing_file = File.objects.filter(
            user_id=user_id,
            file_hash=file_hash,
            is_reference=False
        ).first()

        if existing_file:
            # Duplicate found - create reference instead of saving file
            file_instance = File(
                original_filename=file_obj.name,
                file_type=file_obj.content_type,
                size=file_obj.size,
                user_id=user_id,
                file_hash=file_hash,
                is_reference=True,
                original_file=existing_file,
                file=existing_file.file.name
            )
            file_instance.save()

            # Increment reference count on original file
            existing_file.reference_count += 1
            existing_file.save()

            serializer = self.get_serializer(file_instance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            # New file - save normally
            data = {
                'file': file_obj,
                'original_filename': file_obj.name,
                'file_type': file_obj.content_type,
                'size': file_obj.size
            }

            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            file_instance = serializer.save(
                user_id=user_id,
                file_hash=file_hash,
                is_reference=False
            )

            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        if instance.is_reference:
            # Decrement reference count on original file
            if instance.original_file:
                instance.original_file.reference_count -= 1
                instance.original_file.save()
            instance.delete()
        else:
            # Decrement reference count
            instance.reference_count -= 1

            if instance.reference_count <= 0:
                # No more references - delete physical file and record
                if instance.file and os.path.isfile(instance.file.path):
                    os.remove(instance.file.path)
                instance.delete()
            else:
                # Still has references - just update count
                instance.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def storage_stats(self, request):
        """Get storage usage statistics for the user"""
        from django.conf import settings

        user_id = request.headers.get('UserId')
        if not user_id:
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get storage quota from settings
        storage_limit = getattr(settings, 'STORAGE_QUOTA_PER_USER', 10 * 1024 * 1024)

        # Get all files for user
        user_files = File.objects.filter(user_id=user_id)

        # Calculate total storage used (only original files)
        total_storage_used = sum(
            f.size for f in user_files if not f.is_reference
        )

        # Calculate original storage (all files including references)
        original_storage_used = sum(f.size for f in user_files)

        # Calculate savings
        storage_savings = original_storage_used - total_storage_used
        savings_percentage = (storage_savings / original_storage_used * 100) if original_storage_used > 0 else 0.0

        # Calculate remaining storage
        storage_remaining = storage_limit - total_storage_used

        # Calculate quota usage percentage
        quota_usage_percentage = (total_storage_used / storage_limit * 100) if storage_limit > 0 else 0.0

        return Response({
            'user_id': user_id,
            'total_storage_used': total_storage_used,
            'original_storage_used': original_storage_used,
            'storage_savings': storage_savings,
            'savings_percentage': round(savings_percentage, 2),
            'storage_limit': storage_limit,
            'storage_remaining': storage_remaining,
            'quota_usage_percentage': round(quota_usage_percentage, 2)
        })

    @action(detail=False, methods=['get'])
    def file_types(self, request):
        """Get list of unique file types (MIME types) for the user"""
        user_id = request.headers.get('UserId')
        if not user_id:
            return Response({'error': 'UserId header is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get distinct file types for user
        file_types = File.objects.filter(
            user_id=user_id
        ).values_list('file_type', flat=True).distinct().order_by('file_type')

        return Response(list(set(file_types)))
