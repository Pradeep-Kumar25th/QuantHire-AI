"""
Retry Logic with Exponential Backoff
====================================
Enterprise-grade retry mechanism with circuit breaker pattern.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

from agents.jd_generation.config import JDGenerationConfig, get_config
from agents.jd_generation.exceptions import JDGenerationError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add jitter to delay
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
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
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute function with circuit breaker.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if self.state == "open":
            if self._should_attempt_recovery():
                self.state = "half_open"
                logger.info("Circuit breaker: Attempting recovery (half-open)")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open. "
                    f"Last failure: {self.last_failure_time}. "
                    f"Recovery timeout: {self.recovery_timeout}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_recovery(self) -> bool:
        """Check if recovery should be attempted."""
        if self.last_failure_time is None:
            return True
        
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == "half_open":
            logger.info("Circuit breaker: Recovery successful, closing circuit")
            self.state = "closed"
            self.failure_count = 0
        elif self.state == "closed":
            self.failure_count = 0
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker: Opened after {self.failure_count} failures. "
                f"Will attempt recovery after {self.recovery_timeout}s"
            )


class CircuitBreakerOpenError(JDGenerationError):
    """Raised when circuit breaker is open."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="CIRCUIT_BREAKER_OPEN",
            retryable=False,
        )


def retry_with_backoff(
    retry_config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        retry_config: Retry configuration
        retryable_exceptions: Exceptions that should trigger retry
        on_retry: Callback function called on each retry
        
    Returns:
        Decorated function
    """
    if retry_config is None:
        config = get_config()
        retry_config = RetryConfig(
            max_retries=config.max_retries,
            initial_delay=config.retry_delay,
        )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(retry_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if error is retryable
                    if isinstance(e, JDGenerationError) and not e.retryable:
                        logger.debug(f"Error is not retryable: {e}")
                        raise
                    
                    if attempt < retry_config.max_retries:
                        delay = _calculate_delay(
                            attempt,
                            retry_config.initial_delay,
                            retry_config.max_delay,
                            retry_config.exponential_base,
                            retry_config.jitter,
                        )
                        
                        logger.warning(
                            f"Attempt {attempt + 1}/{retry_config.max_retries + 1} failed: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        
                        if on_retry:
                            on_retry(e, attempt + 1)
                        
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {retry_config.max_retries + 1} attempts failed. "
                            f"Last error: {e}"
                        )
                        raise
            
            # Should never reach here, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic failed unexpectedly")
        
        return wrapper
    
    return decorator


def _calculate_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
) -> float:
    """
    Calculate delay for exponential backoff.
    
    Args:
        attempt: Current attempt number (0-indexed)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add jitter
        
    Returns:
        Delay in seconds
    """
    delay = initial_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        import random
        jitter_amount = delay * 0.1  # 10% jitter
        delay += random.uniform(-jitter_amount, jitter_amount)
        delay = max(0, delay)  # Ensure non-negative
    
    return delay

