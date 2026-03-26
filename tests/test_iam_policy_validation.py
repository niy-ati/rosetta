"""
Unit tests for IAM policy validation script.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from scripts.iam_policy_validation import IAMPolicyValidator, PolicyViolation


class TestIAMPolicyValidator:
    """Tests for IAMPolicyValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create an IAMPolicyValidator instance with mocked clients."""
        with patch('scripts.iam_policy_validation.boto3'):
            validator = IAMPolicyValidator(stack_name="TestStack")
            return validator
    
    def test_check_wildcard_actions_complete_wildcard(self, validator):
        """Test detection of complete wildcard action."""
        statement = {
            'Effect': 'Allow',
            'Action': '*',
            'Resource': 'arn:aws:s3:::my-bucket/*'
        }
        
        violations = validator.check_wildcard_actions('test-role', 'test-policy', statement)
        
        assert len(violations) == 1
        assert violations[0].violation_type == "Complete wildcard action"
        assert violations[0].severity == "HIGH"
    
    def test_check_wildcard_actions_service_wildcard(self, validator):
        """Test detection of service-level wildcard action."""
        statement = {
            'Effect': 'Allow',
            'Action': 's3:*',
            'Resource': 'arn:aws:s3:::my-bucket/*'
        }
        
        violations = validator.check_wildcard_actions('test-role', 'test-policy', statement)
        
        assert len(violations) == 1
        assert violations[0].violation_type == "Service-level wildcard action"
        assert violations[0].severity == "HIGH"
    
    def test_check_wildcard_actions_acceptable(self, validator):
        """Test that acceptable wildcard actions don't trigger violations."""
        statement = {
            'Effect': 'Allow',
            'Action': ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
            'Resource': '*'
        }
        
        violations = validator.check_wildcard_actions('test-role', 'test-policy', statement)
        
        assert len(violations) == 0
    
    def test_check_wildcard_resources_with_non_acceptable_actions(self, validator):
        """Test detection of wildcard resource with non-acceptable actions."""
        statement = {
            'Effect': 'Allow',
            'Action': ['s3:GetObject', 's3:PutObject'],
            'Resource': '*'
        }
        
        violations = validator.check_wildcard_resources('test-role', 'test-policy', statement)
        
        assert len(violations) == 1
        assert violations[0].violation_type == "Wildcard resource with non-standard actions"
        assert violations[0].severity == "HIGH"
    
    def test_check_wildcard_resources_with_acceptable_actions(self, validator):
        """Test that wildcard resource with acceptable actions doesn't trigger violations."""
        statement = {
            'Effect': 'Allow',
            'Action': ['logs:CreateLogGroup', 'logs:CreateLogStream'],
            'Resource': '*'
        }
        
        violations = validator.check_wildcard_resources('test-role', 'test-policy', statement)
        
        assert len(violations) == 0
    
    def test_check_overly_permissive_principals_wildcard(self, validator):
        """Test detection of wildcard principal."""
        statement = {
            'Effect': 'Allow',
            'Principal': '*',
            'Action': 's3:GetObject',
            'Resource': 'arn:aws:s3:::my-bucket/*'
        }
        
        violations = validator.check_overly_permissive_principals('test-role', 'test-policy', statement)
        
        assert len(violations) == 1
        assert violations[0].violation_type == "Wildcard principal"
        assert violations[0].severity == "HIGH"
    
    def test_check_overly_permissive_principals_service_wildcard(self, validator):
        """Test detection of service wildcard principal."""
        statement = {
            'Effect': 'Allow',
            'Principal': {'Service': '*'},
            'Action': 's3:GetObject',
            'Resource': 'arn:aws:s3:::my-bucket/*'
        }
        
        violations = validator.check_overly_permissive_principals('test-role', 'test-policy', statement)
        
        assert len(violations) == 1
        assert violations[0].violation_type == "Wildcard Service principal"
        assert violations[0].severity == "MEDIUM"
    
    def test_validate_policy_document_with_violations(self, validator):
        """Test validation of policy document with violations."""
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': '*',
                    'Resource': '*'
                }
            ]
        }
        
        violations = validator.validate_policy_document('test-role', 'test-policy', policy_doc)
        
        # Should have violations for both wildcard action and wildcard resource
        assert len(violations) >= 1
        assert any(v.violation_type == "Complete wildcard action" for v in violations)
    
    def test_validate_policy_document_without_violations(self, validator):
        """Test validation of policy document without violations."""
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': ['s3:GetObject'],
                    'Resource': 'arn:aws:s3:::my-bucket/*'
                }
            ]
        }
        
        violations = validator.validate_policy_document('test-role', 'test-policy', policy_doc)
        
        assert len(violations) == 0
    
    def test_validate_policy_document_deny_statement(self, validator):
        """Test that Deny statements are not checked for violations."""
        policy_doc = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Deny',
                    'Action': '*',
                    'Resource': '*'
                }
            ]
        }
        
        violations = validator.validate_policy_document('test-role', 'test-policy', policy_doc)
        
        # Deny statements should not trigger violations
        assert len(violations) == 0
    
    def test_get_stack_roles(self, validator):
        """Test retrieving IAM roles from CloudFormation stack."""
        validator.cloudformation_client.get_paginator = Mock(return_value=MagicMock())
        paginator = validator.cloudformation_client.get_paginator.return_value
        paginator.paginate.return_value = [{
            'StackResourceSummaries': [
                {'ResourceType': 'AWS::IAM::Role', 'PhysicalResourceId': 'test-role-1'},
                {'ResourceType': 'AWS::IAM::Role', 'PhysicalResourceId': 'test-role-2'},
                {'ResourceType': 'AWS::Lambda::Function', 'PhysicalResourceId': 'test-function'}
            ]
        }]
        
        roles = validator.get_stack_roles()
        
        assert len(roles) == 2
        assert 'test-role-1' in roles
        assert 'test-role-2' in roles
        assert 'test-function' not in roles
    
    def test_get_role_policies(self, validator):
        """Test retrieving policies for a role."""
        validator.iam_client.list_role_policies = Mock(return_value={
            'PolicyNames': ['inline-policy-1']
        })
        validator.iam_client.get_role_policy = Mock(return_value={
            'PolicyDocument': {
                'Version': '2012-10-17',
                'Statement': []
            }
        })
        validator.iam_client.list_attached_role_policies = Mock(return_value={
            'AttachedPolicies': []
        })
        
        policies = validator.get_role_policies('test-role')
        
        assert len(policies['inline']) == 1
        assert policies['inline'][0]['name'] == 'inline-policy-1'
        assert len(policies['managed']) == 0
