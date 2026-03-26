"""Retry strategy with exponential backoff."""

import time
import logging
from typing import Callable, Any, Optional
from functools import wraps


logger = logging.getLogger(__name__)


class TransientError(Exception):
    """Temporary failure that can be retried."""
    pass


class PermanentError(Exception):
    """Failure requiring operator intervention."""
    pass


class BehavioralDiscrepancyError(Exception):
    """Test failure indicating implementation differences."""
    pass


class RetryExhaustedError(Exception):
    """All retry attempts have been exhausted."""
    
    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


class RetryStrategy:
    """Exponential backoff retry strategy."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: int = 2,
        max_delay_seconds: int = 60
    ):
        """
        Initialize retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay_seconds: Base delay for exponential backoff
            max_delay_seconds: Maximum delay between retries
        """
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
    
    def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute operation with exponential backoff retry.
        
        Args:
            operation: Callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result from successful operation execution
            
        Raises:
            PermanentError: For errors that should not be retried
            BehavioralDiscrepancyError: For test failures
            RetryExhaustedError: When all retry attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Log attempt
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt}/{self.max_retries} for {operation.__name__}",
                        extra={
                            'operation': operation.__name__,
                            'attempt': attempt,
                            'max_retries': self.max_retries,
                        }
                    )
                
                # Execute operation
                result = operation(*args, **kwargs)
                
                # Log success after retry
                if attempt > 0:
                    logger.info(
                        f"Operation {operation.__name__} succeeded after {attempt} retries",
                        extra={
                            'operation': operation.__name__,
                            'attempts': attempt,
                        }
                    )
                
                return result
                
            except TransientError as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(
                        self.base_delay_seconds * (2 ** attempt),
                        self.max_delay_seconds
                    )
                    
                    # Log retry scheduled
                    logger.warning(
                        f"Transient error in {operation.__name__}, retrying in {delay}s",
                        extra={
                            'operation': operation.__name__,
                            'attempt': attempt,
                            'delay_seconds': delay,
                            'error': str(e),
                            'error_type': type(e).__name__,
                        }
                    )
                    
                    # Wait before retry
                    time.sleep(delay)
                else:
                    # Max retries exceeded
                    logger.error(
                        f"Retry exhausted for {operation.__name__} after {self.max_retries} attempts",
                        extra={
                            'operation': operation.__name__,
                            'max_retries': self.max_retries,
                            'last_error': str(e),
                        }
                    )
            
            except (PermanentError, BehavioralDiscrepancyError) as e:
                # Don't retry permanent errors or behavioral discrepancies
                logger.error(
                    f"Permanent error in {operation.__name__}, not retrying",
                    extra={
                        'operation': operation.__name__,
                        'error': str(e),
                        'error_type': type(e).__name__,
                    }
                )
                raise
            
            except Exception as e:
                # Unknown errors are treated as permanent
                logger.error(
                    f"Unknown error in {operation.__name__}, not retrying",
                    extra={
                        'operation': operation.__name__,
                        'error': str(e),
                        'error_type': type(e).__name__,
                    }
                )
                raise PermanentError(f"Unknown error: {e}") from e
        
        # All retries failed
        raise RetryExhaustedError(
            f"Operation {operation.__name__} failed after {self.max_retries} retries",
            last_exception
        )


def with_retry(
    max_retries: int = 3,
    base_delay_seconds: int = 2,
    max_delay_seconds: int = 60
):
    """
    Decorator to add retry logic to a function.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay_seconds: Base delay for exponential backoff
        max_delay_seconds: Maximum delay between retries
        
    Example:
        @with_retry(max_retries=3)
        def my_function():
            # Function that may raise TransientError
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            strategy = RetryStrategy(
                max_retries=max_retries,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds
            )
            return strategy.execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


def log_retry_attempt(operation_name: str, attempt: int):
    """Log a retry attempt."""
    logger.info(
        f"Retry attempt for {operation_name}",
        extra={
            'operation': operation_name,
            'attempt': attempt,
        }
    )


def log_retry_success(operation_name: str, attempts: int):
    """Log successful retry."""
    logger.info(
        f"Operation {operation_name} succeeded after retries",
        extra={
            'operation': operation_name,
            'attempts': attempts,
        }
    )


def log_retry_scheduled(operation_name: str, attempt: int, delay: float, error: str):
    """Log scheduled retry."""
    logger.warning(
        f"Scheduling retry for {operation_name}",
        extra={
            'operation': operation_name,
            'attempt': attempt,
            'delay_seconds': delay,
            'error': error,
        }
    )


def log_retry_exhausted(operation_name: str, error: str):
    """Log retry exhaustion."""
    logger.error(
        f"Retry exhausted for {operation_name}",
        extra={
            'operation': operation_name,
            'error': error,
        }
    )


def log_permanent_error(operation_name: str, error: str):
    """Log permanent error."""
    logger.error(
        f"Permanent error in {operation_name}",
        extra={
            'operation': operation_name,
            'error': error,
        }
    )
