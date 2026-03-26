"""
Error handling for Certificate Generator Lambda.

This module implements error handling, retry logic, and operator alerts
for certificate generation failures.

Requirements: 19.2, 19.3, 19.4, 25.1-25.5
"""

import json
from typing import Any, Dict, Optional
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from rosetta_zero.utils import log_aws_500_error

logger = Logger(child=True)


def handle_certificate_error(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str],
    context: Dict[str, Any]
) -> None:
    """
    Handle certificate generation errors.
    
    This function:
    1. Classifies error type (transient vs permanent)
    2. Logs error to CloudWatch
    3. Publishes operator alerts for AWS 500-level errors
    4. Determines if retry is appropriate
    
    Args:
        error: Exception that occurred
        sns_client: Boto3 SNS client
        sns_topic_arn: SNS topic ARN for operator notifications
        workflow_id: Workflow ID for tracking
        context: Additional context about the operation
        
    Requirements: 19.2, 19.3, 19.4, 25.1-25.5
    """
    
    logger.error("Certificate generation error occurred", extra={
        'error_type': type(error).__name__,
        'error_message': str(error),
        'workflow_id': workflow_id
    })
    
    # Classify error type
    error_classification = _classify_error(error)
    
    logger.info("Error classified", extra={
        'classification': error_classification,
        'workflow_id': workflow_id
    })
    
    # Handle AWS 500-level errors
    if error_classification == 'aws_500_error':
        _handle_aws_500_error(
            error=error,
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            workflow_id=workflow_id,
            context=context
        )
    
    # Handle KMS failures
    elif error_classification == 'kms_failure':
        _handle_kms_failure(
            error=error,
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            workflow_id=workflow_id
        )
    
    # Handle S3 failures
    elif error_classification == 's3_failure':
        _handle_s3_failure(
            error=error,
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            workflow_id=workflow_id
        )
    
    # Handle DynamoDB failures
    elif error_classification == 'dynamodb_failure':
        _handle_dynamodb_failure(
            error=error,
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            workflow_id=workflow_id
        )
    
    # Handle validation errors (permanent)
    elif error_classification == 'validation_error':
        _handle_validation_error(
            error=error,
            sns_client=sns_client,
            sns_topic_arn=sns_topic_arn,
            workflow_id=workflow_id
        )


def _classify_error(error: Exception) -> str:
    """
    Classify error type for appropriate handling.
    
    Args:
        error: Exception to classify
        
    Returns:
        Error classification string
    """
    
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        http_status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
        
        # AWS 500-level errors
        if http_status >= 500:
            return 'aws_500_error'
        
        # Service-specific errors
        service = error.response.get('ResponseMetadata', {}).get('ServiceId', '')
        
        if 'KMS' in service or 'kms' in error_code.lower():
            return 'kms_failure'
        elif 'S3' in service or 's3' in error_code.lower():
            return 's3_failure'
        elif 'DynamoDB' in service or 'dynamodb' in error_code.lower():
            return 'dynamodb_failure'
    
    # Validation errors
    if isinstance(error, ValueError):
        return 'validation_error'
    
    return 'unknown_error'


def _handle_aws_500_error(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str],
    context: Dict[str, Any]
) -> None:
    """
    Handle AWS 500-level errors.
    
    Requirements: 19.3, 19.4
    """
    
    logger.error("AWS 500-level error detected", extra={
        'error': str(error),
        'workflow_id': workflow_id
    })
    
    # Log to CloudWatch
    log_aws_500_error(
        service='certificate_generator',
        error=error,
        context=context
    )
    
    # Publish operator alert
    if sns_topic_arn:
        try:
            alert_message = {
                'alert_type': 'AWS_500_ERROR',
                'component': 'certificate_generator',
                'workflow_id': workflow_id,
                'error': str(error),
                'action_required': 'Operator intervention required. System execution paused.',
                'context': context
            }
            
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='ALERT: Rosetta Zero - AWS 500-Level Error in Certificate Generator',
                Message=json.dumps(alert_message, indent=2)
            )
            
            logger.info("Operator alert sent for AWS 500-level error")
            
        except Exception as e:
            logger.error(f"Failed to send operator alert: {e}")


def _handle_kms_failure(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str]
) -> None:
    """
    Handle KMS signing/verification failures.
    
    Requirements: 19.2, 25.1-25.5
    """
    
    logger.error("KMS operation failed", extra={
        'error': str(error),
        'workflow_id': workflow_id
    })
    
    # Check if it's a transient error
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Transient errors that can be retried
        transient_codes = ['ThrottlingException', 'ServiceUnavailableException']
        
        if error_code in transient_codes:
            logger.info("KMS error is transient - will be retried")
            return
    
    # Permanent KMS error - alert operators
    if sns_topic_arn:
        try:
            alert_message = {
                'alert_type': 'KMS_FAILURE',
                'component': 'certificate_generator',
                'workflow_id': workflow_id,
                'error': str(error),
                'action_required': 'Check KMS key permissions and availability.'
            }
            
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='ALERT: Rosetta Zero - KMS Failure in Certificate Generator',
                Message=json.dumps(alert_message, indent=2)
            )
            
        except Exception as e:
            logger.error(f"Failed to send KMS failure alert: {e}")


def _handle_s3_failure(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str]
) -> None:
    """
    Handle S3 storage failures.
    
    Requirements: 19.2, 25.1-25.5
    """
    
    logger.error("S3 operation failed", extra={
        'error': str(error),
        'workflow_id': workflow_id
    })
    
    # Check if it's a transient error
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Transient errors that can be retried
        transient_codes = ['SlowDown', 'ServiceUnavailable', 'RequestTimeout']
        
        if error_code in transient_codes:
            logger.info("S3 error is transient - will be retried")
            return
    
    # Permanent S3 error - alert operators
    if sns_topic_arn:
        try:
            alert_message = {
                'alert_type': 'S3_FAILURE',
                'component': 'certificate_generator',
                'workflow_id': workflow_id,
                'error': str(error),
                'action_required': 'Check S3 bucket permissions and availability.'
            }
            
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='ALERT: Rosetta Zero - S3 Failure in Certificate Generator',
                Message=json.dumps(alert_message, indent=2)
            )
            
        except Exception as e:
            logger.error(f"Failed to send S3 failure alert: {e}")


def _handle_dynamodb_failure(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str]
) -> None:
    """
    Handle DynamoDB query failures.
    
    Requirements: 19.2, 25.1-25.5
    """
    
    logger.error("DynamoDB operation failed", extra={
        'error': str(error),
        'workflow_id': workflow_id
    })
    
    # Check if it's a transient error
    if isinstance(error, ClientError):
        error_code = error.response.get('Error', {}).get('Code', '')
        
        # Transient errors that can be retried
        transient_codes = ['ProvisionedThroughputExceededException', 'ThrottlingException']
        
        if error_code in transient_codes:
            logger.info("DynamoDB error is transient - will be retried")
            return
    
    # Permanent DynamoDB error - alert operators
    if sns_topic_arn:
        try:
            alert_message = {
                'alert_type': 'DYNAMODB_FAILURE',
                'component': 'certificate_generator',
                'workflow_id': workflow_id,
                'error': str(error),
                'action_required': 'Check DynamoDB table permissions and availability.'
            }
            
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='ALERT: Rosetta Zero - DynamoDB Failure in Certificate Generator',
                Message=json.dumps(alert_message, indent=2)
            )
            
        except Exception as e:
            logger.error(f"Failed to send DynamoDB failure alert: {e}")


def _handle_validation_error(
    error: Exception,
    sns_client,
    sns_topic_arn: Optional[str],
    workflow_id: Optional[str]
) -> None:
    """
    Handle validation errors (e.g., failed tests).
    
    These are permanent errors that cannot be retried.
    
    Requirements: 25.4, 25.5
    """
    
    logger.error("Validation error - cannot generate certificate", extra={
        'error': str(error),
        'workflow_id': workflow_id
    })
    
    # Alert operators about validation failure
    if sns_topic_arn:
        try:
            alert_message = {
                'alert_type': 'VALIDATION_ERROR',
                'component': 'certificate_generator',
                'workflow_id': workflow_id,
                'error': str(error),
                'action_required': (
                    'Certificate cannot be generated due to validation failure. '
                    'Review test results and discrepancy reports.'
                )
            }
            
            sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='ALERT: Rosetta Zero - Certificate Validation Failed',
                Message=json.dumps(alert_message, indent=2)
            )
            
        except Exception as e:
            logger.error(f"Failed to send validation error alert: {e}")
