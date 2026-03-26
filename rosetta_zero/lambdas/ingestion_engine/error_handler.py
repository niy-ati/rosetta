"""Error handling and retry logic for Ingestion Engine.

Requirements: 19.2, 19.3, 19.4, 25.1, 25.2, 25.3, 25.4, 25.5
"""

from typing import Callable, Any
from functools import wraps

import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger

from rosetta_zero.utils.retry import (
    RetryStrategy,
    TransientError,
    PermanentError,
    with_retry,
)
from rosetta_zero.utils.logging import log_error, log_aws_500_error

logger = Logger(child=True)


class IngestionError(Exception):
    """Base exception for ingestion errors."""
    pass


class BedrockThrottlingError(TransientError):
    """Bedrock API throttling error."""
    pass


class MacieError(TransientError):
    """Macie service error."""
    pass


class AWS500Error(TransientError):
    """AWS 500-level error requiring operator notification."""
    
    def __init__(self, service: str, operation: str, error_code: str, message: str):
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.error_code = error_code


def handle_ingestion_error(func: Callable) -> Callable:
    """Decorator to handle ingestion errors with retry logic.
    
    Requirements: 19.2, 19.3, 19.4, 25.1, 25.2, 25.3
    
    Handles:
    - Bedrock throttling: Retry with exponential backoff
    - AWS 500 errors: Notify operators via SNS, retry
    - Macie failures: Retry with exponential backoff
    - Other transient errors: Retry with exponential backoff
    
    Args:
        func: Function to wrap with error handling
    
    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        retry_strategy = RetryStrategy(
            max_retries=3,
            base_delay_seconds=2,
            max_delay_seconds=60,
        )
        
        def execute():
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
                service = e.response.get("ResponseMetadata", {}).get("ServiceName", "Unknown")
                operation = e.operation_name
                
                # Log error before retry or halt (Requirement 25.1)
                log_error(
                    component="ingestion_engine",
                    error_type="ClientError",
                    error_message=str(e),
                    context={
                        "error_code": error_code,
                        "service": service,
                        "operation": operation,
                    }
                )
                
                # Handle AWS 500-level errors (Requirements 19.3, 19.4)
                if 500 <= status_code < 600:
                    log_aws_500_error(
                        service=service,
                        operation=operation,
                        error_code=error_code,
                        error_message=str(e),
                        context={
                            "status_code": status_code,
                        }
                    )
                    
                    # Publish operator alert via SNS (Requirement 19.3)
                    publish_operator_alert(
                        service=service,
                        operation=operation,
                        error_code=error_code,
                        status_code=status_code,
                    )
                    
                    raise AWS500Error(
                        service=service,
                        operation=operation,
                        error_code=error_code,
                        message=str(e),
                    )
                
                # Handle Bedrock throttling (Requirement 19.2)
                if error_code == "ThrottlingException" and service == "bedrock-runtime":
                    logger.warning("Bedrock throttling detected, will retry")
                    raise BedrockThrottlingError(str(e))
                
                # Handle Macie errors (Requirement 19.2)
                if service == "macie2":
                    logger.warning("Macie error detected, will retry")
                    raise MacieError(str(e))
                
                # Handle other transient errors
                if error_code in ["ServiceUnavailable", "RequestTimeout", "TooManyRequests"]:
                    raise TransientError(str(e))
                
                # Permanent errors
                raise PermanentError(str(e))
            
            except Exception as e:
                # Log unexpected errors
                log_error(
                    component="ingestion_engine",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    context={}
                )
                raise
        
        # Execute with retry (Requirement 25.2, 25.3)
        return retry_strategy.execute_with_retry(execute)
    
    return wrapper


def publish_operator_alert(
    service: str,
    operation: str,
    error_code: str,
    status_code: int,
) -> None:
    """Publish operator alert for AWS 500-level errors via SNS.
    
    Requirement: 19.3
    
    Args:
        service: AWS service name
        operation: Operation that failed
        error_code: Error code
        status_code: HTTP status code
    """
    try:
        sns_client = boto3.client("sns")
        topic_arn = boto3.client("ssm").get_parameter(
            Name="/rosetta-zero/operator-alerts-topic-arn"
        )["Parameter"]["Value"]
        
        message = f"""AWS 500-Level Error Detected in Rosetta Zero

Service: {service}
Operation: {operation}
Error Code: {error_code}
Status Code: {status_code}

Action Required: Operator intervention may be required.
The system will pause execution until the error is resolved.

Please check CloudWatch Logs for detailed error information.
"""
        
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"Rosetta Zero Alert: AWS 500 Error in {service}",
            Message=message,
        )
        
        logger.info(
            "Operator alert published",
            extra={
                "service": service,
                "operation": operation,
                "error_code": error_code,
            },
        )
    except Exception as e:
        logger.error(f"Failed to publish operator alert: {e}")
        # Don't fail the main operation if alert publishing fails
