"""
Unit tests for cryptographic validation script.
"""

import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
from scripts.crypto_validation import CryptoValidator, CryptoTestResult


class TestCryptoValidator:
    """Tests for CryptoValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a CryptoValidator instance with mocked clients."""
        with patch('scripts.crypto_validation.boto3'):
            validator = CryptoValidator(stack_name="TestStack")
            return validator
    
    def test_validate_kms_key_spec_symmetric(self, validator):
        """Test validation of symmetric KMS key (AES-256)."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-1',
                'KeySpec': 'SYMMETRIC_DEFAULT',
                'KeyUsage': 'ENCRYPT_DECRYPT'
            }
        })
        
        result = validator.validate_kms_key_spec('test-key-1')
        
        assert result.passed is True
        assert result.test_name == "KMS Symmetric Key Algorithm"
        assert 'AES-256' in result.details
    
    def test_validate_kms_key_spec_asymmetric(self, validator):
        """Test validation of asymmetric KMS key (RSA-4096)."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-2',
                'KeySpec': 'RSA_4096',
                'KeyUsage': 'SIGN_VERIFY'
            }
        })
        
        result = validator.validate_kms_key_spec('test-key-2')
        
        assert result.passed is True
        assert result.test_name == "KMS Asymmetric Key Algorithm"
        assert 'RSA-4096' in result.details
    
    def test_validate_kms_key_spec_wrong_symmetric(self, validator):
        """Test validation fails for wrong symmetric key spec."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-3',
                'KeySpec': 'AES_128',
                'KeyUsage': 'ENCRYPT_DECRYPT'
            }
        })
        
        result = validator.validate_kms_key_spec('test-key-3')
        
        assert result.passed is False
        assert 'AES_128' in result.details
    
    def test_validate_kms_key_spec_wrong_asymmetric(self, validator):
        """Test validation fails for wrong asymmetric key spec."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-4',
                'KeySpec': 'RSA_2048',
                'KeyUsage': 'SIGN_VERIFY'
            }
        })
        
        result = validator.validate_kms_key_spec('test-key-4')
        
        assert result.passed is False
        assert 'RSA_2048' in result.details
    
    def test_validate_signing_algorithm_success(self, validator):
        """Test validation of signing algorithm."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-5',
                'KeyUsage': 'SIGN_VERIFY'
            }
        })
        validator.kms_client.sign = Mock(return_value={
            'Signature': b'test-signature',
            'SigningAlgorithm': 'RSASSA_PSS_SHA_256'
        })
        
        result = validator.validate_signing_algorithm('test-key-5')
        
        assert result.passed is True
        assert result.test_name == "Signing Algorithm"
        assert 'RSASSA-PSS-SHA-256' in result.details
    
    def test_validate_signing_algorithm_not_signing_key(self, validator):
        """Test signing algorithm validation skips non-signing keys."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-6',
                'KeyUsage': 'ENCRYPT_DECRYPT'
            }
        })
        
        result = validator.validate_signing_algorithm('test-key-6')
        
        assert result.passed is True
        assert 'not a signing key' in result.details
    
    def test_test_signature_verification_success(self, validator):
        """Test signature verification workflow."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-7',
                'KeyUsage': 'SIGN_VERIFY'
            }
        })
        validator.kms_client.sign = Mock(return_value={
            'Signature': b'test-signature',
            'SigningAlgorithm': 'RSASSA_PSS_SHA_256'
        })
        validator.kms_client.verify = Mock(return_value={
            'SignatureValid': True
        })
        
        result = validator.test_signature_verification('test-key-7')
        
        assert result.passed is True
        assert result.test_name == "Signature Verification"
        assert 'successful' in result.details
    
    def test_test_signature_verification_failure(self, validator):
        """Test signature verification when signature is invalid."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-8',
                'KeyUsage': 'SIGN_VERIFY'
            }
        })
        validator.kms_client.sign = Mock(return_value={
            'Signature': b'test-signature',
            'SigningAlgorithm': 'RSASSA_PSS_SHA_256'
        })
        validator.kms_client.verify = Mock(return_value={
            'SignatureValid': False
        })
        
        result = validator.test_signature_verification('test-key-8')
        
        assert result.passed is False
        assert 'failed' in result.details
    
    def test_test_signature_verification_not_signing_key(self, validator):
        """Test signature verification skips non-signing keys."""
        validator.kms_client.describe_key = Mock(return_value={
            'KeyMetadata': {
                'KeyId': 'test-key-9',
                'KeyUsage': 'ENCRYPT_DECRYPT'
            }
        })
        
        result = validator.test_signature_verification('test-key-9')
        
        assert result.passed is True
        assert 'not a signing key' in result.details
    
    def test_sha256_hashing(self, validator):
        """Test SHA-256 hashing implementation."""
        result = validator.test_sha256_hashing()
        
        assert result.passed is True
        assert result.test_name == "SHA-256 Hashing"
        assert 'works correctly' in result.details
    
    def test_hash_consistency(self, validator):
        """Test SHA-256 hash consistency."""
        result = validator.test_hash_consistency()
        
        assert result.passed is True
        assert result.test_name == "Hash Consistency"
        assert 'consistent' in result.details
    
    def test_get_stack_kms_keys(self, validator):
        """Test retrieving KMS keys from CloudFormation stack."""
        validator.cloudformation_client.get_paginator = Mock(return_value=MagicMock())
        paginator = validator.cloudformation_client.get_paginator.return_value
        paginator.paginate.return_value = [{
            'StackResourceSummaries': [
                {'ResourceType': 'AWS::KMS::Key', 'PhysicalResourceId': 'key-1'},
                {'ResourceType': 'AWS::KMS::Key', 'PhysicalResourceId': 'key-2'},
                {'ResourceType': 'AWS::S3::Bucket', 'PhysicalResourceId': 'bucket-1'}
            ]
        }]
        
        keys = validator.get_stack_kms_keys()
        
        assert len(keys) == 2
        assert 'key-1' in keys
        assert 'key-2' in keys
        assert 'bucket-1' not in keys
    
    def test_sha256_produces_correct_length(self):
        """Test that SHA-256 produces 64 hex characters."""
        test_data = b"Test data"
        hash_value = hashlib.sha256(test_data).hexdigest()
        
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)
    
    def test_sha256_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        hash1 = hashlib.sha256(b"data1").hexdigest()
        hash2 = hashlib.sha256(b"data2").hexdigest()
        
        assert hash1 != hash2
