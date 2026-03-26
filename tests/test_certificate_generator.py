"""
Unit tests for Certificate Generator Lambda.

Tests certificate generation, KMS signing, S3 storage, and event publishing.

Requirements: 17.1-17.9
"""

import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import pytest

from rosetta_zero.lambdas.certificate_generator.certificate_generation import (
    generate_certificate,
    _query_all_test_results,
    _compute_test_results_hash,
    _collect_individual_hashes,
    _get_execution_date_range
)
from rosetta_zero.lambdas.certificate_generator.certificate_signing import (
    sign_certificate,
    verify_certificate_signature
)
from rosetta_zero.lambdas.certificate_generator.event_publisher import (
    publish_completion_event
)
from rosetta_zero.lambdas.certificate_generator.error_handler import (
    handle_certificate_error,
    _classify_error
)
from rosetta_zero.models import (
    EquivalenceCertificate,
    SignedCertificate,
    ArtifactMetadata,
    CoverageReport
)


class TestCertificateGeneration:
    """Test certificate generation logic."""
    
    def test_generate_certificate_success(self):
        """Test successful certificate generation from test results."""
        # Mock DynamoDB client
        dynamodb_client = Mock()
        dynamodb_client.scan.return_value = {
            'Items': [
                {
                    'test_id': {'S': 'test-1'},
                    'execution_timestamp': {'S': '2024-01-01T00:00:00Z'},
                    'status': {'S': 'PASS'},
                    'comparison_result_hash': {'S': 'hash1'}
                },
                {
                    'test_id': {'S': 'test-2'},
                    'execution_timestamp': {'S': '2024-01-01T00:01:00Z'},
                    'status': {'S': 'PASS'},
                    'comparison_result_hash': {'S': 'hash2'}
                }
            ]
        }
        
        # Mock S3 client
        s3_client = Mock()
        
        # Test data
        legacy_artifact = {
            'identifier': 'legacy-v1',
            'version': '1.0.0',
            'sha256_hash': 'abc123',
            's3_location': 's3://bucket/legacy',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        modern_implementation = {
            'identifier': 'modern-v1',
            'version': '1.0.0',
            'sha256_hash': 'def456',
            's3_location': 's3://bucket/modern',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        coverage_report = {
            'branch_coverage_percent': 95.5,
            'entry_points_covered': 10,
            'total_entry_points': 10,
            'uncovered_branches': []
        }
        
        # Generate certificate
        certificate = generate_certificate(
            dynamodb_client=dynamodb_client,
            s3_client=s3_client,
            test_results_table='test-results',
            legacy_artifact=legacy_artifact,
            modern_implementation=modern_implementation,
            random_seed=12345,
            coverage_report=coverage_report
        )
        
        # Assertions
        assert certificate.certificate_id is not None
        assert certificate.total_test_vectors == 2
        assert certificate.legacy_artifact.identifier == 'legacy-v1'
        assert certificate.modern_implementation.identifier == 'modern-v1'
        assert certificate.random_seed == 12345
        assert certificate.coverage_report.branch_coverage_percent == 95.5
        assert len(certificate.individual_test_hashes) == 2
        assert certificate.test_results_hash is not None
    
    def test_generate_certificate_with_failed_tests(self):
        """Test certificate generation fails when tests failed."""
        # Mock DynamoDB client with failed test
        dynamodb_client = Mock()
        dynamodb_client.scan.return_value = {
            'Items': [
                {
                    'test_id': {'S': 'test-1'},
                    'execution_timestamp': {'S': '2024-01-01T00:00:00Z'},
                    'status': {'S': 'PASS'},
                    'comparison_result_hash': {'S': 'hash1'}
                },
                {
                    'test_id': {'S': 'test-2'},
                    'execution_timestamp': {'S': '2024-01-01T00:01:00Z'},
                    'status': {'S': 'FAIL'},
                    'comparison_result_hash': {'S': 'hash2'}
                }
            ]
        }
        
        s3_client = Mock()
        
        legacy_artifact = {
            'identifier': 'legacy-v1',
            'version': '1.0.0',
            'sha256_hash': 'abc123',
            's3_location': 's3://bucket/legacy',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        modern_implementation = {
            'identifier': 'modern-v1',
            'version': '1.0.0',
            'sha256_hash': 'def456',
            's3_location': 's3://bucket/modern',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        coverage_report = {
            'branch_coverage_percent': 95.5,
            'entry_points_covered': 10,
            'total_entry_points': 10,
            'uncovered_branches': []
        }
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="tests failed"):
            generate_certificate(
                dynamodb_client=dynamodb_client,
                s3_client=s3_client,
                test_results_table='test-results',
                legacy_artifact=legacy_artifact,
                modern_implementation=modern_implementation,
                random_seed=12345,
                coverage_report=coverage_report
            )
    
    def test_generate_certificate_with_no_tests(self):
        """Test certificate generation fails when no tests found."""
        # Mock DynamoDB client with no results
        dynamodb_client = Mock()
        dynamodb_client.scan.return_value = {'Items': []}
        
        s3_client = Mock()
        
        legacy_artifact = {
            'identifier': 'legacy-v1',
            'version': '1.0.0',
            'sha256_hash': 'abc123',
            's3_location': 's3://bucket/legacy',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        modern_implementation = {
            'identifier': 'modern-v1',
            'version': '1.0.0',
            'sha256_hash': 'def456',
            's3_location': 's3://bucket/modern',
            'creation_timestamp': '2024-01-01T00:00:00Z'
        }
        
        coverage_report = {
            'branch_coverage_percent': 95.5,
            'entry_points_covered': 10,
            'total_entry_points': 10,
            'uncovered_branches': []
        }
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="No test results found"):
            generate_certificate(
                dynamodb_client=dynamodb_client,
                s3_client=s3_client,
                test_results_table='test-results',
                legacy_artifact=legacy_artifact,
                modern_implementation=modern_implementation,
                random_seed=12345,
                coverage_report=coverage_report
            )
    
    def test_compute_test_results_hash(self):
        """Test SHA-256 hash computation of test results."""
        test_results = [
            {
                'test_id': {'S': 'test-2'},
                'status': {'S': 'PASS'}
            },
            {
                'test_id': {'S': 'test-1'},
                'status': {'S': 'PASS'}
            }
        ]
        
        hash1 = _compute_test_results_hash(test_results)
        
        # Hash should be deterministic (sorted)
        hash2 = _compute_test_results_hash(test_results)
        assert hash1 == hash2
        
        # Hash should be 64 hex characters (SHA-256)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1)
    
    def test_collect_individual_hashes(self):
        """Test collection of individual test result hashes."""
        test_results = [
            {
                'test_id': {'S': 'test-1'},
                'comparison_result_hash': {'S': 'hash1'}
            },
            {
                'test_id': {'S': 'test-2'},
                'comparison_result_hash': {'S': 'hash2'}
            }
        ]
        
        hashes = _collect_individual_hashes(test_results)
        
        # Should be sorted
        assert hashes == ['hash1', 'hash2']
    
    def test_get_execution_date_range(self):
        """Test extraction of execution date range."""
        test_results = [
            {
                'execution_timestamp': {'S': '2024-01-01T00:00:00Z'}
            },
            {
                'execution_timestamp': {'S': '2024-01-01T12:00:00Z'}
            },
            {
                'execution_timestamp': {'S': '2024-01-01T06:00:00Z'}
            }
        ]
        
        start, end = _get_execution_date_range(test_results)
        
        assert start == '2024-01-01T00:00:00Z'
        assert end == '2024-01-01T12:00:00Z'


class TestCertificateSigning:
    """Test cryptographic certificate signing."""
    
    def test_sign_certificate_success(self):
        """Test successful certificate signing with KMS."""
        # Create test certificate
        certificate = EquivalenceCertificate(
            certificate_id='test-cert-123',
            generation_timestamp='2024-01-01T00:00:00Z',
            legacy_artifact=ArtifactMetadata(
                identifier='legacy-v1',
                version='1.0.0',
                sha256_hash='abc123',
                s3_location='s3://bucket/legacy',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            modern_implementation=ArtifactMetadata(
                identifier='modern-v1',
                version='1.0.0',
                sha256_hash='def456',
                s3_location='s3://bucket/modern',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            total_test_vectors=1000,
            test_execution_start='2024-01-01T00:00:00Z',
            test_execution_end='2024-01-01T01:00:00Z',
            test_results_hash='test_hash',
            individual_test_hashes=['hash1', 'hash2'],
            random_seed=12345,
            coverage_report=CoverageReport(
                branch_coverage_percent=95.5,
                entry_points_covered=10,
                total_entry_points=10,
                uncovered_branches=[]
            )
        )
        
        # Mock KMS client
        kms_client = Mock()
        kms_client.sign.return_value = {
            'Signature': b'mock_signature_bytes'
        }
        
        # Sign certificate
        signed_cert = sign_certificate(
            certificate=certificate,
            kms_client=kms_client,
            kms_key_id='arn:aws:kms:us-east-1:123456789012:key/test-key'
        )
        
        # Assertions
        assert signed_cert.certificate == certificate
        assert signed_cert.signature == b'mock_signature_bytes'
        assert signed_cert.signing_key_id == 'arn:aws:kms:us-east-1:123456789012:key/test-key'
        assert signed_cert.signature_algorithm == 'RSASSA_PSS_SHA_256'
        assert signed_cert.signing_timestamp is not None
        
        # Verify KMS sign was called correctly
        kms_client.sign.assert_called_once()
        call_args = kms_client.sign.call_args[1]
        assert call_args['KeyId'] == 'arn:aws:kms:us-east-1:123456789012:key/test-key'
        assert call_args['MessageType'] == 'DIGEST'
        assert call_args['SigningAlgorithm'] == 'RSASSA_PSS_SHA_256'
        assert len(call_args['Message']) == 32  # SHA-256 hash is 32 bytes
    
    def test_verify_certificate_signature_valid(self):
        """Test certificate signature verification with valid signature."""
        # Create test certificate
        certificate = EquivalenceCertificate(
            certificate_id='test-cert-123',
            generation_timestamp='2024-01-01T00:00:00Z',
            legacy_artifact=ArtifactMetadata(
                identifier='legacy-v1',
                version='1.0.0',
                sha256_hash='abc123',
                s3_location='s3://bucket/legacy',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            modern_implementation=ArtifactMetadata(
                identifier='modern-v1',
                version='1.0.0',
                sha256_hash='def456',
                s3_location='s3://bucket/modern',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            total_test_vectors=1000,
            test_execution_start='2024-01-01T00:00:00Z',
            test_execution_end='2024-01-01T01:00:00Z',
            test_results_hash='test_hash',
            individual_test_hashes=['hash1', 'hash2'],
            random_seed=12345,
            coverage_report=CoverageReport(
                branch_coverage_percent=95.5,
                entry_points_covered=10,
                total_entry_points=10,
                uncovered_branches=[]
            )
        )
        
        signed_cert = SignedCertificate(
            certificate=certificate,
            signature=b'mock_signature',
            signing_key_id='arn:aws:kms:us-east-1:123456789012:key/test-key',
            signature_algorithm='RSASSA_PSS_SHA_256',
            signing_timestamp='2024-01-01T00:00:00Z'
        )
        
        # Mock KMS client
        kms_client = Mock()
        kms_client.verify.return_value = {
            'SignatureValid': True
        }
        
        # Verify signature
        is_valid = verify_certificate_signature(signed_cert, kms_client)
        
        assert is_valid is True
        kms_client.verify.assert_called_once()
    
    def test_verify_certificate_signature_invalid(self):
        """Test certificate signature verification with invalid signature."""
        certificate = EquivalenceCertificate(
            certificate_id='test-cert-123',
            generation_timestamp='2024-01-01T00:00:00Z',
            legacy_artifact=ArtifactMetadata(
                identifier='legacy-v1',
                version='1.0.0',
                sha256_hash='abc123',
                s3_location='s3://bucket/legacy',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            modern_implementation=ArtifactMetadata(
                identifier='modern-v1',
                version='1.0.0',
                sha256_hash='def456',
                s3_location='s3://bucket/modern',
                creation_timestamp='2024-01-01T00:00:00Z'
            ),
            total_test_vectors=1000,
            test_execution_start='2024-01-01T00:00:00Z',
            test_execution_end='2024-01-01T01:00:00Z',
            test_results_hash='test_hash',
            individual_test_hashes=['hash1', 'hash2'],
            random_seed=12345,
            coverage_report=CoverageReport(
                branch_coverage_percent=95.5,
                entry_points_covered=10,
                total_entry_points=10,
                uncovered_branches=[]
            )
        )
        
        signed_cert = SignedCertificate(
            certificate=certificate,
            signature=b'invalid_signature',
            signing_key_id='arn:aws:kms:us-east-1:123456789012:key/test-key',
            signature_algorithm='RSASSA_PSS_SHA_256',
            signing_timestamp='2024-01-01T00:00:00Z'
        )
        
        # Mock KMS client
        kms_client = Mock()
        kms_client.verify.return_value = {
            'SignatureValid': False
        }
        
        # Verify signature
        is_valid = verify_certificate_signature(signed_cert, kms_client)
        
        assert is_valid is False


class TestEventPublisher:
    """Test event publishing to EventBridge and SNS."""
    
    def test_publish_completion_event_success(self):
        """Test successful event publishing."""
        # Mock clients
        eventbridge_client = Mock()
        eventbridge_client.put_events.return_value = {
            'Entries': [{'EventId': 'event-123'}]
        }
        
        sns_client = Mock()
        sns_client.publish.return_value = {
            'MessageId': 'msg-123'
        }
        
        # Publish event
        publish_completion_event(
            eventbridge_client=eventbridge_client,
            sns_client=sns_client,
            event_bus_name='default',
            sns_topic_arn='arn:aws:sns:us-east-1:123456789012:topic',
            certificate_id='cert-123',
            s3_location='s3://bucket/cert',
            workflow_id='workflow-123'
        )
        
        # Verify EventBridge call
        eventbridge_client.put_events.assert_called_once()
        call_args = eventbridge_client.put_events.call_args[1]
        assert len(call_args['Entries']) == 1
        entry = call_args['Entries'][0]
        assert entry['Source'] == 'rosetta-zero.certificate-generator'
        assert entry['DetailType'] == 'Certificate Generation Completed'
        
        # Verify SNS call
        sns_client.publish.assert_called_once()
        sns_call_args = sns_client.publish.call_args[1]
        assert sns_call_args['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:topic'
        assert 'cert-123' in sns_call_args['Message']


class TestErrorHandler:
    """Test error handling and classification."""
    
    def test_classify_aws_500_error(self):
        """Test classification of AWS 500-level errors."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            {
                'Error': {'Code': 'InternalServerError'},
                'ResponseMetadata': {'HTTPStatusCode': 500}
            },
            'operation'
        )
        
        classification = _classify_error(error)
        assert classification == 'aws_500_error'
    
    def test_classify_kms_failure(self):
        """Test classification of KMS failures."""
        from botocore.exceptions import ClientError
        
        error = ClientError(
            {
                'Error': {'Code': 'KMSInvalidStateException'},
                'ResponseMetadata': {'HTTPStatusCode': 400, 'ServiceId': 'KMS'}
            },
            'operation'
        )
        
        classification = _classify_error(error)
        assert classification == 'kms_failure'
    
    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        error = ValueError("Tests failed")
        
        classification = _classify_error(error)
        assert classification == 'validation_error'
    
    def test_handle_certificate_error_with_sns(self):
        """Test error handling with SNS notification."""
        error = ValueError("Test error")
        
        sns_client = Mock()
        sns_client.publish.return_value = {'MessageId': 'msg-123'}
        
        handle_certificate_error(
            error=error,
            sns_client=sns_client,
            sns_topic_arn='arn:aws:sns:us-east-1:123456789012:topic',
            workflow_id='workflow-123',
            context={'test': 'context'}
        )
        
        # Should have sent SNS notification
        sns_client.publish.assert_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
