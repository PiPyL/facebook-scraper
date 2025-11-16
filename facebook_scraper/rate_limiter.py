"""
Adaptive rate limiter for Facebook scraping to avoid IP bans and throttling.
"""

import time
import random
import logging
import threading
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter with multiple strategies to avoid detection and bans.

    Features:
    - Adaptive delays based on error rates
    - Jitter to avoid pattern detection
    - Burst control
    - Automatic cooldown on throttling detection
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        burst_size: int = 3,
        cooldown_period: float = 60.0,
        adaptive: bool = True,
    ):
        """
        Initialize rate limiter.

        Args:
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            burst_size: Number of consecutive requests allowed
            cooldown_period: Cooldown time after throttling detection
            adaptive: Enable adaptive delay adjustment
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.burst_size = burst_size
        self.cooldown_period = cooldown_period
        self.adaptive = adaptive

        # Request tracking
        self.request_times = deque(maxlen=100)
        self.error_count = 0
        self.success_count = 0
        self.current_delay = min_delay
        self.last_request_time: Optional[float] = None
        self.lock = threading.Lock()

        # Throttling detection
        self.error_rate_threshold = 0.3  # 30% error rate triggers adjustment
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3

        logger.info(
            f"RateLimiter initialized: min={min_delay}s, max={max_delay}s, "
            f"burst={burst_size}, adaptive={adaptive}"
        )

    def wait(self):
        """Wait appropriate time before next request."""
        with self.lock:
            if self.last_request_time:
                elapsed = time.time() - self.last_request_time

                # Calculate dynamic delay
                delay = self._calculate_delay()

                # Add jitter to avoid pattern detection (0-20% of delay)
                jitter = random.uniform(0, delay * 0.2)
                total_delay = delay + jitter

                wait_time = total_delay - elapsed
                if wait_time > 0:
                    logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)

            self.last_request_time = time.time()
            self.request_times.append(self.last_request_time)

    def _calculate_delay(self) -> float:
        """
        Calculate adaptive delay based on error rate and recent activity.

        Returns:
            Delay in seconds
        """
        if not self.adaptive:
            return self.current_delay

        # If consecutive errors detected, increase delay significantly
        if self.consecutive_errors >= self.max_consecutive_errors:
            penalty_delay = min(self.current_delay * 2, self.max_delay * 2)
            logger.warning(
                f"Consecutive errors detected. Increasing delay to {penalty_delay:.2f}s"
            )
            return penalty_delay

        # Calculate error rate in recent requests
        total_recent = self.error_count + self.success_count
        if total_recent > 10:  # Need enough data
            error_rate = self.error_count / total_recent

            if error_rate > self.error_rate_threshold:
                # High error rate - increase delay
                new_delay = min(self.current_delay * 1.5, self.max_delay)
                if new_delay != self.current_delay:
                    logger.info(
                        f"Error rate {error_rate:.1%} > {self.error_rate_threshold:.1%}. "
                        f"Increasing delay to {new_delay:.2f}s"
                    )
                self.current_delay = new_delay

            elif error_rate < 0.1 and self.success_count > 20:
                # Low error rate with good history - can decrease delay
                new_delay = max(self.current_delay * 0.9, self.min_delay)
                if new_delay != self.current_delay:
                    logger.debug(f"Low error rate. Decreasing delay to {new_delay:.2f}s")
                self.current_delay = new_delay

        return self.current_delay

    def record_success(self):
        """Record successful request."""
        with self.lock:
            self.success_count += 1
            self.consecutive_errors = 0
            # Gradually decay error count on success
            self.error_count = max(0, self.error_count - 1)
            logger.debug(f"Success recorded. Total: {self.success_count}")

    def record_error(self, error_type: str = 'generic'):
        """
        Record failed request.

        Args:
            error_type: Type of error ('rate_limit', 'temporarily_banned', 'generic')
        """
        with self.lock:
            self.error_count += 1
            self.consecutive_errors += 1

            logger.warning(
                f"Error recorded: {error_type}. "
                f"Consecutive: {self.consecutive_errors}, Total: {self.error_count}"
            )

            # If rate limited or banned, enter cooldown
            if error_type in ['rate_limit', 'temporarily_banned']:
                self.current_delay = self.max_delay * 2
                logger.error(
                    f"Rate limit/ban detected. Entering cooldown for {self.cooldown_period}s"
                )
                time.sleep(self.cooldown_period)

    def reset(self):
        """Reset all counters."""
        with self.lock:
            self.error_count = 0
            self.success_count = 0
            self.consecutive_errors = 0
            self.current_delay = self.min_delay
            logger.info("Rate limiter reset")

    def get_stats(self) -> dict:
        """
        Get current statistics.

        Returns:
            Dictionary with rate limiter stats
        """
        with self.lock:
            total = self.error_count + self.success_count
            success_rate = (self.success_count / total * 100) if total > 0 else 0

            return {
                'success_count': self.success_count,
                'error_count': self.error_count,
                'consecutive_errors': self.consecutive_errors,
                'success_rate': success_rate,
                'current_delay': self.current_delay,
                'requests_in_window': len(self.request_times),
            }
