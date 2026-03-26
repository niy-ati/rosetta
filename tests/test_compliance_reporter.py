"""Unit tests for Compliance Reporter Lambda function."""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from rosetta_zero.models.comparison import (
    ComplianceReport,
    SignedCertificate,
    EquivalenceCertificate,
    DiscrepancyReport,
    ComparisonResult,
    ArtifactMetadata,
    CoverageReport,
)


@pytest.fixture
def sample_artifact_metadata():
    """Sample artifact metadata for testing."""
    return ArtifactMetadata(
        identifier="test-artifact",
        version="1.0",
        sha256_hash="abc123def456",
        s3_location="s3://bucket/key",
        creation_timestamp=datetime.utcnow().isoformat()
    )


@pytest.fixture
def sample_coverage_report():
    """Sample coverage report for testing."""
    return CoverageReport(
        branch_coverage_percent=95.5,
        entry_points_covered=10,
        total_entry_points=10,
        uncovered_branches=[]
    )


@pytest.fixture
def sample_equivalence_certificate(sample_artifact_metadata, sample_coverage_report):
    """Sample equivalence certificate for testing."""
    return EquivalenceCertificate(
        certificate_id="cert-123",
        generation_timestamp=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        total_test_vectors=1000,
        test_execution_start=datetime.utcnow().isoformat(),
        test_execution_end=datetime.utcnow().isoformat(),
        test_results_hash="test-hash-123",
        individual_test_hashes=["hash1", "hash2"],
        random_seed=42,
        coverage_report=sample_coverage_report
    )


@pytest.fixture
def sample_signed_certificate(sample_equivalence_certificate):
    """Sample signed certificate for testing."""
    return SignedCertificate(
        certificate=sample_equivalence_certificate,
        signature=b"signature-bytes",
        signing_key_id="key-123",
        signature_algorithm="RSASSA_PSS_SHA_256",
        signing_timestamp=datetime.utcnow().isoformat()
    )


def test_compliance_report_creation(sample_artifact_metadata, sample_coverage_report, sample_signed_certificate):
    """Test creating a compliance report."""
    report = ComplianceReport(
        report_id="report-123",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-123",
        total_test_vectors=1000,
        passed_tests=1000,
        failed_tests=0,
        test_results_hash="test-hash-123",
        equivalence_certificate=sample_signed_certificate,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-ingestion-engine"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="COMPLIANT",
        compliance_notes=None
    )
    
    assert report.report_id == "report-123"
    assert report.compliance_status == "COMPLIANT"
    assert report.passed_tests == 1000
    assert report.failed_tests == 0
    assert len(report.discrepancy_reports) == 0


def test_compliance_report_serialization(sample_artifact_metadata, sample_coverage_report, sample_signed_certificate):
    """Test compliance report JSON serialization."""
    report = ComplianceReport(
        report_id="report-123",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-123",
        total_test_vectors=1000,
        passed_tests=1000,
        failed_tests=0,
        test_results_hash="test-hash-123",
        equivalence_certificate=sample_signed_certificate,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-ingestion-engine"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="COMPLIANT",
        compliance_notes=None
    )
    
    # Serialize to JSON
    report_json = report.to_json()
    assert isinstance(report_json, str)
    
    # Deserialize from JSON
    report_restored = ComplianceReport.from_json(report_json)
    assert report_restored.report_id == report.report_id
    assert report_restored.compliance_status == report.compliance_status
    assert report_restored.total_test_vectors == report.total_test_vectors


def test_compliance_report_html_generation(sample_artifact_metadata, sample_coverage_report, sample_signed_certificate):
    """Test compliance report HTML generation."""
    report = ComplianceReport(
        report_id="report-123",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-123",
        total_test_vectors=1000,
        passed_tests=1000,
        failed_tests=0,
        test_results_hash="test-hash-123",
        equivalence_certificate=sample_signed_certificate,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-ingestion-engine"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="COMPLIANT",
        compliance_notes=None
    )
    
    # Generate HTML report
    html = report.generate_html_report()
    
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "Rosetta Zero Compliance Report" in html
    assert "report-123" in html
    assert "COMPLIANT" in html
    assert "1,000" in html  # Formatted number


def test_compliance_report_non_compliant(sample_artifact_metadata, sample_coverage_report):
    """Test compliance report with failed tests."""
    report = ComplianceReport(
        report_id="report-456",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-456",
        total_test_vectors=1000,
        passed_tests=995,
        failed_tests=5,
        test_results_hash="test-hash-456",
        equivalence_certificate=None,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-ingestion-engine"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="NON_COMPLIANT",
        compliance_notes="Behavioral discrepancies detected in 5 test vectors."
    )
    
    assert report.compliance_status == "NON_COMPLIANT"
    assert report.failed_tests == 5
    assert report.equivalence_certificate is None
    assert "discrepancies" in report.compliance_notes.lower()


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_compliance_reporter_handler(mock_get_clients, 
                                     sample_artifact_metadata, sample_coverage_report):
    """Test compliance reporter Lambda handler."""
    from rosetta_zero.lambdas.compliance_reporter.handler import handler
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock DynamoDB table
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        'Items': [
            {
                'test_id': 'test-1',
                'status': 'PASS',
                'execution_timestamp': datetime.utcnow().isoformat(),
                'comparison_result_hash': 'hash1'
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    # Mock S3 list_objects_v2 for certificates
    mock_s3.list_objects_v2.return_value = {'Contents': []}
    
    # Mock CloudWatch Logs
    mock_logs.get_paginator.return_value.paginate.return_value = [
        {'logGroups': [{'logGroupName': '/aws/lambda/rosetta-zero-test'}]}
    ]
    
    # Mock KMS sign
    mock_kms.sign.return_value = {'Signature': b'test-signature'}
    
    # Create mock Lambda context
    mock_context = MagicMock()
    mock_context.function_name = 'test-function'
    mock_context.memory_limit_in_mb = 3008
    mock_context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
    mock_context.aws_request_id = 'test-request-id'
    
    # Create event
    event = {
        'workflow_id': 'workflow-123',
        'legacy_artifact': sample_artifact_metadata.to_dict(),
        'modern_implementation': sample_artifact_metadata.to_dict(),
        'coverage_report': sample_coverage_report.to_dict()
    }
    
    # Call handler
    response = handler(event, mock_context)
    
    # Verify response
    assert response['statusCode'] == 200
    assert 'report_id' in response
    assert 'compliance_status' in response
    assert 's3_location' in response


def test_compliance_report_with_discrepancies(sample_artifact_metadata, sample_coverage_report):
    """Test compliance report with discrepancy reports."""
    # Create a sample discrepancy report
    comparison_result = ComparisonResult(
        test_vector_id="test-1",
        comparison_timestamp=datetime.utcnow().isoformat(),
        match=False,
        return_value_match=False,
        stdout_match=True,
        stderr_match=True,
        side_effects_match=True,
        differences=None,
        result_hash="hash-123"
    )
    
    discrepancy = DiscrepancyReport(
        report_id="discrepancy-1",
        generation_timestamp=datetime.utcnow().isoformat(),
        test_vector_id="test-1",
        legacy_result_hash="legacy-hash",
        modern_result_hash="modern-hash",
        comparison_result=comparison_result,
        root_cause_analysis="Return value mismatch detected"
    )
    
    report = ComplianceReport(
        report_id="report-789",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-789",
        total_test_vectors=1000,
        passed_tests=999,
        failed_tests=1,
        test_results_hash="test-hash-789",
        equivalence_certificate=None,
        discrepancy_reports=[discrepancy],
        audit_log_groups=["/aws/lambda/rosetta-zero-ingestion-engine"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="NON_COMPLIANT",
        compliance_notes="Behavioral discrepancies detected in 1 test vector."
    )
    
    assert len(report.discrepancy_reports) == 1
    assert report.discrepancy_reports[0].report_id == "discrepancy-1"
    
    # Generate HTML and verify discrepancy is included
    html = report.generate_html_report()
    assert "discrepancy-1" in html
    assert "Total Discrepancies" in html


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_generate_compliance_report(mock_get_clients, sample_artifact_metadata, sample_coverage_report):
    """Test compliance report generation function."""
    from rosetta_zero.lambdas.compliance_reporter.handler import generate_compliance_report
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock DynamoDB table with test results
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        'Items': [
            {
                'test_id': 'test-1',
                'status': 'PASS',
                'execution_timestamp': '2024-01-01T10:00:00Z',
                'comparison_result_hash': 'hash1'
            },
            {
                'test_id': 'test-2',
                'status': 'PASS',
                'execution_timestamp': '2024-01-01T10:01:00Z',
                'comparison_result_hash': 'hash2'
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    # Mock S3 - no certificates or discrepancy reports
    mock_s3.list_objects_v2.return_value = {'Contents': []}
    
    # Mock CloudWatch Logs
    mock_logs.get_paginator.return_value.paginate.return_value = [
        {'logGroups': [
            {'logGroupName': '/aws/lambda/rosetta-zero-ingestion-engine'},
            {'logGroupName': '/aws/lambda/rosetta-zero-bedrock-architect'}
        ]}
    ]
    
    # Generate compliance report
    report = generate_compliance_report(
        workflow_id='workflow-123',
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report
    )
    
    # Verify report structure
    assert report.workflow_id == 'workflow-123'
    assert report.total_test_vectors == 2
    assert report.passed_tests == 2
    assert report.failed_tests == 0
    assert report.compliance_status == 'NON_COMPLIANT'  # No certificate
    assert 'No equivalence certificate' in report.compliance_notes
    assert len(report.audit_log_groups) == 2
    assert report.legacy_artifact == sample_artifact_metadata
    assert report.modern_implementation == sample_artifact_metadata


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_generate_compliance_report_with_failures(mock_get_clients, sample_artifact_metadata, sample_coverage_report):
    """Test compliance report generation with failed tests."""
    from rosetta_zero.lambdas.compliance_reporter.handler import generate_compliance_report
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock DynamoDB table with some failed tests
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        'Items': [
            {
                'test_id': 'test-1',
                'status': 'PASS',
                'execution_timestamp': '2024-01-01T10:00:00Z',
                'comparison_result_hash': 'hash1'
            },
            {
                'test_id': 'test-2',
                'status': 'FAIL',
                'execution_timestamp': '2024-01-01T10:01:00Z',
                'comparison_result_hash': 'hash2'
            },
            {
                'test_id': 'test-3',
                'status': 'FAIL',
                'execution_timestamp': '2024-01-01T10:02:00Z',
                'comparison_result_hash': 'hash3'
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    # Mock S3 - no certificates
    mock_s3.list_objects_v2.return_value = {'Contents': []}
    
    # Mock CloudWatch Logs
    mock_logs.get_paginator.return_value.paginate.return_value = [
        {'logGroups': [{'logGroupName': '/aws/lambda/rosetta-zero-test'}]}
    ]
    
    # Generate compliance report
    report = generate_compliance_report(
        workflow_id='workflow-456',
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report
    )
    
    # Verify report reflects failures
    assert report.total_test_vectors == 3
    assert report.passed_tests == 1
    assert report.failed_tests == 2
    assert report.compliance_status == 'NON_COMPLIANT'
    assert 'Behavioral discrepancies detected in 2 test vectors' in report.compliance_notes


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_sign_compliance_report(mock_get_clients, sample_artifact_metadata, sample_coverage_report):
    """Test compliance report signing with KMS."""
    from rosetta_zero.lambdas.compliance_reporter.handler import sign_compliance_report
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock KMS sign response
    mock_kms.sign.return_value = {
        'Signature': b'test-signature-bytes-12345'
    }
    
    # Create a compliance report
    report = ComplianceReport(
        report_id="report-123",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-123",
        total_test_vectors=1000,
        passed_tests=1000,
        failed_tests=0,
        test_results_hash="test-hash-123",
        equivalence_certificate=None,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-test"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="COMPLIANT",
        compliance_notes=None
    )
    
    # Sign the report
    signature = sign_compliance_report(report)
    
    # Verify KMS was called correctly
    assert mock_kms.sign.called
    call_args = mock_kms.sign.call_args
    assert call_args[1]['MessageType'] == 'DIGEST'
    assert call_args[1]['SigningAlgorithm'] == 'RSASSA_PSS_SHA_256'
    
    # Verify signature returned
    assert signature == b'test-signature-bytes-12345'


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_store_compliance_report(mock_get_clients, sample_artifact_metadata, sample_coverage_report):
    """Test compliance report storage in S3."""
    from rosetta_zero.lambdas.compliance_reporter.handler import store_compliance_report
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Create a compliance report
    report = ComplianceReport(
        report_id="report-789",
        generation_timestamp=datetime.utcnow().isoformat(),
        workflow_id="workflow-789",
        total_test_vectors=500,
        passed_tests=500,
        failed_tests=0,
        test_results_hash="test-hash-789",
        equivalence_certificate=None,
        discrepancy_reports=[],
        audit_log_groups=["/aws/lambda/rosetta-zero-test"],
        audit_log_query_start=datetime.utcnow().isoformat(),
        audit_log_query_end=datetime.utcnow().isoformat(),
        legacy_artifact=sample_artifact_metadata,
        modern_implementation=sample_artifact_metadata,
        coverage_report=sample_coverage_report,
        compliance_status="COMPLIANT",
        compliance_notes=None
    )
    
    signature = b'test-signature-bytes'
    
    # Store the report
    s3_key = store_compliance_report(report, signature)
    
    # Verify S3 put_object was called twice (JSON and HTML)
    assert mock_s3.put_object.call_count == 2
    
    # Verify JSON report was stored
    json_call = mock_s3.put_object.call_args_list[0]
    assert 'compliance-reports/workflow-789/report-789.json' in json_call[1]['Key']
    assert json_call[1]['ContentType'] == 'application/json'
    assert json_call[1]['ServerSideEncryption'] == 'aws:kms'
    
    # Verify HTML report was stored
    html_call = mock_s3.put_object.call_args_list[1]
    assert 'compliance-reports/workflow-789/report-789.html' in html_call[1]['Key']
    assert html_call[1]['ContentType'] == 'text/html'
    
    # Verify returned S3 key
    assert 'compliance-reports/workflow-789/report-789.json' in s3_key


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_get_all_test_results(mock_get_clients):
    """Test retrieving all test results from DynamoDB."""
    from rosetta_zero.lambdas.compliance_reporter.handler import get_all_test_results
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock DynamoDB table
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        'Items': [
            {
                'test_id': 'test-1',
                'status': 'PASS',
                'execution_timestamp': '2024-01-01T10:00:00Z',
                'comparison_result_hash': 'hash1'
            },
            {
                'test_id': 'test-2',
                'status': 'PASS',
                'execution_timestamp': '2024-01-01T10:01:00Z',
                'comparison_result_hash': 'hash2'
            },
            {
                'test_id': 'test-3',
                'status': 'FAIL',
                'execution_timestamp': '2024-01-01T10:02:00Z',
                'comparison_result_hash': 'hash3'
            }
        ]
    }
    mock_dynamodb.Table.return_value = mock_table
    
    # Get test results
    results = get_all_test_results('workflow-123')
    
    # Verify results
    assert results['total_tests'] == 3
    assert results['passed_tests'] == 2
    assert results['failed_tests'] == 1
    assert len(results['individual_test_hashes']) == 3
    assert 'test_results_hash' in results
    assert results['test_execution_start'] == '2024-01-01T10:00:00Z'
    assert results['test_execution_end'] == '2024-01-01T10:02:00Z'


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_get_equivalence_certificate(mock_get_clients, sample_signed_certificate):
    """Test retrieving equivalence certificate from S3."""
    from rosetta_zero.lambdas.compliance_reporter.handler import get_equivalence_certificate
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock S3 list_objects_v2
    mock_s3.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': 'certificates/cert-123/signed-certificate.json',
                'LastModified': datetime.utcnow()
            }
        ]
    }
    
    # Mock S3 get_object
    mock_s3.get_object.return_value = {
        'Body': MagicMock(read=lambda: sample_signed_certificate.to_json().encode('utf-8'))
    }
    
    # Get certificate
    certificate = get_equivalence_certificate('workflow-123')
    
    # Verify certificate retrieved
    assert certificate is not None
    assert certificate.certificate.certificate_id == sample_signed_certificate.certificate.certificate_id


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_get_equivalence_certificate_not_found(mock_get_clients):
    """Test retrieving equivalence certificate when none exists."""
    from rosetta_zero.lambdas.compliance_reporter.handler import get_equivalence_certificate
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock S3 list_objects_v2 - no certificates
    mock_s3.list_objects_v2.return_value = {}
    
    # Get certificate
    certificate = get_equivalence_certificate('workflow-123')
    
    # Verify None returned
    assert certificate is None


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_get_audit_log_references(mock_get_clients):
    """Test retrieving audit log references from CloudWatch."""
    from rosetta_zero.lambdas.compliance_reporter.handler import get_audit_log_references
    
    # Mock AWS clients
    mock_s3 = MagicMock()
    mock_dynamodb = MagicMock()
    mock_kms = MagicMock()
    mock_logs = MagicMock()
    
    mock_get_clients.return_value = (mock_s3, mock_dynamodb, mock_kms, mock_logs)
    
    # Mock CloudWatch Logs paginator
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            'logGroups': [
                {'logGroupName': '/aws/lambda/rosetta-zero-ingestion-engine'},
                {'logGroupName': '/aws/lambda/rosetta-zero-bedrock-architect'}
            ]
        },
        {
            'logGroups': [
                {'logGroupName': '/aws/lambda/rosetta-zero-hostile-auditor'}
            ]
        }
    ]
    mock_logs.get_paginator.return_value = mock_paginator
    
    # Get audit log references
    log_groups = get_audit_log_references('workflow-123', '2024-01-01T00:00:00Z', '2024-01-02T00:00:00Z')
    
    # Verify log groups retrieved
    assert len(log_groups) == 3
    assert '/aws/lambda/rosetta-zero-ingestion-engine' in log_groups
    assert '/aws/lambda/rosetta-zero-bedrock-architect' in log_groups
    assert '/aws/lambda/rosetta-zero-hostile-auditor' in log_groups


@patch('rosetta_zero.lambdas.compliance_reporter.handler.get_aws_clients')
def test_handler_error_handling(mock_get_clients):
    """Test Lambda handler error handling."""
    from rosetta_zero.lambdas.compliance_reporter.handler import handler
    
    # Mock AWS clients to raise an exception
    mock_get_clients.side_effect = Exception("AWS service error")
    
    # Create mock Lambda context
    mock_context = MagicMock()
    mock_context.function_name = 'test-function'
    mock_context.memory_limit_in_mb = 3008
    mock_context.invoked_function_arn = 'arn:aws:lambda:us-east-1:123456789012:function:test'
    mock_context.aws_request_id = 'test-request-id'
    
    # Create event with invalid data
    event = {
        'workflow_id': 'workflow-error'
    }
    
    # Call handler
    response = handler(event, mock_context)
    
    # Verify error response
    assert response['statusCode'] == 500
    assert 'error' in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
