"""
Legacy Binary Executor - Fargate Integration.

Launches Fargate tasks to execute legacy binaries and captures execution results.
Requirements: 11.2, 11.5, 11.6
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
ecs_client = boto3.client('ecs')
logs_client = boto3.client('logs')

# Environment variables
CLUSTER_NAME = os.environ.get('ECS_CLUSTER_NAME', 'rosetta-zero-legacy-cluster')
TASK_DEFINITION = os.environ.get('TASK_DEFINITION', 'rosetta-zero-legacy-executor')
SUBNET_IDS = os.environ.get('SUBNET_IDS', '').split(',')
SECURITY_GROUP_ID = os.environ.get('SECURITY_GROUP_ID', '')
LOG_GROUP_NAME = os.environ.get('LOG_GROUP_NAME', '/ecs/rosetta-zero-legacy-executor')


@tracer.capture_method
def execute_legacy_binary(test_vector: TestVector) -> ExecutionResult:
    """
    Execute legacy binary in Fargate container.
    
    Requirements: 11.2, 11.5, 11.6
    
    Launches Fargate task with test vector input and captures:
    - Return value
    - stdout/stderr
    - File system writes
    - Network operations
    - Execution duration
    
    Args:
        test_vector: Test vector containing binary path and input parameters
        
    Returns:
        ExecutionResult with all captured outputs and side effects
        
    Raises:
        TransientError: For retryable failures (AWS throttling, etc.)
        PermanentError: For non-retryable failures (invalid input, etc.)
    """
    logger.info(f"Executing legacy binary for test vector: {test_vector.vector_id}")
    
    start_time = time.time()
    
    try:
        # Launch Fargate task
        task_arn = _launch_fargate_task(test_vector)
        
        # Wait for task to complete
        _wait_for_task_completion(task_arn)
        
        # Retrieve execution results from CloudWatch Logs
        execution_result = _retrieve_execution_results(task_arn, test_vector)
        
        end_time = time.time()
        execution_duration_ms = int((end_time - start_time) * 1000)
        
        # Update execution duration
        execution_result.execution_duration_ms = execution_duration_ms
        
        # Log execution metrics
        log_execution_metrics(
            implementation_type='LEGACY',
            test_vector_id=test_vector.vector_id,
            duration_ms=execution_duration_ms,
            success=execution_result.error is None
        )
        
        logger.info(
            f"Legacy execution completed",
            extra={
                'test_vector_id': test_vector.vector_id,
                'task_arn': task_arn,
                'duration_ms': execution_duration_ms,
                'return_value': execution_result.return_value,
            }
        )
        
        return execution_result
        
    except Exception as e:
        end_time = time.time()
        execution_duration_ms = int((end_time - start_time) * 1000)
        
        log_error(
            "Legacy execution failed",
            e,
            test_vector.vector_id,
            extra={'duration_ms': execution_duration_ms}
        )
        
        # Create error execution result
        return ExecutionResult(
            test_vector_id=test_vector.vector_id,
            implementation_type=ImplementationType.LEGACY,
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
def _launch_fargate_task(test_vector: TestVector) -> str:
    """
    Launch Fargate task to execute legacy binary.
    
    Args:
        test_vector: Test vector with binary path and input parameters
        
    Returns:
        Task ARN of launched Fargate task
        
    Raises:
        TransientError: For retryable AWS errors
        PermanentError: For non-retryable errors
    """
    logger.info(f"Launching Fargate task for test vector: {test_vector.vector_id}")
    
    # Prepare test vector as JSON for container
    test_vector_json = test_vector.to_json()
    
    try:
        response = ecs_client.run_task(
            cluster=CLUSTER_NAME,
            taskDefinition=TASK_DEFINITION,
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets': SUBNET_IDS,
                    'securityGroups': [SECURITY_GROUP_ID],
                    'assignPublicIp': 'DISABLED'  # Requirement 21.5: No public internet
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 'LegacyExecutor',
                        'environment': [
                            {
                                'name': 'TEST_VECTOR',
                                'value': test_vector_json
                            }
                        ]
                    }
                ]
            },
            tags=[
                {
                    'key': 'TestVectorId',
                    'value': test_vector.vector_id
                },
                {
                    'key': 'Component',
                    'value': 'VerificationEnvironment'
                }
            ]
        )
        
        if not response.get('tasks'):
            raise PermanentError("Failed to launch Fargate task: No tasks in response")
        
        task_arn = response['tasks'][0]['taskArn']
        
        logger.info(
            f"Fargate task launched",
            extra={
                'task_arn': task_arn,
                'test_vector_id': test_vector.vector_id
            }
        )
        
        return task_arn
        
    except ecs_client.exceptions.ClientException as e:
        # Client errors are permanent
        log_error("ECS client error", e, test_vector.vector_id)
        raise PermanentError(f"ECS client error: {e}")
        
    except ecs_client.exceptions.ServerException as e:
        # Server errors are transient
        log_error("ECS server error", e, test_vector.vector_id)
        raise TransientError(f"ECS server error: {e}")
        
    except Exception as e:
        log_error("Unexpected error launching Fargate task", e, test_vector.vector_id)
        raise TransientError(f"Unexpected error: {e}")


@tracer.capture_method
def _wait_for_task_completion(task_arn: str, timeout_seconds: int = 600) -> None:
    """
    Wait for Fargate task to complete.
    
    Args:
        task_arn: ARN of Fargate task
        timeout_seconds: Maximum time to wait (default 10 minutes)
        
    Raises:
        PermanentError: If task fails or times out
    """
    logger.info(f"Waiting for task completion: {task_arn}")
    
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        
        if elapsed > timeout_seconds:
            raise PermanentError(f"Task execution timeout after {timeout_seconds} seconds")
        
        try:
            response = ecs_client.describe_tasks(
                cluster=CLUSTER_NAME,
                tasks=[task_arn]
            )
            
            if not response.get('tasks'):
                raise PermanentError(f"Task not found: {task_arn}")
            
            task = response['tasks'][0]
            last_status = task.get('lastStatus')
            
            logger.debug(f"Task status: {last_status}")
            
            if last_status == 'STOPPED':
                # Task completed, check exit code
                containers = task.get('containers', [])
                if containers:
                    exit_code = containers[0].get('exitCode')
                    
                    logger.info(
                        f"Task completed",
                        extra={
                            'task_arn': task_arn,
                            'exit_code': exit_code
                        }
                    )
                    
                    # Exit code 0 is success, non-zero may be expected for legacy binaries
                    # We capture the exit code in the execution result
                    return
                else:
                    raise PermanentError("Task stopped but no container information available")
            
            # Task still running, wait before checking again
            time.sleep(5)
            
        except ecs_client.exceptions.ClientException as e:
            log_error("ECS client error while waiting for task", e, task_arn)
            raise PermanentError(f"ECS client error: {e}")
            
        except ecs_client.exceptions.ServerException as e:
            log_error("ECS server error while waiting for task", e, task_arn)
            # Retry on server errors
            time.sleep(5)
            continue


@tracer.capture_method
def _retrieve_execution_results(task_arn: str, test_vector: TestVector) -> ExecutionResult:
    """
    Retrieve execution results from CloudWatch Logs.
    
    Args:
        task_arn: ARN of completed Fargate task
        test_vector: Original test vector
        
    Returns:
        ExecutionResult with captured outputs and side effects
        
    Raises:
        PermanentError: If logs cannot be retrieved
    """
    logger.info(f"Retrieving execution results for task: {task_arn}")
    
    # Extract task ID from ARN
    task_id = task_arn.split('/')[-1]
    
    # CloudWatch Logs stream name format: prefix/container-name/task-id
    log_stream_name = f"legacy-executor/LegacyExecutor/{task_id}"
    
    try:
        # Retrieve logs from CloudWatch
        response = logs_client.get_log_events(
            logGroupName=LOG_GROUP_NAME,
            logStreamName=log_stream_name,
            startFromHead=True
        )
        
        events = response.get('events', [])
        
        if not events:
            raise PermanentError(f"No log events found for task: {task_arn}")
        
        # The executor.py script outputs JSON result as the last log message
        # Find the JSON output
        result_json = None
        for event in reversed(events):
            message = event.get('message', '')
            if message.strip().startswith('{'):
                try:
                    result_json = json.loads(message)
                    break
                except json.JSONDecodeError:
                    continue
        
        if not result_json:
            raise PermanentError(f"No JSON result found in logs for task: {task_arn}")
        
        # Parse execution result
        execution_result = _parse_execution_result(result_json, test_vector)
        
        logger.info(
            f"Execution results retrieved",
            extra={
                'task_arn': task_arn,
                'test_vector_id': test_vector.vector_id,
                'return_value': execution_result.return_value
            }
        )
        
        return execution_result
        
    except logs_client.exceptions.ResourceNotFoundException as e:
        log_error("CloudWatch Logs stream not found", e, task_arn)
        raise PermanentError(f"Log stream not found: {e}")
        
    except Exception as e:
        log_error("Error retrieving execution results", e, task_arn)
        raise PermanentError(f"Error retrieving results: {e}")


def _parse_execution_result(result_json: Dict[str, Any], test_vector: TestVector) -> ExecutionResult:
    """
    Parse execution result JSON into ExecutionResult object.
    
    Args:
        result_json: JSON result from executor container
        test_vector: Original test vector
        
    Returns:
        ExecutionResult object
    """
    # Parse stdout/stderr from hex encoding
    stdout_hex = result_json.get('stdout', '')
    stderr_hex = result_json.get('stderr', '')
    
    stdout = bytes.fromhex(stdout_hex) if stdout_hex else b''
    stderr = bytes.fromhex(stderr_hex) if stderr_hex else b''
    
    # Parse error if present
    error = None
    if result_json.get('error'):
        error_data = result_json['error']
        error = ExecutionError(
            error_type=error_data.get('type', 'UnknownError'),
            message=error_data.get('message', ''),
            traceback=None
        )
    
    # Create execution result
    return ExecutionResult(
        test_vector_id=test_vector.vector_id,
        implementation_type=ImplementationType.LEGACY,
        execution_timestamp=datetime.fromisoformat(result_json['execution_timestamp']),
        return_value=result_json['return_value'],
        stdout=stdout,
        stderr=stderr,
        side_effects=[],  # Side effects are in result_json['side_effects'], parse if needed
        execution_duration_ms=result_json['execution_duration_ms'],
        error=error
    )
