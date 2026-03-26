"""
Error handling for Hostile Auditor Lambda.

Implements retry logic and error classification for test generation failures.
"""

import boto3
from aws_lambda_powertools import Logger

from rosetta_zero.utils.retry import (
    RetryStrategy,
    TransientError,
    PermanentError
)

logger = Logger(service="hostile-auditor-error-handling")

# Initialize SNS client for operator notifications
sns_client = boto3.client('sns')


class TestGenerationError(Exception):
    """Base exception for test generation errors."""
    pass


class StrategyCreationError(TestGenerationError):
    """Error creating Hypothesis strategy."""
    pass


class CoverageCalculationError(TestGenerationError):
    """Error calculating branch coverage."""
    pass


class StorageError(TestGenerationError):
    """Error storing test vectors."""
    pass


def handle_test_generation_error(
    error: Exception,
    operation_name: str,
    artifact_id: str,
    sns_topic_arn: str = None
) -> None:
    """
    Handle test generation errors with appropriate logging and notifications.
    
    Args:
        error: The exception that occurred
        operation_name: Name of the operation that failed
        artifact_id: Artifact identifier for context
        sns_topic_arn: SNS topic ARN for operator notifications
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    logger.error(
        f"Test generation error in {operation_name}",
        extra={
            "error_type": error_type,
            "error_message": error_message,
            "artifact_id": artifact_id,
            "operation": operation_name
        }
    )
    
    # Classify error
    if _is_transient_error(error):
        logger.info(
            "Error classified as transient, will retry",
            extra={"error_type": error_type}
        )
        raise TransientError(f"{operation_name} failed: {error_message}") from error
    
    elif _is_aws_500_error(error):
        logger.error(
            "AWS 500-level error detected, notifying operators",
            extra={
                "error_type": error_type,
                "error_message": error_message
            }
        )
        
        # Notify operators via SNS
        if sns_topic_arn:
            _publish_operator_alert(
                sns_topic_arn=sns_topic_arn,
                error_type=error_type,
                error_message=error_message,
                artifact_id=artifact_id,
                operation=operation_name
            )
        
        raise PermanentError(
            f"AWS 500-level error in {operation_name}: {error_message}"
        ) from error
    
    else:
        logger.error(
            "Error classified as permanent",
            extra={"error_type": error_type}
        )
        raise PermanentError(f"{operation_name} failed: {error_message}") from error


def _is_transient_error(error: Exception) -> bool:
    """
    Determine if an error is transient and should be retried.
    
    Args:
        error: The exception to classify
        
    Returns:
        True if error is transient, False otherwise
    """
    error_type = type(error).__name__
    error_message = str(error).lower()
    
    # AWS throttling errors
    if error_type in ['ThrottlingException', 'TooManyRequestsException']:
        return True
    
    # Network errors
    if error_type in ['ConnectionError', 'Timeout', 'ReadTimeoutError']:
        return True
    
    # S3 transient errors
    if 'slowdown' in error_message or 'serviceunavailable' in error_message:
        return True
    
    # DynamoDB transient errors
    if 'provisionedthroughputexceeded' in error_message:
        return True
    
    return False


def _is_aws_500_error(error: Exception) -> bool:
    """
    Determine if an error is an AWS 500-level error requiring operator intervention.
    
    Args:
        error: The exception to classify
        
    Returns:
        True if error is AWS 500-level, False otherwise
    """
    error_message = str(error).lower()
    
    # Check for 500-level HTTP status codes
    if any(code in error_message for code in ['500', '502', '503', '504']):
        return True
    
    # Check for AWS service errors
    if 'internalservererror' in error_message:
        return True
    
    if 'serviceerror' in error_message:
        return True
    
    return False


def _publish_operator_alert(
    sns_topic_arn: str,
    error_type: str,
    error_message: str,
    artifact_id: str,
    operation: str
) -> None:
    """
    Publish operator alert to SNS topic.
    
    Args:
        sns_topic_arn: SNS topic ARN
        error_type: Type of error
        error_message: Error message
        artifact_id: Artifact identifier
        operation: Operation that failed
    """
    try:
        subject = f"Rosetta Zero: AWS 500-level Error in Hostile Auditor"
        
        message = f"""
AWS 500-level error detected in Rosetta Zero Hostile Auditor.

Component: Hostile Auditor
Operation: {operation}
Artifact ID: {artifact_id}
Error Type: {error_type}
Error Message: {error_message}

Action Required: Operator intervention needed. The system has paused execution.

Please investigate the AWS service status and retry the operation once resolved.
        """
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=message
        )
        
        logger.info(
            "Operator alert published to SNS",
            extra={
                "sns_topic_arn": sns_topic_arn,
                "artifact_id": artifact_id
            }
        )
    
    except Exception as e:
        logger.error(
            "Failed to publish operator alert",
            extra={
                "error": str(e),
                "sns_topic_arn": sns_topic_arn
            }
        )


def execute_with_error_handling(
    operation_func,
    operation_name: str,
    artifact_id: str,
    retry_strategy: RetryStrategy,
    sns_topic_arn: str = None
):
    """
    Execute an operation with error handling and retry logic.
    
    Args:
        operation_func: Function to execute
        operation_name: Name of the operation for logging
        artifact_id: Artifact identifier for context
        retry_strategy: RetryStrategy instance for retries
        sns_topic_arn: SNS topic ARN for operator notifications
        
    Returns:
        Result of operation_func
        
    Raises:
        PermanentError: If operation fails permanently
    """
    try:
        return retry_strategy.execute_with_retry(
            operation_func,
            operation_name=operation_name
        )
    except Exception as e:
        handle_test_generation_error(
            error=e,
            operation_name=operation_name,
            artifact_id=artifact_id,
            sns_topic_arn=sns_topic_arn
        )
