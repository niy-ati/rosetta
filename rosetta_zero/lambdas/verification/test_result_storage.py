"""
Test Result Storage in DynamoDB.

Stores test results with cryptographic hashes for audit trails.
Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 16.1, 16.2
"""

import hashlib
import json
import os
from datetime import datetime
from typing import Optional

import boto3
from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import (
    TestVector,
    ExecutionResult,
    ComparisonResult,
)
from rosetta_zero.utils import (
    logger,
    tracer,
    with_retry,
    TransientError,
    log_error,
)

# AWS clients
dynamodb_client = boto3.client('dynamodb')

# Environment variables
TEST_RESULTS_TABLE = os.environ.get('TEST_RESULTS_TABLE', 'rosetta-zero-test-results')


@tracer.capture_method
@with_retry(max_retries=3)
def store_test_result(
    test_vector: TestVector,
    legacy_result: ExecutionResult,
    modern_result: ExecutionResult,
    comparison: ComparisonResult,
    discrepancy_report_id: Optional[str] = None
) -> None:
    """
    Store test result in DynamoDB with cryptographic hashes.
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 16.1, 16.2
    
    Stores:
    - Test ID and execution timestamp (Requirement 15.1)
    - Test vector inputs (Requirement 15.2)
    - Execution output hashes (Requirement 15.3)
    - Pass/fail status (Requirement 15.4)
    - Execution timestamps (Requirement 15.5)
    - SHA-256 hash of complete test result (Requirements 16.1, 16.2)
    
    Args:
        test_vector: Test vector that was executed
        legacy_result: Legacy execution result
        modern_result: Modern execution result
        comparison: Comparison result
        discrepancy_report_id: Optional report ID if test failed
        
    Raises:
        TransientError: For retryable DynamoDB errors
    """
    logger.info(
        f"Storing test result for test vector: {test_vector.vector_id}",
        extra={
            'test_vector_id': test_vector.vector_id,
            'status': 'PASS' if comparison.match else 'FAIL'
        }
    )
    
    # Compute hashes (Requirement 15.3)
    legacy_result_hash = _compute_execution_result_hash(legacy_result)
    modern_result_hash = _compute_execution_result_hash(modern_result)
    comparison_result_hash = comparison.result_hash
    
    # Compute complete test result hash (Requirements 16.1, 16.2)
    complete_result_hash = _compute_complete_test_result_hash(
        test_vector,
        legacy_result,
        modern_result,
        comparison
    )
    
    # Prepare DynamoDB item
    item = {
        'test_id': {'S': test_vector.vector_id},  # Partition key (Requirement 15.1)
        'execution_timestamp': {'S': comparison.comparison_timestamp.isoformat()},  # Sort key (Requirement 15.1)
        'status': {'S': 'PASS' if comparison.match else 'FAIL'},  # Requirement 15.4
        'test_vector_id': {'S': test_vector.vector_id},
        'test_vector_inputs': {'S': json.dumps(test_vector.input_parameters)},  # Requirement 15.2
        'legacy_result_hash': {'S': legacy_result_hash},  # Requirement 15.3
        'modern_result_hash': {'S': modern_result_hash},  # Requirement 15.3
        'comparison_result_hash': {'S': comparison_result_hash},  # Requirement 15.3
        'complete_result_hash': {'S': complete_result_hash},  # Requirements 16.1, 16.2
        'legacy_execution_timestamp': {'S': legacy_result.execution_timestamp.isoformat()},  # Requirement 15.5
        'modern_execution_timestamp': {'S': modern_result.execution_timestamp.isoformat()},  # Requirement 15.5
        'comparison_timestamp': {'S': comparison.comparison_timestamp.isoformat()},  # Requirement 15.5
        'legacy_execution_duration_ms': {'N': str(legacy_result.execution_duration_ms)},
        'modern_execution_duration_ms': {'N': str(modern_result.execution_duration_ms)},
        'return_value_match': {'BOOL': comparison.return_value_match},
        'stdout_match': {'BOOL': comparison.stdout_match},
        'stderr_match': {'BOOL': comparison.stderr_match},
        'side_effects_match': {'BOOL': comparison.side_effects_match},
        'legacy_return_value': {'N': str(legacy_result.return_value)},
        'modern_return_value': {'N': str(modern_result.return_value)},
    }
    
    # Add discrepancy report ID if test failed
    if discrepancy_report_id:
        item['discrepancy_report_id'] = {'S': discrepancy_report_id}
    
    try:
        # Store in DynamoDB
        dynamodb_client.put_item(
            TableName=TEST_RESULTS_TABLE,
            Item=item
        )
        
        logger.info(
            f"Test result stored in DynamoDB",
            extra={
                'test_vector_id': test_vector.vector_id,
                'status': 'PASS' if comparison.match else 'FAIL',
                'complete_result_hash': complete_result_hash
            }
        )
        
    except dynamodb_client.exceptions.ProvisionedThroughputExceededException as e:
        # Throttling is transient
        log_error("DynamoDB throttling", e, test_vector.vector_id)
        raise TransientError(f"DynamoDB throttling: {e}")
        
    except dynamodb_client.exceptions.InternalServerError as e:
        # Server errors are transient
        log_error("DynamoDB server error", e, test_vector.vector_id)
        raise TransientError(f"DynamoDB server error: {e}")
        
    except Exception as e:
        log_error("Failed to store test result", e, test_vector.vector_id)
        raise


@tracer.capture_method
def _compute_execution_result_hash(execution_result: ExecutionResult) -> str:
    """
    Compute SHA-256 hash of execution result.
    
    Requirement 15.3: Store execution output hashes
    
    Args:
        execution_result: Execution result to hash
        
    Returns:
        SHA-256 hash as hex string
    """
    # Create canonical representation for hashing
    hash_input = b''
    hash_input += str(execution_result.return_value).encode('utf-8')
    hash_input += b'|'
    hash_input += execution_result.stdout
    hash_input += b'|'
    hash_input += execution_result.stderr
    hash_input += b'|'
    hash_input += execution_result.execution_timestamp.isoformat().encode('utf-8')
    
    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(hash_input).digest()
    hash_hex = hash_bytes.hex()
    
    return hash_hex


@tracer.capture_method
def _compute_complete_test_result_hash(
    test_vector: TestVector,
    legacy_result: ExecutionResult,
    modern_result: ExecutionResult,
    comparison: ComparisonResult
) -> str:
    """
    Compute SHA-256 hash of complete test result.
    
    Requirements 16.1, 16.2: Generate SHA-256 hash of complete test result
    
    Args:
        test_vector: Test vector
        legacy_result: Legacy execution result
        modern_result: Modern execution result
        comparison: Comparison result
        
    Returns:
        SHA-256 hash as hex string
    """
    # Create canonical representation for hashing
    hash_input = f"{test_vector.vector_id}|"
    hash_input += f"{json.dumps(test_vector.input_parameters, sort_keys=True)}|"
    hash_input += f"{legacy_result.return_value}|"
    hash_input += f"{legacy_result.stdout.hex()}|"
    hash_input += f"{legacy_result.stderr.hex()}|"
    hash_input += f"{modern_result.return_value}|"
    hash_input += f"{modern_result.stdout.hex()}|"
    hash_input += f"{modern_result.stderr.hex()}|"
    hash_input += f"{comparison.match}|"
    hash_input += f"{comparison.comparison_timestamp.isoformat()}"
    
    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(hash_input.encode('utf-8')).digest()
    hash_hex = hash_bytes.hex()
    
    logger.debug(
        f"Computed complete test result hash",
        extra={
            'test_vector_id': test_vector.vector_id,
            'hash': hash_hex
        }
    )
    
    return hash_hex


@tracer.capture_method
@with_retry(max_retries=3)
def query_test_results_by_status(status: str, limit: int = 100) -> list:
    """
    Query test results by status using GSI.
    
    Args:
        status: Test status ('PASS' or 'FAIL')
        limit: Maximum number of results to return
        
    Returns:
        List of test result items
    """
    logger.info(
        f"Querying test results by status",
        extra={'status': status, 'limit': limit}
    )
    
    try:
        response = dynamodb_client.query(
            TableName=TEST_RESULTS_TABLE,
            IndexName='status-index',
            KeyConditionExpression='#status = :status',
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':status': {'S': status}
            },
            Limit=limit,
            ScanIndexForward=False  # Most recent first
        )
        
        items = response.get('Items', [])
        
        logger.info(
            f"Retrieved {len(items)} test results",
            extra={'status': status, 'count': len(items)}
        )
        
        return items
        
    except Exception as e:
        log_error("Failed to query test results", e, status)
        raise


@tracer.capture_method
@with_retry(max_retries=3)
def get_test_result(test_id: str, execution_timestamp: str) -> Optional[dict]:
    """
    Get specific test result by test ID and execution timestamp.
    
    Args:
        test_id: Test vector ID
        execution_timestamp: Execution timestamp (ISO 8601)
        
    Returns:
        Test result item or None if not found
    """
    logger.info(
        f"Getting test result",
        extra={'test_id': test_id, 'execution_timestamp': execution_timestamp}
    )
    
    try:
        response = dynamodb_client.get_item(
            TableName=TEST_RESULTS_TABLE,
            Key={
                'test_id': {'S': test_id},
                'execution_timestamp': {'S': execution_timestamp}
            }
        )
        
        item = response.get('Item')
        
        if item:
            logger.info(f"Test result found", extra={'test_id': test_id})
        else:
            logger.warning(f"Test result not found", extra={'test_id': test_id})
        
        return item
        
    except Exception as e:
        log_error("Failed to get test result", e, test_id)
        raise
