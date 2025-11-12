# Feature 3: Call & Storage Limit Implementation

## Objective

Protect the application's health by programmatically limiting the number of API calls a particular user can make per second and by limiting the amount of file storage space used per user.

## Requirements Summary

### User Identification

- Each API request must be traceable/trackable to a user
- Use HTTP Header called `UserId` to pass in a userId
- All API endpoints must require and validate the UserId header

### API Rate Limiting

- Limit API calls by a particular user to **2 calls per second** (default)
- Both rate (x) and time window (n seconds) should be easily configurable
- Return HTTP 429 with message "Call Limit Reached" when limit is exceeded
- Rate limit should apply across all API endpoints

### Storage Quota Management

- Track the total size of all files stored by each user
- Reject file uploads that would exceed user's storage limit of **10MB per user** (default)
- Storage limit should be easily configurable
- Return HTTP 429 with message "Storage Quota Exceeded" when limit is reached
- Storage tracking must account for file deduplication (only count actual storage used)

## Step-by-Step Implementation Plan

### Step 1: Create Configuration Settings

**File: `backend/core/settings.py`**

- Add configurable settings for rate limiting:
  - `RATE_LIMIT_CALLS` = 2 (calls per window)
  - `RATE_LIMIT_WINDOW` = 1 (seconds)
- Add configurable setting for storage:
  - `STORAGE_QUOTA_PER_USER` = 10 _ 1024 _ 1024 (10MB in bytes)

### Step 2: Create Rate Limiting Middleware

**File: `backend/files/middleware.py` (new file)**

- Create `RateLimitMiddleware` class
- Extract `UserId` from request headers
- Implement rate limiting logic using cache backend (Django cache framework)
- Track API calls per user with timestamps
- Return 429 response with "Call Limit Reached" when limit exceeded
- Use Redis or Django's cache framework for storing rate limit data

### Step 3: Create UserId Authentication/Validation

**File: `backend/files/middleware.py` or `backend/files/authentication.py`**

- Create middleware or DRF authentication class to validate UserId header
- Ensure UserId header is present in all requests
- Return 401/403 if UserId is missing
- Attach user_id to request object for easy access in views

### Step 4: Update File Model for Storage Tracking

**File: `backend/files/models.py`**

- Ensure `user_id` field exists in File model (already added in feature 1)
- Add helper method to calculate user's total storage usage
- Consider caching storage calculations for performance

### Step 5: Create Storage Quota Validation Utility

**File: `backend/files/utils.py`**

- Create function `check_storage_quota(user_id, file_size)`
- Calculate current storage used by user (accounting for deduplication)
- Check if adding new file would exceed quota
- Return boolean or raise exception with appropriate message

### Step 6: Update FileViewSet for Storage Enforcement

**File: `backend/files/views.py`**

- In `create()` method (file upload), call storage quota check before saving
- Calculate file size from uploaded file
- If quota exceeded, return 429 response with "Storage Quota Exceeded"
- Only enforce quota on actual file uploads (not references/duplicates)

### Step 7: Update Storage Stats Endpoint

**File: `backend/files/views.py`**

- Update `storage_stats` action to include:
  - `storage_limit`: The configured storage quota
  - `storage_remaining`: Available storage space
  - Percentage of quota used

### Step 8: Register Middleware

**File: `backend/core/settings.py`**

- Add `RateLimitMiddleware` to `MIDDLEWARE` list
- Add `UserIdValidationMiddleware` to `MIDDLEWARE` list
- Ensure proper ordering (validation before rate limiting)

### Step 9: Configure Cache Backend for Rate Limiting

**File: `backend/core/settings.py`**

- Configure Django cache backend (default cache or Redis)
- For development: use `LocMemCache`
- For production: recommend Redis for distributed rate limiting

### Step 10: Update API Tests

**File: `backend/files/tests.py`**

- Add test cases for rate limiting:
  - Test successful requests within limit
  - Test 429 response when limit exceeded
  - Test rate limit reset after time window
- Add test cases for storage quota:
  - Test successful upload within quota
  - Test 429 response when quota exceeded
  - Test storage calculation with deduplication
- Add test cases for UserId header validation:
  - Test missing UserId returns 401/403
  - Test valid UserId passes through

### Step 11: Perform manual API testing

## Technical Considerations

### Rate Limiting Strategy

- Use sliding window algorithm for accurate rate limiting
- Store timestamps of recent requests in cache with user_id as key
- Clean up old timestamps outside the time window
- Use atomic cache operations to prevent race conditions

### Storage Calculation

- When calculating storage for deduplication:
  - Only count physical file size once per unique file_hash
  - References don't add to storage count
- Cache storage totals per user and invalidate on file upload/delete
- Use database aggregation queries for accuracy

### Performance Optimization

- Use database indexes on user_id and file_hash fields
- Implement caching for storage calculations
- Consider async tasks for storage recalculation if needed
- Use select_related/prefetch_related for efficient queries

### Error Handling

- Ensure 429 responses are properly formatted
- Include retry-after headers for rate limiting
- Log rate limit violations for monitoring
- Handle edge cases (concurrent requests, cache failures)

## Definition of Done

- [ ] Rate limiting middleware implemented and working
- [ ] UserId header validation in place
- [ ] Storage quota enforcement on file uploads
- [ ] Configurable settings for both limits
- [ ] Proper 429 error responses with correct messages
- [ ] Storage stats endpoint updated with quota information
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Works correctly with deduplication feature
