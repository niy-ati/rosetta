"""
Unit tests for security validation script.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from scripts.security_validation import SecurityValidator, ValidationResult


class TestSecurityValidator:
    """Tests for SecurityValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a SecurityValidator instance with mocked clients."""
        with patch('scripts.security_validation.boto3'):
            validator = SecurityValidator(stack_name="TestStack")
            return validator
    
    def test_validate_s3_public_access_blocked_success(self, validator):
        """Test S3 public access validation when all access is blocked."""
        validator.s3_client.get_public_access_block = Mock(return_value={
            'PublicAccessBlockConfiguration': {
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        })
        
        result = validator.validate_s3_public_access_blocked('test-bucket')
        
        assert result.passed is True
        assert result.check_name == "S3 Public Access Blocked"
        assert 'test-bucket' in result.details
    
    def test_validate_s3_public_access_blocked_failure(self, validator):
        """Test S3 public access validation when access is not fully blocked."""
        validator.s3_client.get_public_access_block = Mock(return_value={
            'PublicAccessBlockConfiguration': {
                'BlockPublicAcls': True,
                'IgnorePublicAcls': False,  # Not blocked
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        })
        
        result = validator.validate_s3_public_access_blocked('test-bucket')
        
        assert result.passed is False
        assert result.check_name == "S3 Public Access Blocked"
    
    def test_validate_s3_encryption_success(self, validator):
        """Test S3 encryption validation when KMS is used."""
        validator.s3_client.get_bucket_encryption = Mock(return_value={
            'ServerSideEncryptionConfiguration': {
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'aws:kms',
                        'KMSMasterKeyID': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012'
                    }
                }]
            }
        })
        
        result = validator.validate_s3_encryption('test-bucket')
        
        assert result.passed is True
        assert result.check_name == "S3 KMS Encryption"
        assert 'test-bucket' in result.details
    
    def test_validate_s3_encryption_failure(self, validator):
        """Test S3 encryption validation when KMS is not used."""
        validator.s3_client.get_bucket_encryption = Mock(return_value={
            'ServerSideEncryptionConfiguration': {
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'  # Not KMS
                    }
                }]
            }
        })
        
        result = validator.validate_s3_encryption('test-bucket')
        
        assert result.passed is False
        assert result.check_name == "S3 KMS Encryption"
    
    def test_validate_dynamodb_encryption_success(self, validator):
        """Test DynamoDB encryption validation when KMS is used."""
        validator.dynamodb_client.describe_table = Mock(return_value={
            'Table': {
                'TableName': 'test-table',
                'SSEDescription': {
                    'Status': 'ENABLED',
                    'SSEType': 'KMS',
                    'KMSMasterKeyArn': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012'
                }
            }
        })
        
        result = validator.validate_dynamodb_encryption('test-table')
        
        assert result.passed is True
        assert result.check_name == "DynamoDB KMS Encryption"
        assert 'test-table' in result.details
    
    def test_validate_dynamodb_encryption_failure(self, validator):
        """Test DynamoDB encryption validation when KMS is not used."""
        validator.dynamodb_client.describe_table = Mock(return_value={
            'Table': {
                'TableName': 'test-table',
                'SSEDescription': {
                    'Status': 'DISABLED'
                }
            }
        })
        
        result = validator.validate_dynamodb_encryption('test-table')
        
        assert result.passed is False
        assert result.check_name == "DynamoDB KMS Encryption"
    
    def test_validate_cloudwatch_logs_encryption_success(self, validator):
        """Test CloudWatch Logs encryption validation when KMS is used."""
        validator.logs_client.describe_log_groups = Mock(return_value={
            'logGroups': [{
                'logGroupName': '/aws/lambda/test-function',
                'kmsKeyId': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012'
            }]
        })
        
        result = validator.validate_cloudwatch_logs_encryption('/aws/lambda/test-function')
        
        assert result.passed is True
        assert result.check_name == "CloudWatch Logs KMS Encryption"
    
    def test_validate_cloudwatch_logs_encryption_failure(self, validator):
        """Test CloudWatch Logs encryption validation when KMS is not used."""
        validator.logs_client.describe_log_groups = Mock(return_value={
            'logGroups': [{
                'logGroupName': '/aws/lambda/test-function'
                # No kmsKeyId
            }]
        })
        
        result = validator.validate_cloudwatch_logs_encryption('/aws/lambda/test-function')
        
        assert result.passed is False
        assert result.check_name == "CloudWatch Logs KMS Encryption"
    
    def test_validate_vpc_no_internet_gateway_success(self, validator):
        """Test VPC validation when no internet gateway is attached."""
        validator.ec2_client.describe_internet_gateways = Mock(return_value={
            'InternetGateways': []
        })
        
        result = validator.validate_vpc_no_internet_gateway('vpc-12345')
        
        assert result.passed is True
        assert result.check_name == "VPC No Internet Gateway"
        assert 'vpc-12345' in result.details
    
    def test_validate_vpc_no_internet_gateway_failure(self, validator):
        """Test VPC validation when internet gateway is attached."""
        validator.ec2_client.describe_internet_gateways = Mock(return_value={
            'InternetGateways': [{
                'InternetGatewayId': 'igw-12345',
                'Attachments': [{'VpcId': 'vpc-12345', 'State': 'available'}]
            }]
        })
        
        result = validator.validate_vpc_no_internet_gateway('vpc-12345')
        
        assert result.passed is False
        assert result.check_name == "VPC No Internet Gateway"
    
    def test_validate_vpc_no_nat_gateway_success(self, validator):
        """Test VPC validation when no NAT gateway exists."""
        validator.ec2_client.describe_nat_gateways = Mock(return_value={
            'NatGateways': []
        })
        
        result = validator.validate_vpc_no_nat_gateway('vpc-12345')
        
        assert result.passed is True
        assert result.check_name == "VPC No NAT Gateway"
    
    def test_validate_vpc_no_nat_gateway_failure(self, validator):
        """Test VPC validation when NAT gateway exists."""
        validator.ec2_client.describe_nat_gateways = Mock(return_value={
            'NatGateways': [{
                'NatGatewayId': 'nat-12345',
                'VpcId': 'vpc-12345',
                'State': 'available'
            }]
        })
        
        result = validator.validate_vpc_no_nat_gateway('vpc-12345')
        
        assert result.passed is False
        assert result.check_name == "VPC No NAT Gateway"
    
    def test_validate_lambda_vpc_config_success(self, validator):
        """Test Lambda VPC configuration validation when VPC is configured."""
        validator.lambda_client.get_function_configuration = Mock(return_value={
            'FunctionName': 'test-function',
            'VpcConfig': {
                'VpcId': 'vpc-12345',
                'SubnetIds': ['subnet-1', 'subnet-2'],
                'SecurityGroupIds': ['sg-12345']
            }
        })
        
        result = validator.validate_lambda_vpc_config('test-function')
        
        assert result.passed is True
        assert result.check_name == "Lambda VPC Configuration"
        assert 'test-function' in result.details
    
    def test_validate_lambda_vpc_config_failure(self, validator):
        """Test Lambda VPC configuration validation when VPC is not configured."""
        validator.lambda_client.get_function_configuration = Mock(return_value={
            'FunctionName': 'test-function',
            'VpcConfig': {}
        })
        
        result = validator.validate_lambda_vpc_config('test-function')
        
        assert result.passed is False
        assert result.check_name == "Lambda VPC Configuration"
    
    def test_get_stack_resources(self, validator):
        """Test retrieving resources from CloudFormation stack."""
        validator.cloudformation_client.get_paginator = Mock(return_value=MagicMock())
        paginator = validator.cloudformation_client.get_paginator.return_value
        paginator.paginate.return_value = [{
            'StackResourceSummaries': [
                {'ResourceType': 'AWS::S3::Bucket', 'PhysicalResourceId': 'test-bucket'},
                {'ResourceType': 'AWS::DynamoDB::Table', 'PhysicalResourceId': 'test-table'},
                {'ResourceType': 'AWS::Logs::LogGroup', 'PhysicalResourceId': '/aws/lambda/test'},
                {'ResourceType': 'AWS::EC2::VPC', 'PhysicalResourceId': 'vpc-12345'},
                {'ResourceType': 'AWS::Lambda::Function', 'PhysicalResourceId': 'test-function'}
            ]
        }]
        
        resources = validator.get_stack_resources()
        
        assert 'test-bucket' in resources['s3_buckets']
        assert 'test-table' in resources['dynamodb_tables']
        assert '/aws/lambda/test' in resources['log_groups']
        assert 'vpc-12345' in resources['vpcs']
        assert 'test-function' in resources['lambda_functions']
