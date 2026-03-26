"""
Error Handling for Verification Environment.

Handles Fargate failures, Lambda failures, Step Functions errors, and behavioral discrepancies.
Requirements: 19.2, 19.3, 19.4, 25.1-25.5
"""

import json
import os
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import TestVector, ExecutionResult
from rosetta_zero.utils import (
    logger,
    tracer,
    TransientError,
    PermanentError,
    BehavioralDiscrepancyError,
    log_error,
    log_aws_500_error,
)

# AWS clients
sns_client = boto3.client('sns')
events_client = boto3.client('events')
s3_client = boto3.client('s3')

# Environment variables
OPERATOR_ALERTS_TOPIC_ARN = os.environ.get('OPERATOR_ALERTS_TOPIC_ARN', '')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')
EXECUTION_FAILURE_BUCKET = os.environ.get('DISCREPANCY_BUCKET', 'rosetta-zero-discrepancy-reports')


@tracer.capture_method
def handle_verification_error(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle errors during verification phase.
    
    Requirements: 19.2, 19.3, 19.4, 25.1-25.5
    
    Handles:
    - Fargate task failures
    - Lambda invocation failures
    - Step Functions execution errors
    - Behavioral discrepancies
    
    Actions:
    - Generate execution failure reports
    - Halt pipeline on behavioral discrepancies (Requirement 19.2)
    - Add retry logic for transient errors (Requirement 25.2, 25.3)
    - Publish operator alerts for AWS 500-level errors (Requirements 19.3, 25.5)
    
    Args:
        error: Exception that occurred
        test_vector: Test vector being executed
        context: Additional context about the error
        
    Raises:
        TransientError: For retryable errors
        PermanentError: For non-retryable errors
        BehavioralDiscrepancyError: For behavioral discrepancies
    """
    error_type = type(error).__name__
    error_message = str(error)
    
    logger.error(
        f"Verification error occurred",
        extra={
            'error_type': error_type,
            'error_message': error_message,
            'test_vector_id': test_vector.vector_id,
            'context': context
        }
    )
    
    # Log error before retry (Requirement 25.1)
    log_error(
        "Verification error",
        error,
        test_vector.vector_id,
        extra=context
    )
    
    # Handle specific error types
    if isinstance(error, BehavioralDiscrepancyError):
        # Behavioral discrepancy - halt pipeline (Requirement 19.2)
        _handle_behavioral_discrepancy(error, test_vector, context)
        raise error
    
    elif _is_fargate_failure(error, context):
        # Fargate task failure
        _handle_fargate_failure(error, test_vector, context)
        
    elif _is_lambda_failure(error, context):
        # Lambda invocation failure
        _handle_lambda_failure(error, test_vector, context)
        
    elif _is_step_functions_error(error, context):
        # Step Functions execution error
        _handle_step_functions_error(error, test_vector, context)
        
    elif _is_aws_500_error(error):
        # AWS 500-level error - notify operators (Requirements 19.3, 25.5)
        _handle_aws_500_error(error, test_vector, context)
        
    else:
        # Unknown error
        _handle_unknown_error(error, test_vector, context)


@tracer.capture_method
def _handle_behavioral_discrepancy(
    error: BehavioralDiscrepancyError,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle behavioral discrepancy.
    
    Requirement 19.2: Halt pipeline on behavioral discrepancies
    
    Args:
        error: Behavioral discrepancy error
        test_vector: Test vector
        context: Error context
    """
    logger.error(
        "Behavioral discrepancy detected - halting pipeline",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error': str(error)
        }
    )
    
    # Publish event
    _publish_failure_event(
        'BehavioralDiscrepancy',
        test_vector,
        str(error),
        context
    )
    
    # Pipeline will be halted by raising the error


@tracer.capture_method
def _handle_fargate_failure(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle Fargate task failure.
    
    Generates execution failure report and halts pipeline.
    
    Args:
        error: Fargate failure error
        test_vector: Test vector
        context: Error context
        
    Raises:
        BehavioralDiscrepancyError: To halt pipeline
    """
    logger.error(
        "Fargate task failed",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error': str(error),
            'task_arn': context.get('task_arn')
        }
    )
    
    # Generate execution failure report
    report_id = _generate_execution_failure_report(
        test_vector,
        'FARGATE_FAILURE',
        error,
        context
    )
    
    # Publish failure event
    _publish_failure_event(
        'FargateExecutionFailure',
        test_vector,
        str(error),
        context
    )
    
    # Halt pipeline
    raise BehavioralDiscrepancyError(
        f"Legacy execution failed for test {test_vector.vector_id}. "
        f"Failure report: {report_id}"
    )


@tracer.capture_method
def _handle_lambda_failure(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle Lambda invocation failure.
    
    Generates execution failure report and halts pipeline.
    
    Args:
        error: Lambda failure error
        test_vector: Test vector
        context: Error context
        
    Raises:
        BehavioralDiscrepancyError: To halt pipeline
    """
    logger.error(
        "Lambda invocation failed",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error': str(error),
            'lambda_arn': context.get('lambda_arn')
        }
    )
    
    # Generate execution failure report
    report_id = _generate_execution_failure_report(
        test_vector,
        'LAMBDA_FAILURE',
        error,
        context
    )
    
    # Publish failure event
    _publish_failure_event(
        'LambdaExecutionFailure',
        test_vector,
        str(error),
        context
    )
    
    # Halt pipeline
    raise BehavioralDiscrepancyError(
        f"Modern execution failed for test {test_vector.vector_id}. "
        f"Failure report: {report_id}"
    )


@tracer.capture_method
def _handle_step_functions_error(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle Step Functions execution error.
    
    Checks if error is transient (500-level) or permanent.
    
    Args:
        error: Step Functions error
        test_vector: Test vector
        context: Error context
        
    Raises:
        TransientError: For retryable errors
        PermanentError: For non-retryable errors
    """
    logger.error(
        "Step Functions execution error",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error': str(error),
            'execution_arn': context.get('execution_arn')
        }
    )
    
    # Check if it's a 500-level error
    if _is_aws_500_error(error):
        _handle_aws_500_error(error, test_vector, context)
    else:
        # Client error - permanent
        raise PermanentError(f"Step Functions error: {error}")


@tracer.capture_method
def _handle_aws_500_error(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle AWS 500-level error.
    
    Requirements 19.3, 19.4, 25.5: Notify operators and pause execution
    
    Args:
        error: AWS 500-level error
        test_vector: Test vector
        context: Error context
        
    Raises:
        PermanentError: To pause execution until operator intervention
    """
    logger.error(
        "AWS 500-level error detected",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error': str(error),
            'service': context.get('service', 'Unknown')
        }
    )
    
    # Log AWS 500 error
    log_aws_500_error(
        service=context.get('service', 'Unknown'),
        error=error,
        context_id=test_vector.vector_id,
        additional_context=context
    )
    
    # Publish operator alert (Requirement 25.5)
    _publish_operator_alert(
        'AWS 500-Level Error',
        error,
        test_vector,
        context
    )
    
    # Publish failure event
    _publish_failure_event(
        'AWS500Error',
        test_vector,
        str(error),
        context
    )
    
    # Pause execution (Requirement 19.4)
    raise PermanentError(
        f"AWS 500-level error in {context.get('service', 'Unknown')}. "
        f"Operator intervention required. Error: {error}"
    )


@tracer.capture_method
def _handle_unknown_error(
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Handle unknown error.
    
    Args:
        error: Unknown error
        test_vector: Test vector
        context: Error context
        
    Raises:
        TransientError: To retry
    """
    logger.error(
        "Unknown verification error",
        extra={
            'test_vector_id': test_vector.vector_id,
            'error_type': type(error).__name__,
            'error': str(error)
        }
    )
    
    # Treat as transient and retry
    raise TransientError(f"Unknown error: {error}")


@tracer.capture_method
def _generate_execution_failure_report(
    test_vector: TestVector,
    failure_type: str,
    error: Exception,
    context: Dict[str, Any]
) -> str:
    """
    Generate execution failure report.
    
    Args:
        test_vector: Test vector
        failure_type: Type of failure
        error: Error that occurred
        context: Error context
        
    Returns:
        Report ID
    """
    import uuid
    from datetime import datetime
    
    report_id = f"execution-failure-{test_vector.vector_id}-{uuid.uuid4().hex[:8]}"
    
    report = {
        'report_id': report_id,
        'generation_timestamp': datetime.utcnow().isoformat(),
        'test_vector_id': test_vector.vector_id,
        'test_vector': test_vector.to_dict(),
        'failure_type': failure_type,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context
    }
    
    # Store report in S3
    s3_key = f"execution-failures/{report_id}/report.json"
    
    try:
        s3_client.put_object(
            Bucket=EXECUTION_FAILURE_BUCKET,
            Key=s3_key,
            Body=json.dumps(report, indent=2),
            ContentType='application/json'
        )
        
        logger.info(
            f"Execution failure report generated",
            extra={
                'report_id': report_id,
                's3_location': f"s3://{EXECUTION_FAILURE_BUCKET}/{s3_key}"
            }
        )
        
    except Exception as e:
        log_error("Failed to store execution failure report", e, report_id)
    
    return report_id


@tracer.capture_method
def _publish_operator_alert(
    alert_type: str,
    error: Exception,
    test_vector: TestVector,
    context: Dict[str, Any]
) -> None:
    """
    Publish operator alert via SNS.
    
    Requirement 25.5: Publish operator alerts for AWS 500-level errors
    
    Args:
        alert_type: Type of alert
        error: Error that occurred
        test_vector: Test vector
        context: Error context
    """
    if not OPERATOR_ALERTS_TOPIC_ARN:
        logger.warning("Operator alerts topic ARN not configured")
        return
    
    message = f"""
Rosetta Zero Verification Alert

Alert Type: {alert_type}
Test Vector ID: {test_vector.vector_id}
Error: {type(error).__name__}: {str(error)}

Context:
{json.dumps(context, indent=2)}

Operator intervention required. System execution paused.
"""
    
    try:
        sns_client.publish(
            TopicArn=OPERATOR_ALERTS_TOPIC_ARN,
            Subject=f"Rosetta Zero: {alert_type}",
            Message=message
        )
        
        logger.info(
            f"Operator alert published",
            extra={
                'alert_type': alert_type,
                'test_vector_id': test_vector.vector_id
            }
        )
        
    except Exception as e:
        log_error("Failed to publish operator alert", e, test_vector.vector_id)


@tracer.capture_method
def _publish_failure_event(
    failure_type: str,
    test_vector: TestVector,
    error_message: str,
    context: Dict[str, Any]
) -> None:
    """
    Publish failure event to EventBridge.
    
    Args:
        failure_type: Type of failure
        test_vector: Test vector
        error_message: Error message
        context: Error context
    """
    event_detail = {
        'failure_type': failure_type,
        'test_vector_id': test_vector.vector_id,
        'error_message': error_message,
        'context': context
    }
    
    try:
        events_client.put_events(
            Entries=[
                {
                    'Source': 'rosetta-zero.verification',
                    'DetailType': f'Verification {failure_type}',
                    'Detail': json.dumps(event_detail),
                    'EventBusName': EVENT_BUS_NAME
                }
            ]
        )
        
        logger.info(
            f"Failure event published",
            extra={
                'failure_type': failure_type,
                'test_vector_id': test_vector.vector_id
            }
        )
        
    except Exception as e:
        log_error("Failed to publish failure event", e, test_vector.vector_id)


def _is_fargate_failure(error: Exception, context: Dict[str, Any]) -> bool:
    """Check if error is a Fargate failure."""
    return 'task_arn' in context or 'FargateTaskFailedException' in type(error).__name__


def _is_lambda_failure(error: Exception, context: Dict[str, Any]) -> bool:
    """Check if error is a Lambda failure."""
    return 'lambda_arn' in context or 'LambdaInvocationException' in type(error).__name__


def _is_step_functions_error(error: Exception, context: Dict[str, Any]) -> bool:
    """Check if error is a Step Functions error."""
    return 'execution_arn' in context or 'StepFunctionsExecutionException' in type(error).__name__


def _is_aws_500_error(error: Exception) -> bool:
    """Check if error is an AWS 500-level error."""
    error_str = str(error).lower()
    return (
        '500' in error_str or
        'internal server error' in error_str or
        'service error' in error_str or
        'InternalServerError' in type(error).__name__ or
        'ServiceException' in type(error).__name__
    )
