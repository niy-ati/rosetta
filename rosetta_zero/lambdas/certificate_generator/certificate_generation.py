"""
Certificate generation logic for equivalence certificates.

This module implements the generation of equivalence certificates from test results,
including verification that all tests passed and computation of cryptographic hashes.

Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from aws_lambda_powertools import Logger
import uuid

from rosetta_zero.models import (
    EquivalenceCertificate,
    ArtifactMetadata,
    CoverageReport
)

logger = Logger(child=True)


def generate_certificate(
    dynamodb_client,
    s3_client,
    test_results_table: str,
    legacy_artifact: Dict[str, Any],
    modern_implementation: Dict[str, Any],
    random_seed: int,
    coverage_report: Dict[str, Any]
) -> EquivalenceCertificate:
    """
    Generate equivalence certificate from test results.
    
    This function:
    1. Queries all test results from DynamoDB
    2. Verifies all tests passed (no failures)
    3. Computes SHA-256 hash of all test results
    4. Collects individual test result hashes
    5. Includes legacy artifact metadata
    6. Includes modern implementation metadata
    7. Includes total test vector count
    8. Includes test execution date range
    9. Includes random seed for reproducibility
    10. Includes coverage report with branch coverage percentage
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        s3_client: Boto3 S3 client
        test_results_table: DynamoDB table name for test results
        legacy_artifact: Legacy artifact metadata dict
        modern_implementation: Modern implementation metadata dict
        random_seed: Random seed used for test generation
        coverage_report: Coverage report dict
        
    Returns:
        EquivalenceCertificate instance
        
    Raises:
        ValueError: If any tests failed or no tests found
        
    Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6
    """
    
    logger.info("Starting certificate generation")
    
    # Step 1: Query all test results from DynamoDB
    logger.info("Querying test results from DynamoDB", extra={
        'table': test_results_table
    })
    
    test_results = _query_all_test_results(dynamodb_client, test_results_table)
    
    if not test_results:
        raise ValueError("No test results found - cannot generate certificate")
    
    logger.info(f"Retrieved {len(test_results)} test results")
    
    # Step 2: Verify all tests passed
    failed_tests = [r for r in test_results if r.get('status', {}).get('S') == 'FAIL']
    
    if failed_tests:
        logger.error(f"Found {len(failed_tests)} failed tests - cannot generate certificate")
        raise ValueError(
            f"Cannot generate certificate: {len(failed_tests)} tests failed. "
            f"All tests must pass for equivalence certification."
        )
    
    logger.info("All tests passed - proceeding with certificate generation")
    
    # Step 3: Compute SHA-256 hash of all test results
    logger.info("Computing SHA-256 hash of all test results")
    test_results_hash = _compute_test_results_hash(test_results)
    
    # Step 4: Collect individual test result hashes
    logger.info("Collecting individual test result hashes")
    individual_test_hashes = _collect_individual_hashes(test_results)
    
    # Step 5-6: Parse artifact metadata
    legacy_artifact_meta = ArtifactMetadata(
        identifier=legacy_artifact['identifier'],
        version=legacy_artifact['version'],
        sha256_hash=legacy_artifact['sha256_hash'],
        s3_location=legacy_artifact['s3_location'],
        creation_timestamp=legacy_artifact['creation_timestamp']
    )
    
    modern_impl_meta = ArtifactMetadata(
        identifier=modern_implementation['identifier'],
        version=modern_implementation['version'],
        sha256_hash=modern_implementation['sha256_hash'],
        s3_location=modern_implementation['s3_location'],
        creation_timestamp=modern_implementation['creation_timestamp']
    )
    
    # Step 7: Get total test vector count
    total_test_vectors = len(test_results)
    
    # Step 8: Determine test execution date range
    test_execution_start, test_execution_end = _get_execution_date_range(test_results)
    
    # Step 9: Include random seed (already provided)
    
    # Step 10: Parse coverage report
    coverage = CoverageReport(
        branch_coverage_percent=coverage_report['branch_coverage_percent'],
        entry_points_covered=coverage_report['entry_points_covered'],
        total_entry_points=coverage_report['total_entry_points'],
        uncovered_branches=coverage_report.get('uncovered_branches', [])
    )
    
    # Generate certificate ID
    certificate_id = str(uuid.uuid4())
    generation_timestamp = datetime.utcnow().isoformat() + 'Z'
    
    # Create EquivalenceCertificate
    certificate = EquivalenceCertificate(
        certificate_id=certificate_id,
        generation_timestamp=generation_timestamp,
        legacy_artifact=legacy_artifact_meta,
        modern_implementation=modern_impl_meta,
        total_test_vectors=total_test_vectors,
        test_execution_start=test_execution_start,
        test_execution_end=test_execution_end,
        test_results_hash=test_results_hash,
        individual_test_hashes=individual_test_hashes,
        random_seed=random_seed,
        coverage_report=coverage
    )
    
    logger.info("Certificate generated successfully", extra={
        'certificate_id': certificate_id,
        'total_test_vectors': total_test_vectors,
        'test_results_hash': test_results_hash,
        'branch_coverage_percent': coverage.branch_coverage_percent
    })
    
    return certificate


def _query_all_test_results(dynamodb_client, table_name: str) -> List[Dict[str, Any]]:
    """
    Query all test results from DynamoDB.
    
    Uses scan operation to retrieve all test results. For production systems
    with millions of test results, this should be paginated.
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        table_name: DynamoDB table name
        
    Returns:
        List of test result items
    """
    
    test_results = []
    
    # Scan with pagination
    scan_kwargs = {
        'TableName': table_name
    }
    
    while True:
        response = dynamodb_client.scan(**scan_kwargs)
        test_results.extend(response.get('Items', []))
        
        # Check if there are more results
        if 'LastEvaluatedKey' not in response:
            break
            
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    
    return test_results


def _compute_test_results_hash(test_results: List[Dict[str, Any]]) -> str:
    """
    Compute SHA-256 hash of all test results.
    
    Creates a canonical representation of all test results and computes
    a single hash for integrity verification.
    
    Args:
        test_results: List of test result items from DynamoDB
        
    Returns:
        Hex-encoded SHA-256 hash
    """
    
    # Sort test results by test_id for canonical ordering
    sorted_results = sorted(
        test_results,
        key=lambda r: r.get('test_id', {}).get('S', '')
    )
    
    # Create canonical JSON representation
    canonical_json = json.dumps(sorted_results, sort_keys=True)
    
    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(canonical_json.encode('utf-8'))
    
    return hash_obj.hexdigest()


def _collect_individual_hashes(test_results: List[Dict[str, Any]]) -> List[str]:
    """
    Collect individual test result hashes.
    
    Each test result should have a pre-computed hash stored in DynamoDB.
    This function extracts those hashes for inclusion in the certificate.
    
    Args:
        test_results: List of test result items from DynamoDB
        
    Returns:
        List of hex-encoded SHA-256 hashes
    """
    
    hashes = []
    
    for result in test_results:
        # Try to get pre-computed hash from comparison_result_hash field
        result_hash = result.get('comparison_result_hash', {}).get('S')
        
        if result_hash:
            hashes.append(result_hash)
        else:
            # If no pre-computed hash, compute from the result itself
            result_json = json.dumps(result, sort_keys=True)
            result_hash = hashlib.sha256(result_json.encode('utf-8')).hexdigest()
            hashes.append(result_hash)
    
    # Sort hashes for canonical ordering
    return sorted(hashes)


def _get_execution_date_range(test_results: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    Determine test execution date range.
    
    Finds the earliest and latest execution timestamps from test results.
    
    Args:
        test_results: List of test result items from DynamoDB
        
    Returns:
        Tuple of (start_timestamp, end_timestamp) in ISO 8601 format
    """
    
    timestamps = []
    
    for result in test_results:
        timestamp_str = result.get('execution_timestamp', {}).get('S')
        if timestamp_str:
            timestamps.append(timestamp_str)
    
    if not timestamps:
        # If no timestamps found, use current time
        current_time = datetime.utcnow().isoformat() + 'Z'
        return (current_time, current_time)
    
    # Sort timestamps
    timestamps.sort()
    
    return (timestamps[0], timestamps[-1])
