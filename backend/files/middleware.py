from django.http import JsonResponse
from django.core.cache import cache
from django.conf import settings
import time


class UserIdValidationMiddleware:
    """Middleware to validate UserId header presence"""

    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that don't require UserId header
        self.excluded_paths = ['/admin/', '/static/', '/media/']

    def __call__(self, request):
        # Skip validation for excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return self.get_response(request)

        # Check if request is for API endpoints
        if request.path.startswith('/api/'):
            user_id = request.headers.get('UserId')
            if not user_id:
                return JsonResponse(
                    {'error': 'UserId header is required'},
                    status=401
                )

        return self.get_response(request)


class RateLimitMiddleware:
    """Middleware to implement rate limiting per user"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.rate_limit_calls = getattr(settings, 'RATE_LIMIT_CALLS', 2)
        self.rate_limit_window = getattr(settings, 'RATE_LIMIT_WINDOW', 1)
        # Paths that don't require rate limiting
        self.excluded_paths = ['/admin/', '/static/', '/media/']

    def __call__(self, request):
        # Disable rate limiting during tests
        if getattr(settings, 'TESTING', False):
            return self.get_response(request)

        # Skip rate limiting for excluded paths
        if any(request.path.startswith(path) for path in self.excluded_paths):
            return self.get_response(request)

        # Apply rate limiting for API endpoints
        if request.path.startswith('/api/'):
            user_id = request.headers.get('UserId')

            # If no UserId, let UserIdValidationMiddleware handle it
            if not user_id:
                return self.get_response(request)

            # Check rate limit
            if not self._check_rate_limit(user_id):
                return JsonResponse(
                    {'error': 'Call Limit Reached'},
                    status=429
                )

        return self.get_response(request)

    def _check_rate_limit(self, user_id):
        """
        Check if user has exceeded rate limit using sliding window algorithm
        Returns True if request is allowed, False otherwise
        """
        cache_key = f'rate_limit_{user_id}'
        current_time = time.time()

        # Get list of timestamps for this user
        timestamps = cache.get(cache_key, [])

        # Remove timestamps outside the current window
        window_start = current_time - self.rate_limit_window
        timestamps = [ts for ts in timestamps if ts > window_start]

        # Check if limit exceeded
        if len(timestamps) >= self.rate_limit_calls:
            return False

        # Add current timestamp
        timestamps.append(current_time)

        # Store back in cache with expiry slightly longer than window
        cache.set(cache_key, timestamps, timeout=self.rate_limit_window + 1)

        return True
