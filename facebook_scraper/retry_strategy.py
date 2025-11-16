"""
Retry strategy with circuit breaker pattern for robust error handling.
"""

import time
import random
import logging
from functools import wraps
from typing import Type, Tuple, Callable, Any
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'

        logger.info(
            f"CircuitBreaker initialized: threshold={failure_threshold}, "
            f"recovery={recovery_timeout}s"
        )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == 'OPEN':
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                time_remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                raise Exception(
                    f"Circuit breaker OPEN. Retry in {time_remaining:.1f}s "
                    f"({self.failure_count} failures)"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful execution."""
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info("Circuit breaker recovered - state: CLOSED")

        self.failure_count = 0

    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            if self.state != 'OPEN':
                self.state = 'OPEN'
                logger.error(
                    f"Circuit breaker OPEN after {self.failure_count} consecutive failures"
                )

    def reset(self):
        """Reset circuit breaker to initial state."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'
        logger.info("Circuit breaker reset")


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        RequestException,
        Timeout,
        ConnectionError,
    ),
):
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to delay
        retryable_exceptions: Tuple of exceptions that trigger retry

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = base_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retryable_exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) reached for {func.__name__}. "
                            f"Last error: {type(e).__name__}: {str(e)}"
                        )
                        raise

                    # Calculate exponential backoff delay
                    delay = min(base_delay * (exponential_base**attempt), max_delay)

                    # Add jitter (0-10% of delay)
                    if jitter:
                        jitter_amount = random.uniform(0, delay * 0.1)
                        delay += jitter_amount

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}. "
                        f"Error: {type(e).__name__}: {str(e)[:100]}. "
                        f"Retrying in {delay:.2f}s..."
                    )

                    time.sleep(delay)

                except Exception as e:
                    # Non-retryable exception - fail immediately
                    logger.error(
                        f"Non-retryable error in {func.__name__}: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    raise

        return wrapper

    return decorator


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def __repr__(self):
        return (
            f"RetryConfig(max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}, max_delay={self.max_delay})"
        )


def retry_with_config(config: RetryConfig, retryable_exceptions: Tuple[Type[Exception], ...]):
    """
    Retry decorator using RetryConfig.

    Args:
        config: RetryConfig instance
        retryable_exceptions: Exceptions that trigger retry

    Returns:
        Decorator function
    """
    return retry_with_backoff(
        max_retries=config.max_retries,
        base_delay=config.base_delay,
        max_delay=config.max_delay,
        exponential_base=config.exponential_base,
        jitter=config.jitter,
        retryable_exceptions=retryable_exceptions,
    )
