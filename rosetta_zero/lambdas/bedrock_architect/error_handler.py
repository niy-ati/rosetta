"""Error handling and retry logic for Bedrock Architect.

Requirements: 19.2, 19.3, 19.4, 25.1, 25.2, 25.3, 25.4, 25.5
"""

import json
import boto3
from typing import Any, Optional
from botocore.exceptions import ClientError

from rosetta_zero.utils.logging import logger, log_error, log_aws_500_error, log_retry_attempt
from rosetta_zero.utils.retry import TransientError, PermanentError


def handle_bedrock_error(
    error: Exception,
    operation: str,
    artifact_id: str
) -> Any:
    """
    Handle Bedrock API errors with appropriate retry logic.
    
    Args:
        error: Exception that occurred
        operation: Name of the operation that failed
        artifact_id: Artifact ID for logging context
        
    Raises:
        TransientError: For errors that should be retried
        PermanentError: For errors requiring operator intervention
    """
    error_str = str(error)
    error_type = type(error).__name__
    
    # Log the error
    log_error(
        component="bedrock_architect",
        error_type=error_type,
        error_message=error_str,
        context={
            "operation": operation,
            "artifact_id": artifact_id,
        }
    )
    
    # Handle ClientError from boto3
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        
        # AWS 500-level errors - notify operators
        if http_status >= 500:
            log_aws_500_error(
                service="bedrock",
                operation=operation,
                error_code=error_code,
                error_message=error_str,
                context={
                    "artifact_id": artifact_id,
                    "http_status": http_status,
                }
            )
            
            # Publish SNS notification for operator intervention
            _publish_operator_alert(
                service="bedrock",
                operation=operation,
                error_code=error_code,
                error_message=error_str,
                artifact_id=artifact_id,
            )
            
            # Raise as transient error for retry
            raise TransientError(f"AWS 500-level error: {error_code} - {error_str}")
        
        # Throttling errors - retry with backoff
        if error_code in ['ThrottlingException', 'TooManyRequestsException', 'ProvisionedThroughputExceededException']:
            logger.warning(
                f"Bedrock throttling error in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise TransientError(f"Bedrock throttling: {error_code}")
        
        # Validation errors - permanent failure
        if error_code in ['ValidationException', 'InvalidRequestException']:
            logger.error(
                f"Bedrock validation error in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise PermanentError(f"Invalid request: {error_code} - {error_str}")
        
        # Access denied - permanent failure
        if error_code in ['AccessDeniedException', 'UnauthorizedException']:
            logger.error(
                f"Bedrock access denied in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise PermanentError(f"Access denied: {error_code} - {error_str}")
        
        # Resource not found - permanent failure
        if error_code in ['ResourceNotFoundException', 'ModelNotFoundException']:
            logger.error(
                f"Bedrock resource not found in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise PermanentError(f"Resource not found: {error_code} - {error_str}")
        
        # Service unavailable - transient error
        if error_code in ['ServiceUnavailableException', 'InternalServerException']:
            logger.warning(
                f"Bedrock service unavailable in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise TransientError(f"Service unavailable: {error_code}")
        
        # Timeout errors - transient
        if error_code in ['TimeoutException', 'RequestTimeoutException']:
            logger.warning(
                f"Bedrock timeout in {operation}",
                extra={
                    "error_code": error_code,
                    "artifact_id": artifact_id,
                }
            )
            raise TransientError(f"Request timeout: {error_code}")
    
    # Network errors - transient
    if 'connection' in error_str.lower() or 'timeout' in error_str.lower():
        logger.warning(
            f"Network error in {operation}",
            extra={
                "error": error_str,
                "artifact_id": artifact_id,
            }
        )
        raise TransientError(f"Network error: {error_str}")
    
    # Unknown errors - treat as permanent
    logger.error(
        f"Unknown error in {operation}",
        extra={
            "error_type": error_type,
            "error": error_str,
            "artifact_id": artifact_id,
        }
    )
    raise PermanentError(f"Unknown error: {error_type} - {error_str}")


def _publish_operator_alert(
    service: str,
    operation: str,
    error_code: str,
    error_message: str,
    artifact_id: str,
):
    """Publish SNS notification for operator intervention."""
    try:
        import os
        sns_topic_arn = os.environ.get('OPERATOR_ALERT_SNS_TOPIC')
        
        if not sns_topic_arn:
            logger.warning("OPERATOR_ALERT_SNS_TOPIC not configured, skipping SNS notification")
            return
        
        sns_client = boto3.client('sns')
        
        message = {
            "alert_type": "AWS_500_ERROR",
            "service": service,
            "operation": operation,
            "error_code": error_code,
            "error_message": error_message,
            "artifact_id": artifact_id,
            "component": "bedrock_architect",
            "action_required": "Operator intervention required - check AWS service status",
        }
        
        sns_client.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Rosetta Zero: AWS 500-level error in {service}",
            Message=json.dumps(message, indent=2),
        )
        
        logger.info(
            "Operator alert published",
            extra={
                "sns_topic": sns_topic_arn,
                "service": service,
                "operation": operation,
            }
        )
        
    except Exception as e:
        logger.error(
            f"Failed to publish operator alert: {e}",
            extra={
                "service": service,
                "operation": operation,
            }
        )


def handle_s3_error(
    error: Exception,
    operation: str,
    bucket: str,
    key: str
) -> Any:
    """
    Handle S3 errors with appropriate retry logic.
    
    Args:
        error: Exception that occurred
        operation: Name of the operation that failed
        bucket: S3 bucket name
        key: S3 object key
        
    Raises:
        TransientError: For errors that should be retried
        PermanentError: For errors requiring operator intervention
    """
    error_str = str(error)
    
    log_error(
        component="bedrock_architect",
        error_type=type(error).__name__,
        error_message=error_str,
        context={
            "operation": operation,
            "bucket": bucket,
            "key": key,
        }
    )
    
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        
        # 500-level errors
        if http_status >= 500:
            log_aws_500_error(
                service="s3",
                operation=operation,
                error_code=error_code,
                error_message=error_str,
                context={"bucket": bucket, "key": key}
            )
            raise TransientError(f"S3 500-level error: {error_code}")
        
        # Throttling
        if error_code in ['SlowDown', 'RequestLimitExceeded']:
            raise TransientError(f"S3 throttling: {error_code}")
        
        # Not found - permanent
        if error_code in ['NoSuchKey', 'NoSuchBucket']:
            raise PermanentError(f"S3 resource not found: {error_code}")
        
        # Access denied - permanent
        if error_code in ['AccessDenied', 'InvalidAccessKeyId']:
            raise PermanentError(f"S3 access denied: {error_code}")
    
    # Network errors - transient
    if 'connection' in error_str.lower() or 'timeout' in error_str.lower():
        raise TransientError(f"S3 network error: {error_str}")
    
    # Unknown - permanent
    raise PermanentError(f"S3 unknown error: {error_str}")


def log_synthesis_decision(
    artifact_id: str,
    decision: str,
    details: dict
):
    """Log synthesis decision to CloudWatch for audit trail."""
    from rosetta_zero.utils.logging import log_architect_decision
    
    log_architect_decision(
        logic_map_id=artifact_id,
        decision=decision,
        details=details
    )


def validate_bedrock_response(response_body: dict) -> bool:
    """
    Validate Bedrock response structure.
    
    Args:
        response_body: Parsed Bedrock response
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(response_body, dict):
        logger.error("Bedrock response is not a dictionary")
        return False
    
    if 'content' not in response_body:
        logger.error("Bedrock response missing 'content' field")
        return False
    
    content = response_body['content']
    if not isinstance(content, list) or len(content) == 0:
        logger.error("Bedrock response 'content' is empty or not a list")
        return False
    
    if 'text' not in content[0]:
        logger.error("Bedrock response content missing 'text' field")
        return False
    
    return True
