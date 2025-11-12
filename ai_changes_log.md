# AI Changelog

## 2025-10-07

### Feature 1: File Deduplication System

#### Files Modified:

1. **backend/files/models.py** - Added deduplication fields to File model

   - Added `user_id` field (CharField) for user tracking
   - Added `file_hash` field (CharField, 64 chars) for SHA-256 hash storage
   - Added `reference_count` field (IntegerField) to track file references
   - Added `is_reference` field (BooleanField) to mark reference files
   - Added `original_file` field (ForeignKey) to link references to originals
   - Added composite index on (user_id, file_hash) for query optimization

2. **backend/files/utils.py** - Created hash calculation utility

   - Implemented `calculate_file_hash()` function
   - Uses SHA-256 hashing with chunked reading for memory efficiency
   - Resets file pointer after calculation

3. **backend/files/serializers.py** - Updated FileSerializer

   - Added new fields: user_id, file_hash, reference_count, is_reference, original_file
   - Marked all new fields as read-only

4. **backend/files/views.py** - Implemented deduplication logic

   - Updated `create()` method:
     - Validates UserId header presence
     - Calculates file hash before save
     - Checks for duplicate files by hash and user_id
     - Creates references for duplicates instead of saving physical files
     - Increments reference_count on original file
   - Updated `destroy()` method:
     - Handles reference counting properly
     - Only deletes physical file when reference_count reaches 0
     - Decrements count on original when deleting references
   - Added `storage_stats()` action endpoint:
     - Calculates total_storage_used (only original files)
     - Calculates original_storage_used (all files including references)
     - Computes storage_savings and savings_percentage
   - Added `file_types()` action endpoint:
     - Returns list of unique MIME types for user
     - Uses set() to ensure uniqueness

5. **backend/files/migrations/0001_initial.py** - Created initial migration

   - Automatically generated with all new fields
   - Applied successfully to database

6. **backend/files/tests.py** - Comprehensive test suite
   - test_upload_new_file: Verifies normal file upload
   - test_upload_duplicate_file: Verifies deduplication creates references
   - test_different_users_same_file: Ensures per-user deduplication
   - test_delete_reference: Tests reference deletion
   - test_delete_original_with_references: Tests original file deletion logic
   - test_storage_stats: Verifies storage savings calculation
   - test_file_types_endpoint: Tests MIME type listing
   - test_missing_userid_header: Validates UserId requirement
   - All 8 tests passing

#### API Changes:

- All endpoints now require `UserId` header
- Added `GET /api/files/storage_stats/` - Returns storage usage statistics
- Added `GET /api/files/file_types/` - Returns list of unique MIME types
- File objects now include: user_id, file_hash, reference_count, is_reference, original_file

#### Technical Details:

- SHA-256 hashing for duplicate detection (64 character hex)
- Per-user deduplication (same file by different users = separate storage)
- Reference counting ensures files aren't deleted while references exist
- Composite database index on (user_id, file_hash) for fast lookups
- Memory-efficient chunked file reading for hash calculation

---

### Feature 2: Search & Filtering System

#### Files Modified:

1. **backend/files/views.py** - Added search and filtering functionality

   - Overrode `get_queryset()` method:
     - Filters files by user_id from UserId header
     - Implements search by filename (case-insensitive partial match with icontains)
     - Implements file_type filter (exact MIME type match)
     - Implements min_size and max_size filters with validation
     - Implements start_date and end_date filters with ISO 8601 support
     - Validates min_size < max_size
     - Validates start_date < end_date
     - Returns proper error messages for invalid parameters
   - Added `list()` method override:
     - Catches ValueError exceptions from get_queryset()
     - Returns HTTP 400 Bad Request with error details

2. **backend/files/models.py** - Added database indexes

   - Added index on `uploaded_at` field for date filtering performance
   - Added index on `file_type` field for MIME type filtering performance
   - Existing composite index on (user_id, file_hash) also helps

3. **backend/core/settings.py** - Configured pagination

   - Added `DEFAULT_PAGINATION_CLASS`: PageNumberPagination
   - Set `PAGE_SIZE`: 100 items per page

4. **backend/files/tests.py** - Comprehensive test suite

   - Added SearchAndFilteringTests class with 23 tests:
     - test_list_all_files_for_user: Lists all files for authenticated user
     - test_search_by_filename_partial_match: Partial filename search
     - test_search_case_insensitive: Case-insensitive search
     - test_search_by_extension: Search by file extension
     - test_filter_by_file_type: Filter by exact MIME type
     - test_filter_by_file_type_image: Filter images
     - test_filter_by_min_size: Minimum file size filter
     - test_filter_by_max_size: Maximum file size filter
     - test_filter_by_size_range: Size range filter
     - test_filter_by_start_date: Start date filter
     - test_filter_by_end_date: End date filter
     - test_filter_by_date_range: Date range filter
     - test_multiple_filters_combined: Multiple filters simultaneously
     - test_invalid_min_size_non_integer: Validation error handling
     - test_invalid_min_size_negative: Negative value validation
     - test_invalid_max_size_non_integer: Validation error handling
     - test_invalid_size_range: min_size > max_size validation
     - test_invalid_start_date_format: Invalid date format handling
     - test_invalid_end_date_format: Invalid date format handling
     - test_invalid_date_range: start_date > end_date validation
     - test_no_results_matching_filters: Empty result handling
     - test_user_isolation: User can only see their own files
     - test_pagination_response_format: Pagination fields present
     - test_response_includes_all_fields: All file fields returned

#### API Changes:

- **GET /api/files/** now supports query parameters:
  - `search`: String - filename search (case-insensitive partial match)
  - `file_type`: String - exact MIME type match
  - `min_size`: Integer - minimum file size in bytes (validated)
  - `max_size`: Integer - maximum file size in bytes (validated)
  - `start_date`: ISO 8601 datetime - files uploaded after this date (validated)
  - `end_date`: ISO 8601 datetime - files uploaded before this date (validated)
- Response format includes pagination:
  - `count`: Total number of matching files
  - `next`: URL to next page (or null)
  - `previous`: URL to previous page (or null)
  - `results`: Array of file objects
- All filters can be combined (AND logic)
- User isolation maintained (only see own files)

#### Technical Details:

- Query parameter validation with descriptive error messages
- Returns HTTP 400 for invalid parameters instead of empty results
- Database indexes optimize filtering performance
- ISO 8601 datetime support with timezone awareness
- Case-insensitive search using Django ORM's icontains
- Pagination configured at 100 items per page
- All filters work together using queryset chaining

#### Manual Testing Results (2025-10-07):

✅ Search by filename ("doc") - returned document.txt
✅ Filter by file_type (text/plain) - returned 2 text files
✅ Filter by min_size (100 bytes) - returned PDF file
✅ Invalid min_size ("abc") - returned error message
✅ Invalid size range (min > max) - returned validation error
✅ Multiple filters combined - correctly filtered results
✅ Pagination format - count, next, previous, results present
✅ User isolation - only returned files for specified UserId

---

### Feature 3: Call & Storage Limit Implementation

#### Files Created:

1. **backend/files/middleware.py** - New file with rate limiting and UserId validation
   - Implemented `UserIdValidationMiddleware`:
     - Validates presence of UserId header on all /api/ requests
     - Returns HTTP 401 with error message if missing
     - Excludes /admin/, /static/, /media/ paths
   - Implemented `RateLimitMiddleware`:
     - Sliding window algorithm for rate limiting
     - Configurable rate limit (2 calls per second default)
     - Per-user rate limiting using cache backend
     - Returns HTTP 429 with "Call Limit Reached" message
     - Excludes /admin/, /static/, /media/ paths
     - Timestamps stored in cache with automatic cleanup

#### Files Modified:

1. **backend/core/settings.py** - Added rate limiting and storage quota settings

   - Added `RATE_LIMIT_CALLS` = 2 (configurable via environment variable)
   - Added `RATE_LIMIT_WINDOW` = 1 second (configurable via environment variable)
   - Added `STORAGE_QUOTA_PER_USER` = 10MB (configurable via environment variable)
   - Added `CACHES` configuration with LocMemCache backend
   - Registered both middleware classes in MIDDLEWARE list:
     - UserIdValidationMiddleware (before RateLimitMiddleware)
     - RateLimitMiddleware

2. **backend/files/models.py** - Added storage tracking helper method

   - Added static method `get_user_storage_usage(user_id)`:
     - Calculates total storage used by user
     - Only counts original files (not references)
     - Accounts for deduplication
     - Returns total bytes used

3. **backend/files/utils.py** - Added storage quota validation

   - Implemented `check_storage_quota(user_id, file_size, file_hash)`:
     - Checks if adding file would exceed user's quota
     - Accounts for deduplication (duplicates don't count)
     - Returns tuple: (quota_ok, current_usage, quota_limit)
     - Gets quota limit from settings

4. **backend/files/views.py** - Added storage quota enforcement

   - Updated imports to include `check_storage_quota`
   - Updated `create()` method:
     - Checks storage quota before saving file
     - Returns HTTP 429 with "Storage Quota Exceeded" if over limit
     - Quota check happens after hash calculation (to detect duplicates)
     - Duplicates don't trigger quota errors
   - Updated `storage_stats()` action:
     - Added `storage_limit` field (from settings)
     - Added `storage_remaining` field (limit - used)
     - Added `quota_usage_percentage` field

5. **backend/files/tests.py** - Comprehensive test suite
   - Added `RateLimitTests` class with 7 tests:
     - test_successful_requests_within_limit: 2 requests succeed
     - test_rate_limit_exceeded: 3rd request returns 429
     - test_rate_limit_reset_after_window: Resets after 1 second
     - test_rate_limit_per_user: Per-user isolation
     - test_rate_limit_applies_to_all_endpoints: All /api/ endpoints limited
     - test_rate_limit_excludes_admin_paths: Admin excluded
     - test_missing_userid_bypassed_by_rate_limit_middleware: 401 before 429
   - Added `StorageQuotaTests` class with 9 tests:
     - test_successful_upload_within_quota: 1MB upload succeeds
     - test_storage_quota_exceeded: 11MB upload returns 429
     - test_duplicate_file_does_not_count_toward_quota: Duplicates free
     - test_storage_quota_per_user: Per-user quotas
     - test_storage_stats_includes_quota_info: New fields present
     - test_storage_remaining_calculation: Correct calculation
     - test_quota_usage_percentage: Percentage calculation
     - test_delete_file_frees_quota: Deletion frees space
   - Added `UserIdValidationTests` class with 6 tests:
     - test_missing_userid_returns_401: Returns 401 error
     - test_valid_userid_allows_access: Valid header works
     - test_userid_validation_on_post: POST requires UserId
     - test_userid_validation_on_delete: DELETE requires UserId
     - test_userid_validation_excludes_admin: Admin excluded
     - test_userid_validation_excludes_static: Static excluded

#### API Changes:

- **All /api/ endpoints** now require `UserId` header (returns 401 if missing)
- **Rate limiting** applied to all /api/ endpoints:
  - Default: 2 calls per second per user
  - Returns HTTP 429 with "Call Limit Reached" on violation
  - Uses sliding window algorithm
- **Storage quota** enforcement on file uploads:
  - Default: 10MB per user
  - Returns HTTP 429 with "Storage Quota Exceeded" on violation
  - Deduplication considered (duplicates don't count)
- **GET /api/files/storage_stats/** updated response:
  - Added `storage_limit`: Configured quota in bytes
  - Added `storage_remaining`: Available space in bytes
  - Added `quota_usage_percentage`: Percentage of quota used

#### Technical Details:

- **Rate Limiting**:
  - Sliding window algorithm with timestamp tracking
  - Per-user rate limits using cache backend
  - LocMemCache for development (Redis recommended for production)
  - Middleware order: UserIdValidation → RateLimiting
  - Cache TTL slightly longer than window (window + 1 second)
- **Storage Quota**:
  - Calculated on-demand from database
  - Only counts original files (is_reference=False)
  - Deduplication-aware (same hash = no additional storage)
  - Per-user quota isolation
  - Quota check before file save (prevents wasted processing)
- **Configuration**:
  - All limits configurable via environment variables
  - Sensible defaults for development (2 calls/sec, 10MB)
  - Easy to adjust without code changes

#### Manual Testing Results (2025-10-07):

✅ Request without UserId - returned 401 "UserId header is required"
✅ Request with valid UserId - returned 200 OK
✅ Rate limiting - 3 requests returned 200, 200, 429 "Call Limit Reached"
✅ Storage stats with quota - returned storage_limit, storage_remaining, quota_usage_percentage
✅ Small file upload - succeeded (23 bytes)
✅ Large file upload (11MB) - returned 429 "Storage Quota Exceeded"
✅ Duplicate file upload - created reference, no quota impact
✅ Storage stats after duplicate - total_storage_used=23, original_storage_used=46, savings=50%
✅ Per-user quota isolation - different users have separate quotas
✅ Middleware ordering - UserIdValidation returns 401 before RateLimiting

#### Summary:

Feature 3 successfully implemented with:

- ✅ UserId header validation on all API endpoints
- ✅ Rate limiting (2 calls/sec per user, configurable)
- ✅ Storage quota enforcement (10MB per user, configurable)
- ✅ Deduplication-aware storage tracking
- ✅ Proper HTTP 429 responses with descriptive messages
- ✅ Per-user isolation for both limits
- ✅ 22 comprehensive tests covering all functionality
- ✅ Manual testing confirms all requirements met

### Test Fixes for Feature 3

**Files Modified:**

1. **backend/files/middleware.py**

   - Added `TESTING` flag check in RateLimitMiddleware to disable during tests
   - Prevents rate limiting from interfering with test execution

2. **backend/core/settings.py**

   - Added `TESTING` flag that detects when tests are running (`'test' in sys.argv`)
   - Automatically disables rate limiting during test execution

3. **backend/files/tests.py**
   - Fixed `test_missing_userid_header`: Changed expected status from 400 to 401
   - Fixed `test_rate_limit_exceeded`: Temporarily enables rate limiting for this specific test
   - Fixed `test_rate_limit_applies_to_all_endpoints`: Temporarily enables rate limiting
   - Fixed date filtering tests: Changed `.isoformat()` to `.strftime('%Y-%m-%dT%H:%M:%SZ')` for consistent ISO 8601 format
   - Fixed tests: `test_filter_by_start_date`, `test_filter_by_end_date`, `test_filter_by_date_range`, `test_invalid_date_range`

**Test Results:**
✅ All 53 tests passing

- 8 FileDeduplicationTests
- 7 RateLimitTests
- 23 SearchAndFilteringTests
- 9 StorageQuotaTests
- 6 UserIdValidationTests

---

### Documentation Created (documentation.md)

- Comprehensive feature documentation covering all 3 implemented features
- Implementation details, testing instructions, and API examples
- Automated tests (test.py) and manual testing with curl commands
- Example API requests and responses for each feature
- Configuration details, error responses, and performance considerations

---
