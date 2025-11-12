# File Vault - Features Documentation

This document describes the three implemented features for the Abnormal File Vault API.

---

## Feature 1: File Deduplication System

### Overview

Automatically detects and handles duplicate file uploads by storing references instead of duplicate physical files, optimizing storage efficiency.

### Implementation

- **Hash-based detection**: SHA-256 hash calculated for each uploaded file
- **Reference counting**: Original files track how many references point to them
- **Per-user deduplication**: Same file by different users stored separately
- **Smart deletion**: Physical file only deleted when all references are removed

### Key Files

- `backend/files/models.py`: Added fields (file_hash, is_reference, reference_count, original_file)
- `backend/files/utils.py`: `calculate_file_hash()` function
- `backend/files/views.py`: Deduplication logic in create/destroy methods

### Testing

**Automated Tests:**

```bash
cd backend
python manage.py test files.tests.FileDeduplicationTests
```

**Manual API Testing:**

```bash
# Upload original file
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@test.txt"

# Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "file_hash": "a665a45920422f9d417e4867efdc4fb8...",
  "is_reference": false,
  "reference_count": 1,
  "original_file": null
}

# Upload same file again (creates reference)
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@test_copy.txt"

# Response:
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "file_hash": "a665a45920422f9d417e4867efdc4fb8...",
  "is_reference": true,
  "reference_count": 1,
  "original_file": "550e8400-e29b-41d4-a716-446655440000"
}

# Check storage savings
curl -X GET http://localhost:8000/api/files/storage_stats/ -H "UserId: user1"

# Response:
{
  "user_id": "user1",
  "total_storage_used": 1024,
  "original_storage_used": 2048,
  "storage_savings": 1024,
  "savings_percentage": 50.0
}
```

---

## Feature 2: Search & Filtering System

### Overview

Enables efficient file retrieval through multiple search and filter parameters with validation and pagination.

### Implementation

- **Search**: Case-insensitive filename search using `icontains`
- **Filters**: file_type (MIME), size range (min/max), date range (start/end)
- **Validation**: Parameter validation with descriptive error messages
- **Performance**: Database indexes on file_type, uploaded_at, and user_id
- **Pagination**: 100 items per page

### Key Files

- `backend/files/views.py`: `get_queryset()` and `list()` methods
- `backend/files/models.py`: Database indexes for performance
- `backend/core/settings.py`: Pagination configuration

### Testing

**Automated Tests:**

```bash
cd backend
python manage.py test files.tests.SearchAndFilteringTests
```

**Manual API Testing:**

```bash
# Search by filename
curl -X GET "http://localhost:8000/api/files/?search=document" \
  -H "UserId: user1"

# Filter by file type
curl -X GET "http://localhost:8000/api/files/?file_type=text/plain" \
  -H "UserId: user1"

# Filter by size range (1KB to 1MB)
curl -X GET "http://localhost:8000/api/files/?min_size=1024&max_size=1048576" \
  -H "UserId: user1"

# Filter by date range
curl -X GET "http://localhost:8000/api/files/?start_date=2024-01-01T00:00:00Z&end_date=2024-12-31T23:59:59Z" \
  -H "UserId: user1"

# Combine multiple filters
curl -X GET "http://localhost:8000/api/files/?search=report&file_type=application/pdf&min_size=100000" \
  -H "UserId: user1"

# Response format:
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "original_filename": "report.pdf",
      "file_type": "application/pdf",
      "size": 102400,
      "uploaded_at": "2024-01-15T10:30:00.123456Z"
    }
  ]
}

# Get available file types
curl -X GET "http://localhost:8000/api/files/file_types/" \
  -H "UserId: user1"

# Response:
["text/plain", "image/jpeg", "application/pdf"]
```

**Query Parameters:**

- `search` - Filename search (case-insensitive)
- `file_type` - Exact MIME type match
- `min_size` - Minimum file size in bytes
- `max_size` - Maximum file size in bytes
- `start_date` - Files uploaded after (ISO 8601)
- `end_date` - Files uploaded before (ISO 8601)

---

## Feature 3: Call & Storage Limit Implementation

### Overview

Protects application health through rate limiting and storage quotas with per-user tracking.

### Implementation

**Rate Limiting:**

- Sliding window algorithm (2 calls per second default)
- Per-user tracking via cache backend
- Returns HTTP 429 "Call Limit Reached"

**Storage Quota:**

- 10MB per user default
- Deduplication-aware (references don't count)
- Returns HTTP 429 "Storage Quota Exceeded"

**UserId Validation:**

- All API requests require UserId header
- Returns HTTP 401 if missing

### Key Files

- `backend/files/middleware.py`: Rate limiting and UserId validation middleware
- `backend/core/settings.py`: Configurable limits and cache setup
- `backend/files/utils.py`: `check_storage_quota()` function
- `backend/files/views.py`: Storage enforcement in file upload

### Configuration

```python
# Environment variables (optional)
RATE_LIMIT_CALLS=2           # Calls per window
RATE_LIMIT_WINDOW=1          # Window in seconds
STORAGE_QUOTA_PER_USER=10485760  # 10MB in bytes
```

### Testing

**Automated Tests:**

```bash
cd backend
python manage.py test files.tests.RateLimitTests
python manage.py test files.tests.StorageQuotaTests
python manage.py test files.tests.UserIdValidationTests
```

**Manual API Testing:**

**1. UserId Validation:**

```bash
# Request without UserId (returns 401)
curl -X GET http://localhost:8000/api/files/

# Response:
{"error": "UserId header is required"}

# Request with UserId (succeeds)
curl -X GET http://localhost:8000/api/files/ -H "UserId: user1"

# Response: 200 OK with file list
```

**2. Rate Limiting:**

```bash
# Make 3 rapid requests (3rd will be rate limited)
curl -X GET http://localhost:8000/api/files/ -H "UserId: user1"  # 200 OK
curl -X GET http://localhost:8000/api/files/ -H "UserId: user1"  # 200 OK
curl -X GET http://localhost:8000/api/files/ -H "UserId: user1"  # 429

# Response on 3rd request:
{"error": "Call Limit Reached"}

# Wait 1+ second, then retry (succeeds)
sleep 2
curl -X GET http://localhost:8000/api/files/ -H "UserId: user1"  # 200 OK
```

**3. Storage Quota:**

```bash
# Check current storage stats
curl -X GET http://localhost:8000/api/files/storage_stats/ \
  -H "UserId: user1"

# Response:
{
  "user_id": "user1",
  "total_storage_used": 0,
  "original_storage_used": 0,
  "storage_savings": 0,
  "savings_percentage": 0.0,
  "storage_limit": 10485760,
  "storage_remaining": 10485760,
  "quota_usage_percentage": 0.0
}

# Upload file within quota (succeeds)
dd if=/dev/zero of=file.bin bs=1M count=5  # Create 5MB file
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@file.bin"  # 201 Created

# Upload file exceeding quota (fails)
dd if=/dev/zero of=large.bin bs=1M count=11  # Create 11MB file
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@large.bin"

# Response:
{"error": "Storage Quota Exceeded"}
```

**4. Deduplication + Quota:**

```bash
# Upload original file
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@test.txt"  # 201 Created

# Upload duplicate (creates reference, no quota impact)
curl -X POST http://localhost:8000/api/files/ \
  -H "UserId: user1" \
  -F "file=@test_copy.txt"  # 201 Created

# Check storage - only counts once
curl -X GET http://localhost:8000/api/files/storage_stats/ \
  -H "UserId: user1"

# Response shows storage_savings from deduplication
{
  "total_storage_used": 1024,
  "original_storage_used": 2048,
  "storage_savings": 1024,
  "savings_percentage": 50.0
}
```

---

## Running All Tests

**Test Suite:** All 53 tests passing ✅

- 8 FileDeduplicationTests
- 23 SearchAndFilteringTests
- 7 RateLimitTests
- 9 StorageQuotaTests
- 6 UserIdValidationTests

```bash
# Start Docker environment
docker-compose up --build -d

# Run all tests (53 tests)
docker-compose exec backend python manage.py test files

# Run specific test classes
docker-compose exec backend python manage.py test files.tests.FileDeduplicationTests
docker-compose exec backend python manage.py test files.tests.SearchAndFilteringTests
docker-compose exec backend python manage.py test files.tests.RateLimitTests
docker-compose exec backend python manage.py test files.tests.StorageQuotaTests
docker-compose exec backend python manage.py test files.tests.UserIdValidationTests

# View logs
docker-compose logs -f backend
```

**Note:** Rate limiting is automatically disabled during test execution via the `TESTING` flag in settings. This prevents rate limits from interfering with rapid test requests.

---

## API Endpoints Summary

| Endpoint                    | Method | Description                      | Required Header |
| --------------------------- | ------ | -------------------------------- | --------------- |
| `/api/files/`               | GET    | List files with optional filters | UserId          |
| `/api/files/`               | POST   | Upload file (with deduplication) | UserId          |
| `/api/files/{id}/`          | GET    | Get file details                 | UserId          |
| `/api/files/{id}/`          | DELETE | Delete file                      | UserId          |
| `/api/files/storage_stats/` | GET    | Get storage statistics           | UserId          |
| `/api/files/file_types/`    | GET    | Get available MIME types         | UserId          |

---

## Error Responses

| Status Code | Error Message               | Cause                    |
| ----------- | --------------------------- | ------------------------ |
| 401         | "UserId header is required" | Missing UserId header    |
| 429         | "Call Limit Reached"        | Rate limit exceeded      |
| 429         | "Storage Quota Exceeded"    | Storage quota exceeded   |
| 400         | Validation error message    | Invalid query parameters |

---

## Performance Considerations

- **Database Indexes**: Applied on user_id, file_hash, uploaded_at, file_type
- **Caching**: Rate limit data cached for fast lookups
- **Chunked Reading**: Files read in chunks for memory efficiency
- **Deduplication**: Reduces storage usage and improves performance
- **Pagination**: Limits response size to 100 items per page
