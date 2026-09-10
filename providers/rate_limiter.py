import time
import random
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, min_delay: float = settings.MIN_REQUEST_DELAY_SEC, max_delay: float = settings.MAX_REQUEST_DELAY_SEC):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0.0
        self.consecutive_errors = 0

    def wait(self):
        """Ensures minimum jitter delay between requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        target_delay = random.uniform(self.min_delay, self.max_delay)

        # Exponential backoff if consecutive errors occur
        if self.consecutive_errors > 0:
            extra_backoff = min(60.0, (2 ** self.consecutive_errors) * 2.0)
            target_delay += extra_backoff
            logger.warning(f"RateLimiter applying backoff of {extra_backoff:.1f}s (consecutive errors: {self.consecutive_errors})")

        if elapsed < target_delay:
            sleep_time = target_delay - elapsed
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def record_success(self):
        if self.consecutive_errors > 0:
            logger.info("RateLimiter reset error backoff after success.")
        self.consecutive_errors = 0

    def record_error(self):
        self.consecutive_errors += 1
        logger.warning(f"RateLimiter recorded error count: {self.consecutive_errors}")

rate_limiter = RateLimiter()
