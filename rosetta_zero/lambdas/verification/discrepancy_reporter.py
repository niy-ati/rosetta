"""
Discrepancy Report Generation.

Generates detailed reports when behavioral differences are detected.
Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

import boto3
from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import (
    TestVector,
    ExecutionResult,
    ComparisonResult,
    DiscrepancyReport,
)
from rosetta_zero.utils import (
    logger,
    tracer,
    log_error,
    log_test_failure,
    BehavioralDiscrepancyError,
)

# AWS clients
s3_client = boto3.client('s3')
logs_client = boto3.client('logs')
events_client = boto3.client('events')

# Environment variables
DISCREPANCY_BUCKET = os.environ.get('DISCREPANCY_BUCKET', 'rosetta-zero-discrepancy-reports')
KMS_KEY_ID = os.environ.get('KMS_KEY_ID', '')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')


@tracer.capture_method
def generate_discrepancy_report(
    test_vector: TestVector,
    legacy_result: ExecutionResult,
    modern_result: ExecutionResult,
    comparison: ComparisonResult
) -> DiscrepancyReport:
    """
    Generate detailed discrepancy report on test failure.
    
    Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9
    
    Includes:
    - Test vector input values (Requirement 14.2)
    - Legacy output values (Requirement 14.3)
    - Modern output values (Requirement 14.4)
    - Byte-level diff (Requirement 14.5)
    - Execution timestamps (Requirement 14.6)
    - All side effects (Requirement 14.7)
    
    Stores report in S3 (Requirement 14.8)
    Logs failure to CloudWatch (Requirement 14.7)
    Publishes failure event to EventBridge (Requirement 14.9)
    
    Args:
        test_vector: Test vector that produced different outputs
        legacy_result: Legacy execution result
        modern_result: Modern execution result
        comparison: Comparison result with differences
        
    Returns:
        DiscrepancyReport stored in S3
        
    Raises:
        BehavioralDiscrepancyError: Always raised after report generation
    """
    logger.error(
        f"Behavioral discrepancy detected for test vector: {test_vector.vector_id}",
        extra={
            'test_vector_id': test_vector.vector_id,
            'return_value_match': comparison.return_value_match,
            'stdout_match': comparison.stdout_match,
            'stderr_match': comparison.stderr_match,
            'side_effects_match': comparison.side_effects_match
        }
    )
    
    # Generate report ID
    report_id = f"discrepancy-{test_vector.vector_id}-{uuid.uuid4().hex[:8]}"
    
    # Create discrepancy report (Requirements 14.1-14.7)
    report = DiscrepancyReport(
        report_id=report_id,
        generation_timestamp=datetime.utcnow().isoformat(),
        test_vector_id=test_vector.vector_id,  # Requirement 14.2
        legacy_result_hash=legacy_result.compute_hash(),  # Requirement 14.3
        modern_result_hash=modern_result.compute_hash(),  # Requirement 14.4
        comparison_result=comparison,  # Requirements 14.5, 14.6, 14.7
        root_cause_analysis=None  # Optional: Could invoke Bedrock for analysis
    )
    
    # Store report in S3 (Requirement 14.8)
    s3_key = _store_report_in_s3(report)
    
    # Log failure to CloudWatch (Requirement 14.7)
    _log_failure_to_cloudwatch(report, s3_key)
    
    # Publish failure event to EventBridge (Requirement 14.9)
    _publish_failure_event(report, s3_key)
    
    logger.info(
        f"Discrepancy report generated",
        extra={
            'report_id': report_id,
            's3_location': f"s3://{DISCREPANCY_BUCKET}/{s3_key}"
        }
    )
    
    return report


@tracer.capture_method
def _store_report_in_s3(report: DiscrepancyReport) -> str:
    """
    Store discrepancy report in S3.
    
    Requirement 14.8: Store discrepancy report in S3
    
    Args:
        report: Discrepancy report to store
        
    Returns:
        S3 key where report was stored
    """
    # Generate S3 key with date partitioning
    date_prefix = report.generation_timestamp.strftime('%Y/%m/%d')
    s3_key = f"{date_prefix}/{report.report_id}/report.json"
    
    # Serialize report to JSON
    report_json = report.to_json()
    
    try:
        # Upload to S3 with KMS encryption
        s3_client.put_object(
            Bucket=DISCREPANCY_BUCKET,
            Key=s3_key,
            Body=report_json,
            ContentType='application/json',
            ServerSideEncryption='aws:kms',
            SSEKMSKeyId=KMS_KEY_ID,
            Metadata={
                'report-id': report.report_id,
                'test-vector-id': report.test_vector.vector_id,
                'generation-timestamp': report.generation_timestamp.isoformat()
            }
        )
        
        logger.info(
            f"Discrepancy report stored in S3",
            extra={
                'report_id': report.report_id,
                's3_bucket': DISCREPANCY_BUCKET,
                's3_key': s3_key
            }
        )
        
        return s3_key
        
    except Exception as e:
        log_error(
            "Failed to store discrepancy report in S3",
            e,
            report.report_id
        )
        raise


@tracer.capture_method
def _log_failure_to_cloudwatch(report: DiscrepancyReport, s3_key: str) -> None:
    """
    Log test failure to CloudWatch.
    
    Requirement 14.7: Log failure to CloudWatch before any correction attempts
    Requirement 18.7: Log test failure before correction
    
    Args:
        report: Discrepancy report
        s3_key: S3 key where report is stored
    """
    # Use PowerTools structured logging
    log_test_failure(
        test_vector_id=report.test_vector.vector_id,
        report_id=report.report_id,
        s3_location=f"s3://{DISCREPANCY_BUCKET}/{s3_key}",
        return_value_match=report.comparison.return_value_match,
        stdout_match=report.comparison.stdout_match,
        stderr_match=report.comparison.stderr_match,
        side_effects_match=report.comparison.side_effects_match,
        legacy_return_value=report.legacy_result.return_value,
        modern_return_value=report.modern_result.return_value
    )
    
    logger.error(
        "TEST FAILURE - Behavioral discrepancy detected",
        extra={
            'report_id': report.report_id,
            'test_vector_id': report.test_vector.vector_id,
            's3_location': f"s3://{DISCREPANCY_BUCKET}/{s3_key}",
            'return_value_match': report.comparison.return_value_match,
            'stdout_match': report.comparison.stdout_match,
            'stderr_match': report.comparison.stderr_match,
            'side_effects_match': report.comparison.side_effects_match,
            'legacy_return': report.legacy_result.return_value,
            'modern_return': report.modern_result.return_value,
            'legacy_stdout_size': len(report.legacy_result.stdout),
            'modern_stdout_size': len(report.modern_result.stdout),
            'legacy_stderr_size': len(report.legacy_result.stderr),
            'modern_stderr_size': len(report.modern_result.stderr),
            'generation_timestamp': report.generation_timestamp.isoformat()
        }
    )


@tracer.capture_method
def _publish_failure_event(report: DiscrepancyReport, s3_key: str) -> None:
    """
    Publish failure event to EventBridge.
    
    Requirement 14.9: Publish failure event to EventBridge
    
    Args:
        report: Discrepancy report
        s3_key: S3 key where report is stored
    """
    event_detail = {
        'report_id': report.report_id,
        'test_vector_id': report.test_vector.vector_id,
        's3_location': f"s3://{DISCREPANCY_BUCKET}/{s3_key}",
        's3_bucket': DISCREPANCY_BUCKET,
        's3_key': s3_key,
        'generation_timestamp': report.generation_timestamp.isoformat(),
        'comparison_summary': {
            'match': report.comparison.match,
            'return_value_match': report.comparison.return_value_match,
            'stdout_match': report.comparison.stdout_match,
            'stderr_match': report.comparison.stderr_match,
            'side_effects_match': report.comparison.side_effects_match
        },
        'legacy_return_value': report.legacy_result.return_value,
        'modern_return_value': report.modern_result.return_value
    }
    
    try:
        events_client.put_events(
            Entries=[
                {
                    'Source': 'rosetta-zero.verification',
                    'DetailType': 'Behavioral Discrepancy Detected',
                    'Detail': json.dumps(event_detail),
                    'EventBusName': EVENT_BUS_NAME
                }
            ]
        )
        
        logger.info(
            f"Failure event published to EventBridge",
            extra={
                'report_id': report.report_id,
                'event_bus': EVENT_BUS_NAME
            }
        )
        
    except Exception as e:
        log_error(
            "Failed to publish failure event to EventBridge",
            e,
            report.report_id
        )
        # Don't raise - report is already stored in S3


@tracer.capture_method
def handle_behavioral_discrepancy(
    test_vector: TestVector,
    legacy_result: ExecutionResult,
    modern_result: ExecutionResult,
    comparison: ComparisonResult
) -> None:
    """
    Handle behavioral discrepancy detection.
    
    Generates discrepancy report and halts pipeline.
    
    Args:
        test_vector: Test vector that produced different outputs
        legacy_result: Legacy execution result
        modern_result: Modern execution result
        comparison: Comparison result with differences
        
    Raises:
        BehavioralDiscrepancyError: Always raised to halt pipeline
    """
    # Generate discrepancy report
    report = generate_discrepancy_report(
        test_vector,
        legacy_result,
        modern_result,
        comparison
    )
    
    # Halt pipeline by raising error
    raise BehavioralDiscrepancyError(
        f"Behavioral discrepancy detected. Report: {report.report_id}. "
        f"Location: s3://{DISCREPANCY_BUCKET}/{report.report_id}/report.json"
    )
