"""
Utility to manage API rate limiting for external services
"""
import time
import logging
from collections import deque
from datetime import datetime, timedelta
from threading import Lock

class RateLimiter:
    """
    Simple API rate limiter to avoid hitting rate limits on external APIs
    """
    
    def __init__(self, requests_per_minute=60, burst_limit=10):
        """
        Initialize rate limiter with specified limits
        
        Args:
            requests_per_minute: Maximum sustained requests per minute
            burst_limit: Maximum requests allowed in a burst
        """
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.request_times = deque(maxlen=max(requests_per_minute, burst_limit))
        self.lock = Lock()
    
    def wait_if_needed(self):
        """
        Wait if necessary to comply with rate limits
        
        Returns:
            Time waited in seconds
        """
        with self.lock:
            now = datetime.now()
            
            # First check if we're within burst limits
            if len(self.request_times) >= self.burst_limit:
                # Remove old requests outside our window
                while self.request_times and (now - self.request_times[0]).total_seconds() > 60:
                    self.request_times.popleft()
                
                # Check if we've hit our burst limit
                if len(self.request_times) >= self.burst_limit:
                    # Calculate how long to wait based on oldest request
                    wait_time = 60 - (now - self.request_times[0]).total_seconds()
                    if wait_time > 0:
                        logging.debug(f"Rate limit approaching, waiting {wait_time:.2f} seconds")
                        time.sleep(wait_time)
                        now = datetime.now()  # Update now after waiting
            
            # Now check sustained rate
            if self.request_times:
                # Calculate the rate we need to maintain (seconds between requests)
                min_interval = 60.0 / self.requests_per_minute
                
                # Check if we need to wait based on the most recent request
                if len(self.request_times) > 0:
                    last_request = self.request_times[-1]
                    elapsed = (now - last_request).total_seconds()
                    
                    if elapsed < min_interval:
                        wait_time = min_interval - elapsed
                        logging.debug(f"Throttling API requests, waiting {wait_time:.2f} seconds")
                        time.sleep(wait_time)
                        now = datetime.now()  # Update now after waiting
            
            # Record this request
            self.request_times.append(now)
            return 0  # Successfully waited if needed
