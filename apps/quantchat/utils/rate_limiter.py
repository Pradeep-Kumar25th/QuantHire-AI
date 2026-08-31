"""
Rate Limiter
============

Prevents API rate limit errors with throttling and retry logic.
"""

import time
from collections import deque
from threading import Lock
from ..config.logging_config import setup_logger
from ..config.settings import API_MAX_REQUESTS_PER_MINUTE, API_MIN_INTERVAL_SECONDS

logger = setup_logger("rate_limiter")

class RateLimiter:
    """
    Rate limiter to prevent 429 errors.
    """
    
    def __init__(self):
        self.request_times = deque()
        self.lock = Lock()
        self.min_interval = API_MIN_INTERVAL_SECONDS
        self.max_per_minute = API_MAX_REQUESTS_PER_MINUTE
    
    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        with self.lock:
            now = time.time()
            
            # Remove old requests (older than 1 minute)
            while self.request_times and now - self.request_times[0] > 60:
                self.request_times.popleft()
            
            # Check if we're at limit
            if len(self.request_times) >= self.max_per_minute:
                wait_time = 60 - (now - self.request_times[0])
                if wait_time > 0:
                    logger.warning(f"Rate limit approaching, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
            
            # Enforce minimum interval
            if self.request_times:
                last_request = self.request_times[-1]
                elapsed = now - last_request
                if elapsed < self.min_interval:
                    time.sleep(self.min_interval - elapsed)
            
            # Record this request
            self.request_times.append(time.time())
