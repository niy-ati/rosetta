"""
Compliance Report Generator Lambda Function

Generates comprehensive compliance reports for regulatory submission including:
- All test results
- Audit log references
- Equivalence certificate
- Discrepancy reports (if any)
"""

import json
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from rosetta_zero.models.comparison import (
    ComplianceReport,
    SignedCertificate,
    DiscrepancyReport,
    ArtifactMetadata,
    CoverageReport,
)

logger = Logger()
tracer = Tracer()

# AWS clients - initialized lazily to avoid issues in testing
s3_client = None
dynamodb = None
kms_client = None
logs_client = None


def get_aws_clients():
    """Initialize AWS clients lazily."""
    global s3_client, dynamodb, kms_client, logs_client
    
    if s3_client is None:
        s3_client = boto3.client('s3')
    if dynamodb is None:
        dynamodb = boto3.resource('dynamodb')
    if kms_client is None:
        kms_client = boto3.client('kms')
    if logs_client is None:
        logs_client = boto3.client('logs')
    
    return s3_client, dynamodb, kms_client, logs_client

# Environment variables
TEST_RESULTS_TABLE = os.environ.get('TEST_RESULTS_TABLE', 'rosetta-zero-test-results')
CERTIFICATES_BUCKET = os.environ.get('CERTIFICATES_BUCKET', 'rosetta-zero-certificates')
DISCREPANCY_REPORTS_BUCKET = os.environ.get('DISCREPANCY_REPORTS_BUCKET', 'rosetta-zero-discrepancy-reports')
COMPLIANCE_REPORTS_BUCKET = os.environ.get('COMPLIANCE_REPORTS_BUCKET', 'rosetta-zero-compliance-reports')
KMS_SIGNING_KEY_ID = os.environ.get('KMS_SIGNING_KEY_ID')


@tracer.capture_method
def get_all_test_results(workflow_id: str) -> Dict[str, Any]:
    """
    Query all test results from DynamoDB for a workflow.
    
    Returns:
        Dictionary with test statistics and result hashes
    """
    logger.info(f"Querying test results for workflow {workflow_id}")
    
    _, dynamodb_resource, _, _ = get_aws_clients()
    table = dynamodb_resource.Table(TEST_RESULTS_TABLE)
    
    # Scan table for all test results (in production, use workflow_id index)
    response = table.scan()
    items = response.get('Items', [])
    
    # Continue scanning if there are more items
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    # Calculate statistics
    total_tests = len(items)
    passed_tests = sum(1 for item in items if item.get('status') == 'PASS')
    failed_tests = sum(1 for item in items if item.get('status') == 'FAIL')
    
    # Collect all test result hashes
    test_hashes = [item.get('comparison_result_hash', '') for item in items]
    
    # Compute aggregate hash of all test results
    combined_hash = hashlib.sha256()
    for test_hash in sorted(test_hashes):
        combined_hash.update(test_hash.encode('utf-8'))
    test_results_hash = combined_hash.hexdigest()
    
    # Get execution time range
    timestamps = [item.get('execution_timestamp', '') for item in items if item.get('execution_timestamp')]
    test_execution_start = min(timestamps) if timestamps else datetime.utcnow().isoformat()
    test_execution_end = max(timestamps) if timestamps else datetime.utcnow().isoformat()
    
    logger.info(f"Test results: {total_tests} total, {passed_tests} passed, {failed_tests} failed")
    
    return {
        'total_tests': total_tests,
        'passed_tests': passed_tests,
        'failed_tests': failed_tests,
        'test_results_hash': test_results_hash,
        'individual_test_hashes': test_hashes,
        'test_execution_start': test_execution_start,
        'test_execution_end': test_execution_end,
    }


@tracer.capture_method
def get_equivalence_certificate(workflow_id: str) -> Optional[SignedCertificate]:
    """
    Retrieve the equivalence certificate from S3 if it exists.
    
    Returns:
        SignedCertificate object or None if not found
    """
    logger.info(f"Retrieving equivalence certificate for workflow {workflow_id}")
    
    s3, _, _, _ = get_aws_clients()
    
    try:
        # Try to find certificate in S3
        # In production, use workflow_id to construct the key
        response = s3.list_objects_v2(
            Bucket=CERTIFICATES_BUCKET,
            Prefix=f'certificates/'
        )
        
        if 'Contents' not in response or len(response['Contents']) == 0:
            logger.warning("No equivalence certificate found")
            return None
        
        # Get the most recent certificate
        latest_cert = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[0]
        cert_key = latest_cert['Key']
        
        # Download certificate
        cert_response = s3.get_object(
            Bucket=CERTIFICATES_BUCKET,
            Key=cert_key
        )
        cert_json = cert_response['Body'].read().decode('utf-8')
        
        # Parse certificate
        certificate = SignedCertificate.from_json(cert_json)
        logger.info(f"Retrieved certificate {certificate.certificate.certificate_id}")
        
        return certificate
        
    except Exception as e:
        logger.error(f"Error retrieving equivalence certificate: {e}")
        return None


@tracer.capture_method
def get_discrepancy_reports(workflow_id: str) -> List[DiscrepancyReport]:
    """
    Retrieve all discrepancy reports from S3.
    
    Returns:
        List of DiscrepancyReport objects
    """
    logger.info(f"Retrieving discrepancy reports for workflow {workflow_id}")
    
    s3, _, _, _ = get_aws_clients()
    
    try:
        # List all discrepancy reports in S3
        response = s3.list_objects_v2(
            Bucket=DISCREPANCY_REPORTS_BUCKET,
            Prefix=f'discrepancy-reports/'
        )
        
        if 'Contents' not in response:
            logger.info("No discrepancy reports found")
            return []
        
        discrepancy_reports = []
        
        for obj in response['Contents']:
            # Download each report
            report_response = s3.get_object(
                Bucket=DISCREPANCY_REPORTS_BUCKET,
                Key=obj['Key']
            )
            report_json = report_response['Body'].read().decode('utf-8')
            
            # Parse report
            report = DiscrepancyReport.from_json(report_json)
            discrepancy_reports.append(report)
        
        logger.info(f"Retrieved {len(discrepancy_reports)} discrepancy reports")
        return discrepancy_reports
        
    except Exception as e:
        logger.error(f"Error retrieving discrepancy reports: {e}")
        return []


@tracer.capture_method
def get_audit_log_references(workflow_id: str, start_time: str, end_time: str) -> List[str]:
    """
    Get references to all CloudWatch Log Groups containing audit logs.
    
    Returns:
        List of CloudWatch Log Group names
    """
    logger.info(f"Retrieving audit log references for workflow {workflow_id}")
    
    _, _, _, logs = get_aws_clients()
    
    try:
        # List all log groups with rosetta-zero prefix
        log_groups = []
        paginator = logs.get_paginator('describe_log_groups')
        
        for page in paginator.paginate(logGroupNamePrefix='/aws/lambda/rosetta-zero'):
            for log_group in page.get('logGroups', []):
                log_groups.append(log_group['logGroupName'])
        
        logger.info(f"Found {len(log_groups)} audit log groups")
        return log_groups
        
    except Exception as e:
        logger.error(f"Error retrieving audit log references: {e}")
        return []


@tracer.capture_method
def generate_compliance_report(
    workflow_id: str,
    legacy_artifact: ArtifactMetadata,
    modern_implementation: ArtifactMetadata,
    coverage_report: CoverageReport
) -> ComplianceReport:
    """
    Generate comprehensive compliance report.
    
    Args:
        workflow_id: Unique workflow identifier
        legacy_artifact: Metadata for legacy artifact
        modern_implementation: Metadata for modern implementation
        coverage_report: Test coverage metrics
        
    Returns:
        ComplianceReport object
    """
    logger.info(f"Generating compliance report for workflow {workflow_id}")
    
    # Get all test results
    test_results = get_all_test_results(workflow_id)
    
    # Get equivalence certificate (if exists)
    equivalence_certificate = get_equivalence_certificate(workflow_id)
    
    # Get discrepancy reports (if any)
    discrepancy_reports = get_discrepancy_reports(workflow_id)
    
    # Get audit log references
    audit_log_groups = get_audit_log_references(
        workflow_id,
        test_results['test_execution_start'],
        test_results['test_execution_end']
    )
    
    # Determine compliance status
    compliance_status = 'COMPLIANT' if test_results['failed_tests'] == 0 and equivalence_certificate else 'NON_COMPLIANT'
    
    compliance_notes = None
    if compliance_status == 'NON_COMPLIANT':
        if test_results['failed_tests'] > 0:
            compliance_notes = f"Behavioral discrepancies detected in {test_results['failed_tests']} test vectors. See discrepancy reports for details."
        else:
            compliance_notes = "No equivalence certificate available."
    
    # Create compliance report
    report_id = f"compliance-{workflow_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    compliance_report = ComplianceReport(
        report_id=report_id,
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id=workflow_id,
        total_test_vectors=test_results['total_tests'],
        passed_tests=test_results['passed_tests'],
        failed_tests=test_results['failed_tests'],
        test_results_hash=test_results['test_results_hash'],
        equivalence_certificate=equivalence_certificate,
        discrepancy_reports=discrepancy_reports,
        audit_log_groups=audit_log_groups,
        audit_log_query_start=test_results['test_execution_start'],
        audit_log_query_end=test_results['test_execution_end'],
        legacy_artifact=legacy_artifact,
        modern_implementation=modern_implementation,
        coverage_report=coverage_report,
        compliance_status=compliance_status,
        compliance_notes=compliance_notes,
    )
    
    logger.info(f"Generated compliance report {report_id} with status {compliance_status}")
    
    return compliance_report


@tracer.capture_method
def sign_compliance_report(compliance_report: ComplianceReport) -> bytes:
    """
    Sign compliance report using AWS KMS.
    
    Args:
        compliance_report: ComplianceReport to sign
        
    Returns:
        Signature bytes
    """
    logger.info(f"Signing compliance report {compliance_report.report_id}")
    
    _, _, kms, _ = get_aws_clients()
    
    # Serialize report to canonical JSON
    report_json = compliance_report.to_json()
    report_bytes = report_json.encode('utf-8')
    
    # Compute SHA-256 hash
    report_hash = hashlib.sha256(report_bytes).digest()
    
    # Sign with KMS
    response = kms.sign(
        KeyId=KMS_SIGNING_KEY_ID,
        Message=report_hash,
        MessageType='DIGEST',
        SigningAlgorithm='RSASSA_PSS_SHA_256'
    )
    
    signature = response['Signature']
    logger.info(f"Signed compliance report with key {KMS_SIGNING_KEY_ID}")
    
    return signature


@tracer.capture_method
def store_compliance_report(
    compliance_report: ComplianceReport,
    signature: bytes
) -> str:
    """
    Store compliance report in S3.
    
    Args:
        compliance_report: ComplianceReport to store
        signature: KMS signature
        
    Returns:
        S3 key where report was stored
    """
    logger.info(f"Storing compliance report {compliance_report.report_id}")
    
    s3, _, _, _ = get_aws_clients()
    
    # Create signed report object
    signed_report = {
        'report': json.loads(compliance_report.to_json()),
        'signature': signature.hex(),
        'signing_key_id': KMS_SIGNING_KEY_ID,
        'signature_algorithm': 'RSASSA_PSS_SHA_256',
        'signing_timestamp': datetime.utcnow().isoformat(),
    }
    
    # Store JSON report
    json_key = f"compliance-reports/{compliance_report.workflow_id}/{compliance_report.report_id}.json"
    s3.put_object(
        Bucket=COMPLIANCE_REPORTS_BUCKET,
        Key=json_key,
        Body=json.dumps(signed_report, indent=2),
        ContentType='application/json',
        ServerSideEncryption='aws:kms'
    )
    
    # Generate and store HTML report
    html_report = compliance_report.generate_html_report()
    html_key = f"compliance-reports/{compliance_report.workflow_id}/{compliance_report.report_id}.html"
    s3.put_object(
        Bucket=COMPLIANCE_REPORTS_BUCKET,
        Key=html_key,
        Body=html_report,
        ContentType='text/html',
        ServerSideEncryption='aws:kms'
    )
    
    logger.info(f"Stored compliance report at s3://{COMPLIANCE_REPORTS_BUCKET}/{json_key}")
    
    return json_key


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Lambda handler for compliance report generation.
    
    Event structure:
    {
        "workflow_id": "workflow-123",
        "legacy_artifact": {
            "identifier": "legacy-cobol-app",
            "version": "1.0",
            "sha256_hash": "abc123...",
            "s3_location": "s3://bucket/key",
            "creation_timestamp": "2024-01-01T00:00:00Z"
        },
        "modern_implementation": {
            "identifier": "modern-lambda-app",
            "version": "1.0",
            "sha256_hash": "def456...",
            "s3_location": "s3://bucket/key",
            "creation_timestamp": "2024-01-02T00:00:00Z"
        },
        "coverage_report": {
            "branch_coverage_percent": 95.5,
            "entry_points_covered": 10,
            "total_entry_points": 10,
            "uncovered_branches": []
        }
    }
    
    Returns:
        {
            "statusCode": 200,
            "report_id": "compliance-workflow-123-20240101120000",
            "s3_location": "s3://bucket/compliance-reports/...",
            "compliance_status": "COMPLIANT"
        }
    """
    try:
        logger.info("Compliance report generation started", extra={"event": event})
        
        # Extract parameters from event
        workflow_id = event['workflow_id']
        
        # Parse artifact metadata
        legacy_artifact = ArtifactMetadata.from_dict(event['legacy_artifact'])
        modern_implementation = ArtifactMetadata.from_dict(event['modern_implementation'])
        coverage_report = CoverageReport.from_dict(event['coverage_report'])
        
        # Generate compliance report
        compliance_report = generate_compliance_report(
            workflow_id=workflow_id,
            legacy_artifact=legacy_artifact,
            modern_implementation=modern_implementation,
            coverage_report=coverage_report
        )
        
        # Sign compliance report
        signature = sign_compliance_report(compliance_report)
        
        # Store compliance report
        s3_key = store_compliance_report(compliance_report, signature)
        
        logger.info(
            "Compliance report generation completed",
            extra={
                "report_id": compliance_report.report_id,
                "compliance_status": compliance_report.compliance_status,
                "s3_location": f"s3://{COMPLIANCE_REPORTS_BUCKET}/{s3_key}"
            }
        )
        
        return {
            'statusCode': 200,
            'report_id': compliance_report.report_id,
            's3_location': f"s3://{COMPLIANCE_REPORTS_BUCKET}/{s3_key}",
            'compliance_status': compliance_report.compliance_status,
            'total_test_vectors': compliance_report.total_test_vectors,
            'passed_tests': compliance_report.passed_tests,
            'failed_tests': compliance_report.failed_tests,
        }
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e)
        }
