"""
Enhanced error recovery with AWS 500-level error detection and operator notifications.

This module extends the retry strategy to:
1. Detect AWS 500-level errors specifically
2. Notify operators via SNS when 500-level errors occur
3. Pause execution on 500-level errors (raise PermanentError)
4. Resume execution after transient failures are resolved

Requirements: 19.2, 19.3, 19.4, 19.5, 25.1, 25.2, 25.3, 25.4, 25.5
"""

import os
from typing import Callable, Any, Optional, Dict
from functools import wraps
from botocore.exceptions import ClientError

from rosetta_zero.utils.retry import (
    RetryStrategy,
    TransientError,
    PermanentError,
    BehavioralDiscrepancyError,
    RetryExhaustedError
)
from rosetta_zero.utils.monitoring import SNSNotificationManager, EventBridgeManager
from rosetta_zero.utils.logging import logger, log_error


class AWS500LevelError(PermanentError):
    """AWS 500-level error requiring operator intervention."""
    
    def __init__(
        self,
        service: str,
        operation: str,
        error_code: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(f"AWS 500-level error in {service}.{operation}: {error_code}")
        self.service = service
        self.operation = operation
        self.error_code = error_code
        self.error_message = error_message
        self.context = context or {}


def is_aws_500_error(error: Exception) -> bool:
    """
    Check if error is an AWS 500-level error.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is AWS 500-level error
    """
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        
        # Check for 500-level HTTP status codes
        if 500 <= http_status < 600:
            return True
        
        # Check for known AWS 500-level error codes (but not throttling at 400 level)
        aws_500_errors = [
            'InternalServerError',
            'InternalFailure',
            'ServiceUnavailable',
            'InternalError',
        ]
        
        if error_code in aws_500_errors:
            return True
    
    return False


def is_transient_error(error: Exception) -> bool:
    """
    Check if error is transient and can be retried.
    
    Args:
        error: Exception to check
        
    Returns:
        True if error is transient
    """
    if isinstance(error, TransientError):
        return True
    
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Known transient AWS error codes
        transient_errors = [
            'RequestTimeout',
            'RequestTimeoutException',
            'PriorRequestNotComplete',
            'ConnectionError',
            'HTTPClientError',
            'Throttling',
            'ThrottledException',
            'ThrottlingException',
            'ProvisionedThroughputExceededException',
            'RequestLimitExceeded',
            'TooManyRequestsException',
        ]
        
        if error_code in transient_errors:
            return True
    
    return False


class EnhancedRetryStrategy(RetryStrategy):
    """
    Enhanced retry strategy with AWS 500-level error detection and SNS notifications.
    
    Requirements: 19.2, 19.3, 19.4, 19.5, 25.1, 25.2, 25.3, 25.4, 25.5
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: int = 2,
        max_delay_seconds: int = 60,
        sns_topic_arn: Optional[str] = None,
        component_name: Optional[str] = None
    ):
        """
        Initialize enhanced retry strategy.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay_seconds: Base delay for exponential backoff
            max_delay_seconds: Maximum delay between retries
            sns_topic_arn: SNS topic ARN for operator notifications
            component_name: Name of component for logging
        """
        super().__init__(max_retries, base_delay_seconds, max_delay_seconds)
        self.sns_manager = SNSNotificationManager(topic_arn=sns_topic_arn)
        self.event_manager = EventBridgeManager()
        self.component_name = component_name or 'unknown'
    
    def execute_with_retry(
        self,
        operation: Callable,
        *args,
        operation_name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute operation with enhanced retry logic.
        
        Handles:
        - Transient errors: Retry with exponential backoff (Requirement 19.2, 25.2, 25.3)
        - AWS 500-level errors: Notify operators via SNS, pause execution (Requirement 19.3, 19.4)
        - Permanent failures: Notify operators via SNS (Requirement 25.4, 25.5)
        - Behavioral discrepancies: Halt pipeline immediately
        
        Args:
            operation: Callable to execute
            *args: Positional arguments for operation
            operation_name: Name of operation for logging
            **kwargs: Keyword arguments for operation
            
        Returns:
            Result from successful operation execution
            
        Raises:
            AWS500LevelError: For AWS 500-level errors requiring operator intervention
            PermanentError: For permanent errors
            BehavioralDiscrepancyError: For test failures
            RetryExhaustedError: When all retry attempts are exhausted
        """
        op_name = operation_name or operation.__name__
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Log attempt (Requirement 25.1)
                if attempt > 0:
                    logger.info(
                        f"Retry attempt {attempt}/{self.max_retries} for {op_name}",
                        extra={
                            'component': self.component_name,
                            'operation': op_name,
                            'attempt': attempt,
                            'max_retries': self.max_retries,
                        }
                    )
                
                # Execute operation
                result = operation(*args, **kwargs)
                
                # Log success after retry (Requirement 19.5)
                if attempt > 0:
                    logger.info(
                        f"Operation {op_name} succeeded after {attempt} retries",
                        extra={
                            'component': self.component_name,
                            'operation': op_name,
                            'attempts': attempt,
                        }
                    )
                
                return result
                
            except ClientError as e:
                last_exception = e
                
                # Check for AWS 500-level errors (Requirement 19.3)
                if is_aws_500_error(e):
                    error_code = e.response.get('Error', {}).get('Code', '')
                    error_message = e.response.get('Error', {}).get('Message', '')
                    service = e.response.get('ResponseMetadata', {}).get('ServiceId', 'unknown')
                    
                    # Log error before notification (Requirement 25.1)
                    log_error(
                        component=self.component_name,
                        error_type='AWS500LevelError',
                        error_message=f"{service} {error_code}: {error_message}",
                        context={
                            'operation': op_name,
                            'attempt': attempt,
                            'error_code': error_code,
                            'service': service
                        }
                    )
                    
                    # Notify operators via SNS (Requirement 19.3)
                    try:
                        self.sns_manager.publish_aws_500_error_alert(
                            service=service,
                            operation=op_name,
                            error_code=error_code,
                            error_message=error_message,
                            context={
                                'component': self.component_name,
                                'attempt': attempt,
                                'max_retries': self.max_retries
                            }
                        )
                    except Exception as sns_error:
                        logger.error(
                            f"Failed to send SNS notification: {sns_error}",
                            extra={'component': self.component_name}
                        )
                    
                    # Publish error event to EventBridge (Requirement 25.5)
                    try:
                        self.event_manager.publish_error_event(
                            service=service,
                            error_code=error_code,
                            error_message=error_message,
                            context={
                                'component': self.component_name,
                                'operation': op_name,
                                'attempt': attempt
                            }
                        )
                    except Exception as event_error:
                        logger.error(
                            f"Failed to publish error event: {event_error}",
                            extra={'component': self.component_name}
                        )
                    
                    # Pause execution - raise permanent error (Requirement 19.4)
                    raise AWS500LevelError(
                        service=service,
                        operation=op_name,
                        error_code=error_code,
                        error_message=error_message,
                        context={
                            'component': self.component_name,
                            'attempt': attempt
                        }
                    )
                
                # Check for transient errors (Requirement 19.2, 25.2)
                elif is_transient_error(e):
                    if attempt < self.max_retries:
                        # Calculate delay with exponential backoff (Requirement 25.3)
                        delay = min(
                            self.base_delay_seconds * (2 ** attempt),
                            self.max_delay_seconds
                        )
                        
                        # Log retry scheduled (Requirement 25.1)
                        logger.warning(
                            f"Transient error in {op_name}, retrying in {delay}s",
                            extra={
                                'component': self.component_name,
                                'operation': op_name,
                                'attempt': attempt,
                                'delay_seconds': delay,
                                'error': str(e),
                                'error_type': type(e).__name__,
                            }
                        )
                        
                        # Wait before retry
                        import time
                        time.sleep(delay)
                    else:
                        # Max retries exceeded (Requirement 25.4)
                        logger.error(
                            f"Retry exhausted for {op_name} after {self.max_retries} attempts",
                            extra={
                                'component': self.component_name,
                                'operation': op_name,
                                'max_retries': self.max_retries,
                                'last_error': str(e),
                            }
                        )
                        
                        # Notify operators of permanent failure (Requirement 25.4)
                        try:
                            self.sns_manager.publish_operator_alert(
                                subject=f"Retry Exhausted in {self.component_name}",
                                message=f"Operation '{op_name}' failed after {self.max_retries} retries: {str(e)}",
                                severity="HIGH",
                                context={
                                    'component': self.component_name,
                                    'operation': op_name,
                                    'max_retries': self.max_retries,
                                    'error': str(e)
                                }
                            )
                        except Exception as sns_error:
                            logger.error(
                                f"Failed to send SNS notification: {sns_error}",
                                extra={'component': self.component_name}
                            )
                else:
                    # Non-transient ClientError - treat as permanent
                    logger.error(
                        f"Permanent error in {op_name}, not retrying",
                        extra={
                            'component': self.component_name,
                            'operation': op_name,
                            'error': str(e),
                            'error_type': type(e).__name__,
                        }
                    )
                    raise PermanentError(f"AWS error: {e}") from e
            
            except (PermanentError, BehavioralDiscrepancyError, AWS500LevelError) as e:
                # Don't retry permanent errors or behavioral discrepancies
                logger.error(
                    f"Permanent error in {op_name}, not retrying",
                    extra={
                        'component': self.component_name,
                        'operation': op_name,
                        'error': str(e),
                        'error_type': type(e).__name__,
                    }
                )
                raise
            
            except TransientError as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff (Requirement 25.3)
                    delay = min(
                        self.base_delay_seconds * (2 ** attempt),
                        self.max_delay_seconds
                    )
                    
                    # Log retry scheduled (Requirement 25.1)
                    logger.warning(
                        f"Transient error in {op_name}, retrying in {delay}s",
                        extra={
                            'component': self.component_name,
                            'operation': op_name,
                            'attempt': attempt,
                            'delay_seconds': delay,
                            'error': str(e),
                            'error_type': type(e).__name__,
                        }
                    )
                    
                    # Wait before retry
                    import time
                    time.sleep(delay)
                else:
                    # Max retries exceeded (Requirement 25.4)
                    logger.error(
                        f"Retry exhausted for {op_name} after {self.max_retries} attempts",
                        extra={
                            'component': self.component_name,
                            'operation': op_name,
                            'max_retries': self.max_retries,
                            'last_error': str(e),
                        }
                    )
            
            except Exception as e:
                # Unknown errors are treated as permanent
                logger.error(
                    f"Unknown error in {op_name}, not retrying",
                    extra={
                        'component': self.component_name,
                        'operation': op_name,
                        'error': str(e),
                        'error_type': type(e).__name__,
                    }
                )
                raise PermanentError(f"Unknown error: {e}") from e
        
        # All retries failed - notify operators (Requirement 25.4, 25.5)
        try:
            self.sns_manager.publish_operator_alert(
                subject=f"Permanent Failure in {self.component_name}",
                message=f"Operation '{op_name}' failed permanently after {self.max_retries} retries",
                severity="CRITICAL",
                context={
                    'component': self.component_name,
                    'operation': op_name,
                    'max_retries': self.max_retries,
                    'last_error': str(last_exception) if last_exception else 'Unknown'
                }
            )
        except Exception as sns_error:
            logger.error(
                f"Failed to send SNS notification: {sns_error}",
                extra={'component': self.component_name}
            )
        
        raise RetryExhaustedError(
            f"Operation {op_name} failed after {self.max_retries} retries",
            last_exception
        )


def with_enhanced_retry(
    max_retries: int = 3,
    base_delay_seconds: int = 2,
    max_delay_seconds: int = 60,
    component_name: Optional[str] = None
):
    """
    Decorator to add enhanced retry logic with AWS 500-level error handling.
    
    Requirements: 19.2, 19.3, 19.4, 19.5, 25.1, 25.2, 25.3, 25.4, 25.5
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay_seconds: Base delay for exponential backoff
        max_delay_seconds: Maximum delay between retries
        component_name: Name of component for logging
        
    Example:
        @with_enhanced_retry(max_retries=3, component_name='ingestion_engine')
        def my_function():
            # Function that may raise TransientError or AWS errors
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            strategy = EnhancedRetryStrategy(
                max_retries=max_retries,
                base_delay_seconds=base_delay_seconds,
                max_delay_seconds=max_delay_seconds,
                component_name=component_name or func.__name__
            )
            return strategy.execute_with_retry(
                func,
                *args,
                operation_name=func.__name__,
                **kwargs
            )
        return wrapper
    return decorator
