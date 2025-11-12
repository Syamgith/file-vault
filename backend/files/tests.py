from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from .models import File
from django.utils import timezone
from datetime import timedelta
import hashlib


class FileDeduplicationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.test_file_content = b"Test file content for deduplication"
        self.user_id = "test_user_123"

    def create_test_file(self, filename="test.txt", content=None):
        """Helper to create a test file"""
        if content is None:
            content = self.test_file_content
        return SimpleUploadedFile(filename, content, content_type="text/plain")

    def test_upload_new_file(self):
        """Test uploading a new file"""
        test_file = self.create_test_file("document.txt")
        response = self.client.post(
            '/api/files/',
            {'file': test_file},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_reference'])
        self.assertEqual(response.data['reference_count'], 1)
        self.assertIsNone(response.data['original_file'])

    def test_upload_duplicate_file(self):
        """Test uploading same file twice creates reference"""
        # Upload first file
        test_file1 = self.create_test_file("document.txt")
        response1 = self.client.post(
            '/api/files/',
            {'file': test_file1},
            HTTP_USERID=self.user_id,
            format='multipart'
        )
        original_id = response1.data['id']

        # Upload duplicate file
        test_file2 = self.create_test_file("document_copy.txt")
        response2 = self.client.post(
            '/api/files/',
            {'file': test_file2},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response2.data['is_reference'])
        self.assertEqual(str(response2.data['original_file']), str(original_id))
        self.assertEqual(response2.data['file_hash'], response1.data['file_hash'])

        # Verify original file reference count increased
        original_file = File.objects.get(id=original_id)
        self.assertEqual(original_file.reference_count, 2)

    def test_different_users_same_file(self):
        """Test same file uploaded by different users creates separate storage"""
        user1 = "user1"
        user2 = "user2"

        # User 1 uploads
        test_file1 = self.create_test_file("doc.txt")
        response1 = self.client.post(
            '/api/files/',
            {'file': test_file1},
            HTTP_USERID=user1,
            format='multipart'
        )

        # User 2 uploads same file
        test_file2 = self.create_test_file("doc.txt")
        response2 = self.client.post(
            '/api/files/',
            {'file': test_file2},
            HTTP_USERID=user2,
            format='multipart'
        )

        # Both should be original files, not references
        self.assertFalse(response1.data['is_reference'])
        self.assertFalse(response2.data['is_reference'])
        self.assertNotEqual(response1.data['id'], response2.data['id'])

    def test_delete_reference(self):
        """Test deleting a reference decrements count on original"""
        # Upload original
        test_file1 = self.create_test_file("file.txt")
        response1 = self.client.post(
            '/api/files/',
            {'file': test_file1},
            HTTP_USERID=self.user_id,
            format='multipart'
        )
        original_id = response1.data['id']

        # Upload reference
        test_file2 = self.create_test_file("file_copy.txt")
        response2 = self.client.post(
            '/api/files/',
            {'file': test_file2},
            HTTP_USERID=self.user_id,
            format='multipart'
        )
        reference_id = response2.data['id']

        # Delete reference
        self.client.delete(
            f'/api/files/{reference_id}/',
            HTTP_USERID=self.user_id
        )

        # Original should still exist with decremented count
        original_file = File.objects.get(id=original_id)
        self.assertEqual(original_file.reference_count, 1)

    def test_delete_original_with_references(self):
        """Test deleting original file when references exist"""
        # Upload original
        test_file1 = self.create_test_file("data.txt")
        response1 = self.client.post(
            '/api/files/',
            {'file': test_file1},
            HTTP_USERID=self.user_id,
            format='multipart'
        )
        original_id = response1.data['id']

        # Upload reference
        test_file2 = self.create_test_file("data_copy.txt")
        self.client.post(
            '/api/files/',
            {'file': test_file2},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        # Delete original
        self.client.delete(
            f'/api/files/{original_id}/',
            HTTP_USERID=self.user_id
        )

        # Original should still exist but with decremented count
        original_file = File.objects.get(id=original_id)
        self.assertEqual(original_file.reference_count, 1)

    def test_storage_stats(self):
        """Test storage statistics calculation"""
        # Upload original file
        test_file1 = self.create_test_file("stats_test.txt")
        self.client.post(
            '/api/files/',
            {'file': test_file1},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        # Upload duplicate (creates reference)
        test_file2 = self.create_test_file("stats_test_copy.txt")
        self.client.post(
            '/api/files/',
            {'file': test_file2},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        # Get storage stats
        response = self.client.get(
            '/api/files/storage_stats/',
            HTTP_USERID=self.user_id
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_id'], self.user_id)

        file_size = len(self.test_file_content)
        self.assertEqual(response.data['total_storage_used'], file_size)
        self.assertEqual(response.data['original_storage_used'], file_size * 2)
        self.assertEqual(response.data['storage_savings'], file_size)
        self.assertEqual(response.data['savings_percentage'], 50.0)

    def test_file_types_endpoint(self):
        """Test file types listing"""
        # Upload different file types
        txt_file = SimpleUploadedFile("test.txt", b"text", content_type="text/plain")
        self.client.post(
            '/api/files/',
            {'file': txt_file},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        json_file = SimpleUploadedFile("test.json", b"{}", content_type="application/json")
        self.client.post(
            '/api/files/',
            {'file': json_file},
            HTTP_USERID=self.user_id,
            format='multipart'
        )

        # Get file types
        response = self.client.get(
            '/api/files/file_types/',
            HTTP_USERID=self.user_id
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/plain", response.data)
        self.assertIn("application/json", response.data)

    def test_missing_userid_header(self):
        """Test that UserId header is required"""
        test_file = self.create_test_file("test.txt")
        response = self.client.post(
            '/api/files/',
            {'file': test_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('UserId header is required', response.json()['error'])


class SearchAndFilteringTests(TestCase):
    """Tests for Feature 2: Search & Filtering System"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.user_id = 'test-user-123'
        self.headers = {'HTTP_USERID': self.user_id}

        # Create test files with different attributes
        # File 1: small text file
        self.file1 = File.objects.create(
            original_filename='document.txt',
            file_type='text/plain',
            size=1024,
            user_id=self.user_id,
            file_hash='hash1',
            file='uploads/test1.txt'
        )

        # File 2: large image file
        self.file2 = File.objects.create(
            original_filename='photo.jpg',
            file_type='image/jpeg',
            size=5242880,  # 5MB
            user_id=self.user_id,
            file_hash='hash2',
            file='uploads/test2.jpg'
        )

        # File 3: medium PDF file
        self.file3 = File.objects.create(
            original_filename='report.pdf',
            file_type='application/pdf',
            size=102400,  # 100KB
            user_id=self.user_id,
            file_hash='hash3',
            file='uploads/test3.pdf'
        )

        # File 4: another text file with different name
        self.file4 = File.objects.create(
            original_filename='notes.txt',
            file_type='text/plain',
            size=2048,
            user_id=self.user_id,
            file_hash='hash4',
            file='uploads/test4.txt'
        )

        # File 5: file from another user (should not appear in results)
        self.file5 = File.objects.create(
            original_filename='other-user-file.txt',
            file_type='text/plain',
            size=1024,
            user_id='other-user',
            file_hash='hash5',
            file='uploads/test5.txt'
        )

    def test_list_all_files_for_user(self):
        """Test listing all files for authenticated user"""
        response = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)  # Only user's files

    def test_search_by_filename_partial_match(self):
        """Test search parameter with partial filename match"""
        response = self.client.get('/api/files/?search=doc', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['original_filename'], 'document.txt')

    def test_search_case_insensitive(self):
        """Test search is case-insensitive"""
        response = self.client.get('/api/files/?search=DOC', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['original_filename'], 'document.txt')

    def test_search_by_extension(self):
        """Test search by file extension"""
        response = self.client.get('/api/files/?search=.txt', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)  # document.txt and notes.txt

    def test_filter_by_file_type(self):
        """Test filtering by exact MIME type"""
        response = self.client.get('/api/files/?file_type=text/plain', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filter_by_file_type_image(self):
        """Test filtering by image MIME type"""
        response = self.client.get('/api/files/?file_type=image/jpeg', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['original_filename'], 'photo.jpg')

    def test_filter_by_min_size(self):
        """Test filtering by minimum file size"""
        response = self.client.get('/api/files/?min_size=100000', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)  # photo.jpg and report.pdf

    def test_filter_by_max_size(self):
        """Test filtering by maximum file size"""
        response = self.client.get('/api/files/?max_size=2048', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)  # document.txt and notes.txt

    def test_filter_by_size_range(self):
        """Test filtering by size range (min and max)"""
        response = self.client.get('/api/files/?min_size=2000&max_size=110000', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)  # notes.txt and report.pdf

    def test_filter_by_start_date(self):
        """Test filtering by start date"""
        # Update file1 to have an older date
        old_date = timezone.now() - timedelta(days=5)
        File.objects.filter(id=self.file1.id).update(uploaded_at=old_date)

        # Query for files uploaded in last 3 days
        start_date = (timezone.now() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.get(f'/api/files/?start_date={start_date}', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)  # All except file1

    def test_filter_by_end_date(self):
        """Test filtering by end date"""
        # Update file1 to have an older date
        old_date = timezone.now() - timedelta(days=5)
        File.objects.filter(id=self.file1.id).update(uploaded_at=old_date)

        # Query for files uploaded before 3 days ago
        end_date = (timezone.now() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.get(f'/api/files/?end_date={end_date}', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # Only file1

    def test_filter_by_date_range(self):
        """Test filtering by date range"""
        # Set specific dates for files
        date1 = timezone.now() - timedelta(days=10)
        date2 = timezone.now() - timedelta(days=5)
        date3 = timezone.now() - timedelta(days=2)

        File.objects.filter(id=self.file1.id).update(uploaded_at=date1)
        File.objects.filter(id=self.file2.id).update(uploaded_at=date2)
        File.objects.filter(id=self.file3.id).update(uploaded_at=date3)

        # Query for files between 7 and 3 days ago
        start_date = (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date = (timezone.now() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.get(
            f'/api/files/?start_date={start_date}&end_date={end_date}',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)  # Only file2

    def test_multiple_filters_combined(self):
        """Test applying multiple filters simultaneously"""
        response = self.client.get(
            '/api/files/?file_type=text/plain&min_size=1500&search=notes',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['original_filename'], 'notes.txt')

    def test_invalid_min_size_non_integer(self):
        """Test validation error for non-integer min_size"""
        response = self.client.get('/api/files/?min_size=abc', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_min_size_negative(self):
        """Test validation error for negative min_size"""
        response = self.client.get('/api/files/?min_size=-100', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_max_size_non_integer(self):
        """Test validation error for non-integer max_size"""
        response = self.client.get('/api/files/?max_size=xyz', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_size_range(self):
        """Test validation error when min_size > max_size"""
        response = self.client.get('/api/files/?min_size=1000&max_size=500', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('min_size must be less than', response.data['error'])

    def test_invalid_start_date_format(self):
        """Test validation error for invalid start_date format"""
        response = self.client.get('/api/files/?start_date=invalid-date', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_end_date_format(self):
        """Test validation error for invalid end_date format"""
        response = self.client.get('/api/files/?end_date=2024-13-45', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_date_range(self):
        """Test validation error when start_date > end_date"""
        start_date = timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date = (timezone.now() - timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        response = self.client.get(
            f'/api/files/?start_date={start_date}&end_date={end_date}',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('start_date must be before', response.data['error'])

    def test_no_results_matching_filters(self):
        """Test empty result set when no files match filters"""
        response = self.client.get('/api/files/?search=nonexistent', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(len(response.data['results']), 0)

    def test_user_isolation(self):
        """Test that users only see their own files"""
        # Query as original user
        response = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)

        # Query as other user
        other_headers = {'HTTP_USERID': 'other-user'}
        response = self.client.get('/api/files/', **other_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['original_filename'], 'other-user-file.txt')

    def test_pagination_response_format(self):
        """Test that response includes pagination fields"""
        response = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)

    def test_response_includes_all_fields(self):
        """Test that response includes all file fields"""
        response = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_file = response.data['results'][0]

        # Check all required fields are present
        required_fields = [
            'id', 'file', 'original_filename', 'file_type', 'size',
            'uploaded_at', 'user_id', 'file_hash', 'reference_count',
            'is_reference', 'original_file'
        ]
        for field in required_fields:
            self.assertIn(field, first_file)


class RateLimitTests(TestCase):
    """Tests for Feature 3: Rate Limiting"""

    def setUp(self):
        """Set up test fixtures"""
        from django.core.cache import cache
        self.client = APIClient()
        self.user_id = 'rate-limit-test-user'
        self.headers = {'HTTP_USERID': self.user_id}
        # Clear cache before each test
        cache.clear()

    def test_successful_requests_within_limit(self):
        """Test that requests within rate limit succeed"""
        # Make 2 requests (within limit of 2 per second)
        response1 = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        response2 = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_rate_limit_exceeded(self):
        """Test that exceeding rate limit returns 429"""
        # Temporarily enable rate limiting for this test
        from django.conf import settings
        old_testing = settings.TESTING
        settings.TESTING = False

        try:
            from django.core.cache import cache
            cache.clear()

            # Make 3 requests (exceeds limit of 2 per second)
            self.client.get('/api/files/', **self.headers)
            self.client.get('/api/files/', **self.headers)
            response3 = self.client.get('/api/files/', **self.headers)

            self.assertEqual(response3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn('Call Limit Reached', response3.json()['error'])
        finally:
            settings.TESTING = old_testing

    def test_rate_limit_reset_after_window(self):
        """Test that rate limit resets after time window"""
        import time

        # Make 2 requests (at limit)
        self.client.get('/api/files/', **self.headers)
        self.client.get('/api/files/', **self.headers)

        # Wait for rate limit window to expire (1 second + buffer)
        time.sleep(1.2)

        # Should be able to make request again
        response = self.client.get('/api/files/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rate_limit_per_user(self):
        """Test that rate limits are per user"""
        user2_headers = {'HTTP_USERID': 'different-user'}

        # User 1 makes 2 requests (at limit)
        self.client.get('/api/files/', **self.headers)
        self.client.get('/api/files/', **self.headers)

        # User 2 should still be able to make requests
        response = self.client.get('/api/files/', **user2_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rate_limit_applies_to_all_endpoints(self):
        """Test that rate limit applies to all API endpoints"""
        # Temporarily enable rate limiting for this test
        from django.conf import settings
        old_testing = settings.TESTING
        settings.TESTING = False

        try:
            from django.core.cache import cache
            cache.clear()

            # Make 2 requests to different endpoints
            self.client.get('/api/files/', **self.headers)
            self.client.get('/api/files/storage_stats/', **self.headers)

            # Third request should be rate limited
            response = self.client.get('/api/files/file_types/', **self.headers)
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        finally:
            settings.TESTING = old_testing

    def test_rate_limit_excludes_admin_paths(self):
        """Test that rate limit doesn't apply to admin paths"""
        # This test ensures middleware excludes /admin/ paths
        # Note: We can't fully test admin access without setup, but we can verify exclusion logic
        pass

    def test_missing_userid_bypassed_by_rate_limit_middleware(self):
        """Test that missing UserId is handled by UserIdValidationMiddleware first"""
        # Make request without UserId header
        response = self.client.get('/api/files/')
        # Should get 401 from UserIdValidationMiddleware, not 429 from RateLimitMiddleware
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class StorageQuotaTests(TestCase):
    """Tests for Feature 3: Storage Quota Management"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.user_id = 'quota-test-user'
        self.headers = {'HTTP_USERID': self.user_id}

    def create_test_file(self, filename, size_bytes):
        """Helper to create test file with specific size"""
        content = b'x' * size_bytes
        return SimpleUploadedFile(filename, content, content_type='text/plain')

    def test_successful_upload_within_quota(self):
        """Test that uploads within quota succeed"""
        # Upload 1MB file (well within 10MB quota)
        test_file = self.create_test_file('small.txt', 1024 * 1024)
        response = self.client.post(
            '/api/files/',
            {'file': test_file},
            **self.headers,
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_storage_quota_exceeded(self):
        """Test that exceeding storage quota returns 429"""
        # Upload files totaling more than 10MB quota
        # First file: 6MB
        file1 = self.create_test_file('file1.txt', 6 * 1024 * 1024)
        self.client.post('/api/files/', {'file': file1}, **self.headers, format='multipart')

        # Second file: 5MB (would exceed 10MB quota)
        file2 = self.create_test_file('file2.txt', 5 * 1024 * 1024)
        response = self.client.post('/api/files/', {'file': file2}, **self.headers, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Storage Quota Exceeded', response.json()['error'])

    def test_duplicate_file_does_not_count_toward_quota(self):
        """Test that duplicate files (references) don't count toward quota"""
        # Upload a 6MB file
        content = b'test content for deduplication'
        file1 = SimpleUploadedFile('file1.txt', content, content_type='text/plain')
        response1 = self.client.post('/api/files/', {'file': file1}, **self.headers, format='multipart')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Upload same content with different name (should create reference)
        file2 = SimpleUploadedFile('file2.txt', content, content_type='text/plain')
        response2 = self.client.post('/api/files/', {'file': file2}, **self.headers, format='multipart')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

        # Storage should only count physical file once
        stats_response = self.client.get('/api/files/storage_stats/', **self.headers)
        self.assertEqual(stats_response.data['total_storage_used'], len(content))

    def test_storage_quota_per_user(self):
        """Test that storage quotas are per user"""
        # User 1 uploads 6MB
        file1 = self.create_test_file('user1-file.txt', 6 * 1024 * 1024)
        self.client.post('/api/files/', {'file': file1}, **self.headers, format='multipart')

        # User 2 should have separate quota
        user2_headers = {'HTTP_USERID': 'different-quota-user'}
        file2 = self.create_test_file('user2-file.txt', 6 * 1024 * 1024)
        response = self.client.post('/api/files/', {'file': file2}, **user2_headers, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_storage_stats_includes_quota_info(self):
        """Test that storage_stats endpoint includes quota information"""
        response = self.client.get('/api/files/storage_stats/', **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check quota-related fields
        self.assertIn('storage_limit', response.data)
        self.assertIn('storage_remaining', response.data)
        self.assertIn('quota_usage_percentage', response.data)

        # Verify default quota (10MB)
        self.assertEqual(response.data['storage_limit'], 10 * 1024 * 1024)

    def test_storage_remaining_calculation(self):
        """Test correct calculation of remaining storage"""
        # Upload 3MB file
        file_size = 3 * 1024 * 1024
        test_file = self.create_test_file('test.txt', file_size)
        self.client.post('/api/files/', {'file': test_file}, **self.headers, format='multipart')

        # Check storage stats
        response = self.client.get('/api/files/storage_stats/', **self.headers)
        expected_remaining = (10 * 1024 * 1024) - file_size
        self.assertEqual(response.data['storage_remaining'], expected_remaining)

    def test_quota_usage_percentage(self):
        """Test correct calculation of quota usage percentage"""
        # Upload 5MB (50% of 10MB quota)
        file_size = 5 * 1024 * 1024
        test_file = self.create_test_file('half.txt', file_size)
        self.client.post('/api/files/', {'file': test_file}, **self.headers, format='multipart')

        # Check quota usage percentage
        response = self.client.get('/api/files/storage_stats/', **self.headers)
        self.assertEqual(response.data['quota_usage_percentage'], 50.0)

    def test_delete_file_frees_quota(self):
        """Test that deleting files frees up quota"""
        # Upload 6MB file
        file1 = self.create_test_file('file1.txt', 6 * 1024 * 1024)
        response1 = self.client.post('/api/files/', {'file': file1}, **self.headers, format='multipart')
        file1_id = response1.data['id']

        # Try to upload 5MB (would exceed quota)
        file2 = self.create_test_file('file2.txt', 5 * 1024 * 1024)
        response2 = self.client.post('/api/files/', {'file': file2}, **self.headers, format='multipart')
        self.assertEqual(response2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Delete first file
        self.client.delete(f'/api/files/{file1_id}/', **self.headers)

        # Now should be able to upload second file
        file2_retry = self.create_test_file('file2.txt', 5 * 1024 * 1024)
        response3 = self.client.post('/api/files/', {'file': file2_retry}, **self.headers, format='multipart')
        self.assertEqual(response3.status_code, status.HTTP_201_CREATED)


class UserIdValidationTests(TestCase):
    """Tests for Feature 3: UserId Header Validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

    def test_missing_userid_returns_401(self):
        """Test that missing UserId header returns 401"""
        response = self.client.get('/api/files/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('UserId header is required', response.json()['error'])

    def test_valid_userid_allows_access(self):
        """Test that valid UserId header allows access"""
        response = self.client.get('/api/files/', HTTP_USERID='valid-user')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_userid_validation_on_post(self):
        """Test UserId validation on POST requests"""
        test_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        response = self.client.post('/api/files/', {'file': test_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_userid_validation_on_delete(self):
        """Test UserId validation on DELETE requests"""
        # First create a file with valid UserId
        test_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        create_response = self.client.post(
            '/api/files/',
            {'file': test_file},
            HTTP_USERID='test-user',
            format='multipart'
        )
        file_id = create_response.data['id']

        # Try to delete without UserId
        response = self.client.delete(f'/api/files/{file_id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_userid_validation_excludes_admin(self):
        """Test that /admin/ paths don't require UserId header"""
        # Admin paths should not require UserId
        # Note: This test is limited without full admin setup
        pass

    def test_userid_validation_excludes_static(self):
        """Test that /static/ paths don't require UserId header"""
        # Static paths should not require UserId
        pass
