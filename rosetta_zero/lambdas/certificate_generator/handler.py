"""
Certificate Generator Lambda Handler.

This Lambda function generates cryptographically signed equivalence certificates
when all test vectors pass. It implements the Trust Phase of the Rosetta Zero workflow.

Requirements: 17.1-17.9
"""

import json
import os
from typing import Dict, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext
import boto3

from .certificate_generation import generate_certificate
from .certificate_signing import sign_certificate
from .event_publisher import publish_completion_event
from .error_handler import handle_certificate_error
from rosetta_zero.utils import RetryStrategy, log_certificate_generated

# Initialize PowerTools
logger = Logger(service="certificate_generator")
tracer = Tracer(service="certificate_generator")
metrics = Metrics(namespace="RosettaZero", service="certificate_generator")

# Environment variables
TEST_RESULTS_TABLE = os.environ.get('TEST_RESULTS_TABLE', 'rosetta-zero-test-results')
CERTIFICATES_BUCKET = os.environ.get('CERTIFICATES_BUCKET', 'rosetta-zero-certificates')
KMS_SIGNING_KEY_ID = os.environ.get('KMS_SIGNING_KEY_ID')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'default')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

# AWS clients (initialized lazily)
_dynamodb = None
_s3 = None
_kms = None
_eventbridge = None
_sns = None


def _get_clients():
    """Get or initialize AWS clients."""
    global _dynamodb, _s3, _kms, _eventbridge, _sns
    
    if _dynamodb is None:
        _dynamodb = boto3.client('dynamodb')
    if _s3 is None:
        _s3 = boto3.client('s3')
    if _kms is None:
        _kms = boto3.client('kms')
    if _eventbridge is None:
        _eventbridge = boto3.client('events')
    if _sns is None:
        _sns = boto3.client('sns')
    
    return _dynamodb, _s3, _kms, _eventbridge, _sns


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for certificate generation.
    
    Event structure:
    {
        "workflow_id": "string",
        "legacy_artifact": {
            "identifier": "string",
            "version": "string",
            "sha256_hash": "string",
            "s3_location": "string",
            "creation_timestamp": "ISO8601"
        },
        "modern_implementation": {
            "identifier": "string",
            "version": "string",
            "sha256_hash": "string",
            "s3_location": "string",
            "creation_timestamp": "ISO8601"
        },
        "random_seed": int,
        "coverage_report": {
            "branch_coverage_percent": float,
            "entry_points_covered": int,
            "total_entry_points": int,
            "uncovered_branches": []
        }
    }
    
    Returns:
        {
            "statusCode": 200,
            "certificate_id": "string",
            "s3_location": "string",
            "signature_valid": bool
        }
    """
    
    logger.info("Certificate generation started", extra={
        'workflow_id': event.get('workflow_id'),
        'component': 'certificate_generator'
    })
    
    # Get AWS clients
    dynamodb, s3, kms, eventbridge, sns = _get_clients()
    
    retry_strategy = RetryStrategy(max_retries=3, backoff_base=2)
    
    try:
        # Step 1: Generate equivalence certificate
        logger.info("Generating equivalence certificate")
        certificate = retry_strategy.execute_with_retry(
            lambda: generate_certificate(
                dynamodb_client=dynamodb,
                s3_client=s3,
                test_results_table=TEST_RESULTS_TABLE,
                legacy_artifact=event['legacy_artifact'],
                modern_implementation=event['modern_implementation'],
                random_seed=event['random_seed'],
                coverage_report=event['coverage_report']
            )
        )
        
        # Step 2: Sign certificate with KMS
        logger.info("Signing certificate with KMS", extra={
            'certificate_id': certificate.certificate_id
        })
        signed_certificate = retry_strategy.execute_with_retry(
            lambda: sign_certificate(
                certificate=certificate,
                kms_client=kms,
                kms_key_id=KMS_SIGNING_KEY_ID
            )
        )
        
        # Step 3: Store signed certificate in S3
        logger.info("Storing signed certificate in S3")
        s3_key = f"certificates/{certificate.certificate_id}/signed-certificate.json"
        retry_strategy.execute_with_retry(
            lambda: s3.put_object(
                Bucket=CERTIFICATES_BUCKET,
                Key=s3_key,
                Body=signed_certificate.to_json().encode('utf-8'),
                ServerSideEncryption='aws:kms',
                ContentType='application/json'
            )
        )
        
        s3_location = f"s3://{CERTIFICATES_BUCKET}/{s3_key}"
        logger.info("Certificate stored in S3", extra={
            'certificate_id': certificate.certificate_id,
            's3_location': s3_location
        })
        
        # Step 4: Publish completion event
        logger.info("Publishing certificate completion event")
        retry_strategy.execute_with_retry(
            lambda: publish_completion_event(
                eventbridge_client=eventbridge,
                sns_client=sns,
                event_bus_name=EVENT_BUS_NAME,
                sns_topic_arn=SNS_TOPIC_ARN,
                certificate_id=certificate.certificate_id,
                s3_location=s3_location,
                workflow_id=event.get('workflow_id')
            )
        )
        
        # Log certificate generation
        log_certificate_generated(
            certificate_id=certificate.certificate_id,
            s3_location=s3_location,
            total_tests=certificate.total_test_vectors,
            coverage_percent=event['coverage_report']['branch_coverage_percent']
        )
        
        metrics.add_metric(name="CertificateGenerated", unit="Count", value=1)
        
        return {
            'statusCode': 200,
            'certificate_id': certificate.certificate_id,
            's3_location': s3_location,
            'signature_valid': True,
            'total_test_vectors': certificate.total_test_vectors,
            'test_results_hash': certificate.test_results_hash
        }
        
    except Exception as e:
        logger.error("Certificate generation failed", extra={
            'error': str(e),
            'workflow_id': event.get('workflow_id')
        })
        
        # Handle error with retry logic and operator alerts
        handle_certificate_error(
            error=e,
            sns_client=sns,
            sns_topic_arn=SNS_TOPIC_ARN,
            workflow_id=event.get('workflow_id'),
            context=event
        )
        
        metrics.add_metric(name="CertificateGenerationFailed", unit="Count", value=1)
        
        return {
            'statusCode': 500,
            'error': str(e),
            'workflow_id': event.get('workflow_id')
        }
