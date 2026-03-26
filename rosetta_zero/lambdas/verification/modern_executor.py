"""
Modern Lambda Executor.

Executes modern Lambda implementations and captures execution results.
Requirements: 11.3, 11.5, 11.6
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import TestVector, ExecutionResult, ExecutionError, ImplementationType
from rosetta_zero.utils import (
    logger,
    tracer,
    with_retry,
    TransientError,
    PermanentError,
    log_error,
    log_execution_metrics,
)

# AWS clients
lambda_client = boto3.client('lambda')
logs_client = boto3.client('logs')
s3_client = boto3.client('s3')
dynamodb_client = boto3.client('dynamodb')


@tracer.capture_method
def execute_modern_lambda(test_vector: TestVector, lambda_function_arn: str) -> ExecutionResult:
    """
    Execute modern Lambda implementation.
    
    Requirements: 11.3, 11.5, 11.6
    
    Invokes Lambda function with test vector input and captures:
    - Return value
    - stdout/stderr from CloudWatch Logs
    - Side effects (S3 writes, DynamoDB operations)
    - Execution duration
    
    Args:
        test_vector: Test vector containing input parameters
        lambda_function_arn: ARN of modern Lambda function to execute
        
    Returns:
        ExecutionResult with all captured outputs and side effects
        
    Raises:
        TransientError: For retryable failures (AWS throttling, etc.)
        PermanentError: For non-retryable failures (invalid input, etc.)
    """
    logger.info(
        f"Executing modern Lambda for test vector: {test_vector.vector_id}",
        extra={'lambda_arn': lambda_function_arn}
    )
    
    start_time = time.time()
    
    try:
        # Invoke Lambda function
        response = _invoke_lambda(test_vector, lambda_function_arn)
        
        # Parse response
        return_value, error = _parse_lambda_response(response)
        
        # Retrieve stdout/stderr from CloudWatch Logs
        request_id = response.get('ResponseMetadata', {}).get('RequestId')
        stdout, stderr = _retrieve_lambda_logs(lambda_function_arn, request_id)
        
        # Capture side effects (S3 writes, DynamoDB operations)
        side_effects = _capture_side_effects(test_vector.vector_id, start_time)
        
        end_time = time.time()
        execution_duration_ms = int((end_time - start_time) * 1000)
        
        # Create execution result
        execution_result = ExecutionResult(
            test_vector_id=test_vector.vector_id,
            implementation_type=ImplementationType.MODERN,
            execution_timestamp=datetime.utcnow(),
            return_value=return_value if error is None else -1,
            stdout=stdout,
            stderr=stderr,
            side_effects=side_effects,
            execution_duration_ms=execution_duration_ms,
            error=error
        )
        
        # Log execution metrics
        log_execution_metrics(
            implementation_type='MODERN',
            test_vector_id=test_vector.vector_id,
            duration_ms=execution_duration_ms,
            success=error is None
        )
        
        logger.info(
            f"Modern execution completed",
            extra={
                'test_vector_id': test_vector.vector_id,
                'lambda_arn': lambda_function_arn,
                'duration_ms': execution_duration_ms,
                'return_value': return_value,
                'has_error': error is not None
            }
        )
        
        return execution_result
        
    except Exception as e:
        end_time = time.time()
        execution_duration_ms = int((end_time - start_time) * 1000)
        
        log_error(
            "Modern execution failed",
            e,
            test_vector.vector_id,
            extra={'duration_ms': execution_duration_ms}
        )
        
        # Create error execution result
        return ExecutionResult(
            test_vector_id=test_vector.vector_id,
            implementation_type=ImplementationType.MODERN,
            execution_timestamp=datetime.utcnow(),
            return_value=-1,
            stdout=b'',
            stderr=str(e).encode('utf-8'),
            side_effects=[],
            execution_duration_ms=execution_duration_ms,
            error=ExecutionError(
                error_type=type(e).__name__,
                message=str(e),
                traceback=None
            )
        )


@tracer.capture_method
@with_retry(max_retries=3)
def _invoke_lambda(test_vector: TestVector, lambda_function_arn: str) -> Dict[str, Any]:
    """
    Invoke Lambda function with test vector.
    
    Args:
        test_vector: Test vector with input parameters
        lambda_function_arn: ARN of Lambda function
        
    Returns:
        Lambda invocation response
        
    Raises:
        TransientError: For retryable AWS errors
        PermanentError: For non-retryable errors
    """
    logger.info(f"Invoking Lambda: {lambda_function_arn}")
    
    # Prepare payload
    payload = {
        'test_vector_id': test_vector.vector_id,
        'input_parameters': test_vector.input_parameters,
        'entry_point': test_vector.entry_point
    }
    
    try:
        response = lambda_client.invoke(
            FunctionName=lambda_function_arn,
            InvocationType='RequestResponse',  # Synchronous invocation
            Payload=json.dumps(payload)
        )
        
        logger.info(
            f"Lambda invoked",
            extra={
                'lambda_arn': lambda_function_arn,
                'status_code': response.get('StatusCode'),
                'function_error': response.get('FunctionError')
            }
        )
        
        return response
        
    except lambda_client.exceptions.TooManyRequestsException as e:
        # Throttling is transient
        log_error("Lambda throttling", e, test_vector.vector_id)
        raise TransientError(f"Lambda throttling: {e}")
        
    except lambda_client.exceptions.ServiceException as e:
        # Service errors are transient
        log_error("Lambda service error", e, test_vector.vector_id)
        raise TransientError(f"Lambda service error: {e}")
        
    except lambda_client.exceptions.InvalidParameterValueException as e:
        # Invalid parameters are permanent
        log_error("Lambda invalid parameters", e, test_vector.vector_id)
        raise PermanentError(f"Invalid parameters: {e}")
        
    except Exception as e:
        log_error("Unexpected error invoking Lambda", e, test_vector.vector_id)
        raise TransientError(f"Unexpected error: {e}")


def _parse_lambda_response(response: Dict[str, Any]) -> tuple:
    """
    Parse Lambda invocation response.
    
    Args:
        response: Lambda invocation response
        
    Returns:
        Tuple of (return_value, error)
    """
    status_code = response.get('StatusCode')
    function_error = response.get('FunctionError')
    
    # Read payload
    payload_bytes = response.get('Payload').read()
    
    if function_error:
        # Lambda function had an error
        try:
            error_payload = json.loads(payload_bytes)
            error_message = error_payload.get('errorMessage', 'Unknown error')
            error_type = error_payload.get('errorType', 'UnknownError')
        except json.JSONDecodeError:
            error_message = payload_bytes.decode('utf-8')
            error_type = 'UnknownError'
        
        error = ExecutionError(
            error_type=error_type,
            message=error_message,
            traceback=None
        )
        
        return -1, error
    
    # Parse successful response
    try:
        result = json.loads(payload_bytes)
        return_value = result.get('return_value', 0)
        return return_value, None
    except json.JSONDecodeError:
        # Response is not JSON, treat as error
        error = ExecutionError(
            error_type='InvalidResponse',
            message=f'Lambda response is not valid JSON: {payload_bytes.decode("utf-8")}',
            traceback=None
        )
        return -1, error


@tracer.capture_method
def _retrieve_lambda_logs(lambda_function_arn: str, request_id: str) -> tuple:
    """
    Retrieve stdout/stderr from CloudWatch Logs.
    
    Args:
        lambda_function_arn: ARN of Lambda function
        request_id: Lambda request ID
        
    Returns:
        Tuple of (stdout, stderr) as bytes
    """
    # Extract function name from ARN
    function_name = lambda_function_arn.split(':')[-1]
    log_group_name = f"/aws/lambda/{function_name}"
    
    try:
        # Find log stream for this request
        # Log stream name format: YYYY/MM/DD/[$LATEST]random-string
        # We need to search for the request ID in recent log streams
        
        response = logs_client.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=10  # Check last 10 streams
        )
        
        log_streams = response.get('logStreams', [])
        
        stdout_lines = []
        stderr_lines = []
        
        for log_stream in log_streams:
            log_stream_name = log_stream['logStreamName']
            
            # Get log events
            events_response = logs_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                startFromHead=True
            )
            
            events = events_response.get('events', [])
            
            # Look for request ID in events
            found_request = False
            for event in events:
                message = event.get('message', '')
                
                if request_id in message:
                    found_request = True
                
                if found_request:
                    # Collect log messages for this request
                    # PowerTools logs are JSON, parse them
                    if message.startswith('START REQUEST') or message.startswith('END REQUEST') or message.startswith('REPORT REQUEST'):
                        continue
                    
                    # Check if it's a PowerTools JSON log
                    if message.strip().startswith('{'):
                        try:
                            log_entry = json.loads(message)
                            log_message = log_entry.get('message', '')
                            log_level = log_entry.get('level', 'INFO')
                            
                            if log_level in ['ERROR', 'CRITICAL']:
                                stderr_lines.append(log_message)
                            else:
                                stdout_lines.append(log_message)
                        except json.JSONDecodeError:
                            stdout_lines.append(message)
                    else:
                        stdout_lines.append(message)
                    
                    # Stop at next START REQUEST
                    if message.startswith('START REQUEST') and found_request:
                        break
            
            if found_request:
                break
        
        stdout = '\n'.join(stdout_lines).encode('utf-8')
        stderr = '\n'.join(stderr_lines).encode('utf-8')
        
        return stdout, stderr
        
    except logs_client.exceptions.ResourceNotFoundException:
        logger.warning(f"Log group not found: {log_group_name}")
        return b'', b''
        
    except Exception as e:
        logger.warning(f"Error retrieving Lambda logs: {e}")
        return b'', b''


@tracer.capture_method
def _capture_side_effects(test_vector_id: str, start_time: float) -> list:
    """
    Capture side effects from modern Lambda execution.
    
    Captures:
    - S3 writes (objects created/modified)
    - DynamoDB operations (items written)
    
    Args:
        test_vector_id: Test vector ID for filtering
        start_time: Execution start time (epoch seconds)
        
    Returns:
        List of observed side effects
    """
    side_effects = []
    
    # Note: In a real implementation, we would use CloudTrail or VPC Flow Logs
    # to capture side effects. For now, we return an empty list.
    # The modern implementation should be instrumented to log side effects.
    
    logger.debug(f"Capturing side effects for test vector: {test_vector_id}")
    
    # TODO: Implement side effect capture using CloudTrail API
    # - Query CloudTrail for S3 PutObject events
    # - Query CloudTrail for DynamoDB PutItem/UpdateItem events
    # - Filter by timestamp and test vector ID
    
    return side_effects
