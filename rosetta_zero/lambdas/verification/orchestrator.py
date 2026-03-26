"""
Parallel Test Execution Orchestration.

Orchestrates parallel execution of multiple test vectors using Step Functions.
Requirements: 11.1, 11.4
"""

import json
import os
from typing import List, Dict, Any

import boto3
from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import TestVector, TestVectorBatch
from rosetta_zero.utils import (
    logger,
    tracer,
    with_retry,
    TransientError,
    log_error,
)

# AWS clients
s3_client = boto3.client('s3')
sfn_client = boto3.client('stepfunctions')

# Environment variables
TEST_VECTORS_BUCKET = os.environ.get('TEST_VECTORS_BUCKET', 'rosetta-zero-test-vectors')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', '')
MAX_PARALLEL_EXECUTIONS = int(os.environ.get('MAX_PARALLEL_EXECUTIONS', '100'))


@tracer.capture_method
def execute_parallel_tests(
    test_vector_batch_s3_key: str,
    modern_lambda_arn: str
) -> Dict[str, Any]:
    """
    Execute test vectors in parallel using Step Functions.
    
    Requirements: 11.1, 11.4
    
    Reads test vector batches from S3 and invokes Step Functions for each test vector.
    Handles parallel execution of multiple test vectors.
    
    Args:
        test_vector_batch_s3_key: S3 key for test vector batch
        modern_lambda_arn: ARN of modern Lambda implementation to test
        
    Returns:
        Execution summary with test results
    """
    logger.info(
        f"Executing parallel tests",
        extra={
            'batch_s3_key': test_vector_batch_s3_key,
            'modern_lambda_arn': modern_lambda_arn
        }
    )
    
    # Read test vector batch from S3 (Requirement 11.1)
    test_vectors = _read_test_vector_batch(test_vector_batch_s3_key)
    
    logger.info(f"Loaded {len(test_vectors)} test vectors from S3")
    
    # Invoke Step Functions for each test vector (Requirement 11.4)
    execution_arns = []
    failed_starts = []
    
    for i, test_vector in enumerate(test_vectors):
        try:
            execution_arn = _start_verification_execution(
                test_vector,
                modern_lambda_arn
            )
            execution_arns.append(execution_arn)
            
            logger.debug(
                f"Started execution {i+1}/{len(test_vectors)}",
                extra={
                    'test_vector_id': test_vector.vector_id,
                    'execution_arn': execution_arn
                }
            )
            
            # Throttle if we've reached max parallel executions
            if len(execution_arns) >= MAX_PARALLEL_EXECUTIONS:
                logger.info(
                    f"Reached max parallel executions ({MAX_PARALLEL_EXECUTIONS}), "
                    "waiting for some to complete..."
                )
                _wait_for_executions(execution_arns[:MAX_PARALLEL_EXECUTIONS // 2])
                execution_arns = execution_arns[MAX_PARALLEL_EXECUTIONS // 2:]
            
        except Exception as e:
            log_error(
                "Failed to start verification execution",
                e,
                test_vector.vector_id
            )
            failed_starts.append({
                'test_vector_id': test_vector.vector_id,
                'error': str(e)
            })
    
    # Wait for all remaining executions to complete
    logger.info(f"Waiting for {len(execution_arns)} executions to complete...")
    results = _wait_for_executions(execution_arns)
    
    # Aggregate results
    summary = _aggregate_results(results, failed_starts)
    
    logger.info(
        f"Parallel test execution completed",
        extra={
            'total_tests': len(test_vectors),
            'successful_starts': len(execution_arns),
            'failed_starts': len(failed_starts),
            'passed': summary['passed'],
            'failed': summary['failed']
        }
    )
    
    return summary


@tracer.capture_method
@with_retry(max_retries=3)
def _read_test_vector_batch(s3_key: str) -> List[TestVector]:
    """
    Read test vector batch from S3.
    
    Args:
        s3_key: S3 key for test vector batch
        
    Returns:
        List of TestVector objects
    """
    logger.info(f"Reading test vector batch from S3: {s3_key}")
    
    try:
        response = s3_client.get_object(
            Bucket=TEST_VECTORS_BUCKET,
            Key=s3_key
        )
        
        batch_json = response['Body'].read().decode('utf-8')
        batch_data = json.loads(batch_json)
        
        # Parse test vector batch
        batch = TestVectorBatch.from_json(batch_json)
        
        logger.info(
            f"Loaded test vector batch",
            extra={
                'batch_id': batch.batch_id,
                'vector_count': len(batch.vectors)
            }
        )
        
        return batch.vectors
        
    except s3_client.exceptions.NoSuchKey as e:
        log_error("Test vector batch not found in S3", e, s3_key)
        raise
        
    except Exception as e:
        log_error("Failed to read test vector batch", e, s3_key)
        raise TransientError(f"Failed to read batch: {e}")


@tracer.capture_method
@with_retry(max_retries=3)
def _start_verification_execution(
    test_vector: TestVector,
    modern_lambda_arn: str
) -> str:
    """
    Start Step Functions execution for test vector.
    
    Args:
        test_vector: Test vector to execute
        modern_lambda_arn: ARN of modern Lambda implementation
        
    Returns:
        Execution ARN
    """
    execution_name = f"test-{test_vector.vector_id}-{int(test_vector.generation_timestamp.timestamp())}"
    
    # Prepare input for state machine
    input_data = {
        'test_vector': test_vector.to_dict(),
        'modern_lambda_arn': modern_lambda_arn
    }
    
    try:
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(input_data)
        )
        
        execution_arn = response['executionArn']
        
        logger.debug(
            f"Started Step Functions execution",
            extra={
                'test_vector_id': test_vector.vector_id,
                'execution_arn': execution_arn
            }
        )
        
        return execution_arn
        
    except sfn_client.exceptions.ExecutionAlreadyExists:
        # Execution already exists, return ARN
        execution_arn = f"{STATE_MACHINE_ARN.replace(':stateMachine:', ':execution:')}:{execution_name}"
        logger.warning(
            f"Execution already exists",
            extra={
                'test_vector_id': test_vector.vector_id,
                'execution_arn': execution_arn
            }
        )
        return execution_arn
        
    except sfn_client.exceptions.ExecutionLimitExceeded as e:
        # Too many concurrent executions, retry
        log_error("Step Functions execution limit exceeded", e, test_vector.vector_id)
        raise TransientError(f"Execution limit exceeded: {e}")
        
    except Exception as e:
        log_error("Failed to start Step Functions execution", e, test_vector.vector_id)
        raise TransientError(f"Failed to start execution: {e}")


@tracer.capture_method
def _wait_for_executions(execution_arns: List[str]) -> List[Dict[str, Any]]:
    """
    Wait for Step Functions executions to complete.
    
    Args:
        execution_arns: List of execution ARNs to wait for
        
    Returns:
        List of execution results
    """
    logger.info(f"Waiting for {len(execution_arns)} executions to complete")
    
    results = []
    
    for execution_arn in execution_arns:
        try:
            # Poll execution status
            while True:
                response = sfn_client.describe_execution(
                    executionArn=execution_arn
                )
                
                status = response['status']
                
                if status in ['SUCCEEDED', 'FAILED', 'TIMED_OUT', 'ABORTED']:
                    # Execution completed
                    result = {
                        'execution_arn': execution_arn,
                        'status': status,
                        'output': response.get('output'),
                        'stop_date': response.get('stopDate')
                    }
                    results.append(result)
                    
                    logger.debug(
                        f"Execution completed",
                        extra={
                            'execution_arn': execution_arn,
                            'status': status
                        }
                    )
                    
                    break
                
                # Still running, wait before checking again
                import time
                time.sleep(5)
                
        except Exception as e:
            log_error("Error waiting for execution", e, execution_arn)
            results.append({
                'execution_arn': execution_arn,
                'status': 'ERROR',
                'error': str(e)
            })
    
    return results


@tracer.capture_method
def _aggregate_results(
    execution_results: List[Dict[str, Any]],
    failed_starts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Aggregate test execution results.
    
    Args:
        execution_results: List of execution results
        failed_starts: List of failed execution starts
        
    Returns:
        Aggregated summary
    """
    passed = 0
    failed = 0
    errors = 0
    
    for result in execution_results:
        status = result['status']
        
        if status == 'SUCCEEDED':
            # Parse output to check if test passed
            output = result.get('output')
            if output:
                try:
                    output_data = json.loads(output)
                    if output_data.get('match', False):
                        passed += 1
                    else:
                        failed += 1
                except json.JSONDecodeError:
                    errors += 1
            else:
                errors += 1
        else:
            # Execution failed or timed out
            failed += 1
    
    summary = {
        'total_tests': len(execution_results) + len(failed_starts),
        'successful_starts': len(execution_results),
        'failed_starts': len(failed_starts),
        'passed': passed,
        'failed': failed,
        'errors': errors,
        'execution_results': execution_results,
        'failed_start_details': failed_starts
    }
    
    return summary
