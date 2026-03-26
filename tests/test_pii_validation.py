"""
Unit tests for PII validation script.
"""

import pytest
from unittest.mock import Mock, patch
from scripts.pii_validation import PIIValidator, PIITestResult


class TestPIIValidator:
    """Tests for PIIValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a PIIValidator instance with mocked clients."""
        with patch('scripts.pii_validation.boto3'):
            validator = PIIValidator(stack_name="TestStack")
            return validator
    
    def test_create_sample_data_with_pii(self, validator):
        """Test creation of sample data with PII."""
        sample_data = validator.create_sample_data_with_pii()
        
        assert 'cobol_with_ssn' in sample_data
        assert 'cobol_with_email' in sample_data
        assert 'cobol_with_phone' in sample_data
        assert 'cobol_with_credit_card' in sample_data
        
        # Verify PII is present in samples
        assert '123-45-6789' in sample_data['cobol_with_ssn']
        assert 'john.doe@example.com' in sample_data['cobol_with_email']
        assert '555-123-4567' in sample_data['cobol_with_phone']
        assert '4532-1234-5678-9010' in sample_data['cobol_with_credit_card']
    
    def test_detect_pii_patterns_ssn(self, validator):
        """Test detection of SSN pattern."""
        text = "Employee SSN: 123-45-6789"
        detected = validator.detect_pii_patterns(text)
        
        assert 'ssn' in detected
        assert '123-45-6789' in detected['ssn']
    
    def test_detect_pii_patterns_email(self, validator):
        """Test detection of email pattern."""
        text = "Contact: john.doe@example.com"
        detected = validator.detect_pii_patterns(text)
        
        assert 'email' in detected
        assert 'john.doe@example.com' in detected['email']
    
    def test_detect_pii_patterns_phone(self, validator):
        """Test detection of phone number pattern."""
        text = "Phone: 555-123-4567"
        detected = validator.detect_pii_patterns(text)
        
        assert 'phone' in detected
        assert '555-123-4567' in detected['phone']
    
    def test_detect_pii_patterns_credit_card(self, validator):
        """Test detection of credit card pattern."""
        text = "Card: 4532-1234-5678-9010"
        detected = validator.detect_pii_patterns(text)
        
        assert 'credit_card' in detected
        assert '4532-1234-5678-9010' in detected['credit_card']
    
    def test_detect_pii_patterns_name(self, validator):
        """Test detection of name pattern."""
        text = "Employee: John Smith"
        detected = validator.detect_pii_patterns(text)
        
        assert 'name' in detected
        assert 'John Smith' in detected['name']
    
    def test_detect_pii_patterns_no_pii(self, validator):
        """Test detection when no PII is present."""
        text = "This is a clean text without any PII"
        detected = validator.detect_pii_patterns(text)
        
        assert len(detected) == 0
    
    def test_pii_detection(self, validator):
        """Test PII detection test."""
        result = validator.test_pii_detection()
        
        assert result.test_name == "PII Detection"
        assert result.passed is True
        assert len(result.pii_found) > 0
        assert any('ssn' in pii.lower() for pii in result.pii_found)
    
    def test_pii_redaction(self, validator):
        """Test PII redaction test."""
        result = validator.test_pii_redaction()
        
        assert result.test_name == "PII Redaction"
        assert result.passed is True
        assert 'Successfully redacted' in result.details
    
    def test_synthetic_data_replacement(self, validator):
        """Test synthetic data replacement test."""
        result = validator.test_synthetic_data_replacement()
        
        assert result.test_name == "Synthetic Data Replacement"
        assert result.passed is True
        assert 'Successfully replaced' in result.details
    
    def test_pii_logging_log_group_not_found(self, validator):
        """Test PII logging when log group doesn't exist."""
        validator.logs_client.describe_log_groups = Mock(
            side_effect=Exception("Log group not found")
        )
        
        result = validator.test_pii_logging()
        
        assert result.test_name == "PII Logging"
        assert result.passed is False
        assert 'not found' in result.details
    
    def test_pii_logging_success(self, validator):
        """Test PII logging when log group exists."""
        validator.logs_client.describe_log_groups = Mock(return_value={
            'logGroups': [{
                'logGroupName': '/aws/lambda/TestStack-ingestion-engine'
            }]
        })
        
        result = validator.test_pii_logging()
        
        assert result.test_name == "PII Logging"
        assert result.passed is True
    
    def test_macie_integration_enabled(self, validator):
        """Test Macie integration when Macie is enabled."""
        validator.macie_client.get_macie_session = Mock(return_value={
            'status': 'ENABLED'
        })
        
        result = validator.test_macie_integration()
        
        assert result.test_name == "Macie Integration"
        assert result.passed is True
        assert 'enabled' in result.details.lower()
    
    def test_macie_integration_disabled(self, validator):
        """Test Macie integration when Macie is disabled."""
        validator.macie_client.get_macie_session = Mock(return_value={
            'status': 'PAUSED'
        })
        
        result = validator.test_macie_integration()
        
        assert result.test_name == "Macie Integration"
        assert result.passed is False
        assert 'PAUSED' in result.details
    
    def test_macie_integration_access_denied(self, validator):
        """Test Macie integration when access is denied."""
        from botocore.exceptions import ClientError
        
        validator.macie_client.exceptions.AccessDeniedException = type('AccessDeniedException', (ClientError,), {})
        validator.macie_client.get_macie_session = Mock(
            side_effect=validator.macie_client.exceptions.AccessDeniedException(
                {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
                'GetMacieSession'
            )
        )
        
        result = validator.test_macie_integration()
        
        assert result.test_name == "Macie Integration"
        assert result.passed is False
        assert 'Access denied' in result.details or 'Error' in result.details
