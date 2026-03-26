"""
Unit tests for CDK deployment script.

Tests parameter validation and configuration management.
Requirements: 23.1, 23.2
"""

import json
import pytest
from pathlib import Path
import sys

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from deploy import DeploymentConfig, validate_parameters


class TestDeploymentConfig:
    """Test DeploymentConfig class."""
    
    def test_valid_environments(self):
        """Test that valid environments are accepted."""
        valid_envs = ["dev", "staging", "prod"]
        for env in valid_envs:
            errors = DeploymentConfig.validate_environment(env)
            assert len(errors) == 0, f"Environment '{env}' should be valid"
    
    def test_invalid_environment(self):
        """Test that invalid environments are rejected."""
        errors = DeploymentConfig.validate_environment("test")
        assert len(errors) == 1
        assert "Invalid environment" in errors[0]
    
    def test_valid_regions(self):
        """Test that valid AWS regions are accepted."""
        valid_regions = [
            "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"
        ]
        for region in valid_regions:
            errors = DeploymentConfig.validate_region(region)
            assert len(errors) == 0, f"Region '{region}' should be valid"
    
    def test_invalid_region(self):
        """Test that invalid regions are rejected."""
        errors = DeploymentConfig.validate_region("us-east-3")
        assert len(errors) == 1
        assert "Invalid region" in errors[0]
    
    def test_valid_account_id(self):
        """Test that valid account IDs are accepted."""
        errors = DeploymentConfig.validate_account("123456789012")
        assert len(errors) == 0
    
    def test_invalid_account_id_non_numeric(self):
        """Test that non-numeric account IDs are rejected."""
        errors = DeploymentConfig.validate_account("12345678901a")
        assert len(errors) == 1
        assert "Must be numeric" in errors[0]
    
    def test_invalid_account_id_wrong_length(self):
        """Test that account IDs with wrong length are rejected."""
        errors = DeploymentConfig.validate_account("12345")
        assert len(errors) == 1
        assert "Must be 12 digits" in errors[0]
    
    def test_empty_account_id(self):
        """Test that empty account IDs are rejected."""
        errors = DeploymentConfig.validate_account("")
        assert len(errors) == 1
        assert "required" in errors[0]
    
    def test_environment_config_dev(self):
        """Test dev environment configuration."""
        config = DeploymentConfig("dev", "us-east-1", "123456789012")
        assert config.env_config["log_retention_days"] == 7
        assert config.env_config["enable_deletion_protection"] is False
        assert config.env_config["enable_termination_protection"] is False
    
    def test_environment_config_staging(self):
        """Test staging environment configuration."""
        config = DeploymentConfig("staging", "us-east-1", "123456789012")
        assert config.env_config["log_retention_days"] == 30
        assert config.env_config["enable_deletion_protection"] is True
        assert config.env_config["enable_termination_protection"] is False
    
    def test_environment_config_prod(self):
        """Test prod environment configuration."""
        config = DeploymentConfig("prod", "us-east-1", "123456789012")
        assert config.env_config["log_retention_days"] == 2555  # 7 years
        assert config.env_config["enable_deletion_protection"] is True
        assert config.env_config["enable_termination_protection"] is True
    
    def test_to_cdk_context(self):
        """Test conversion to CDK context."""
        config = DeploymentConfig("dev", "us-east-1", "123456789012")
        context = config.to_cdk_context()
        
        assert context["environment"] == "dev"
        assert context["region"] == "us-east-1"
        assert context["account"] == "123456789012"
        assert context["logRetentionDays"] == 7
        assert context["enableDeletionProtection"] is False
        assert context["enableTerminationProtection"] is False


class TestParameterValidation:
    """Test parameter validation function."""
    
    def test_all_valid_parameters(self):
        """Test that all valid parameters pass validation."""
        errors = validate_parameters("dev", "us-east-1", "123456789012")
        assert len(errors) == 0
    
    def test_invalid_environment(self):
        """Test validation with invalid environment."""
        errors = validate_parameters("test", "us-east-1", "123456789012")
        assert len(errors) == 1
        assert "environment" in errors[0].lower()
    
    def test_invalid_region(self):
        """Test validation with invalid region."""
        errors = validate_parameters("dev", "invalid-region", "123456789012")
        assert len(errors) == 1
        assert "region" in errors[0].lower()
    
    def test_invalid_account(self):
        """Test validation with invalid account."""
        errors = validate_parameters("dev", "us-east-1", "invalid")
        assert len(errors) >= 1
        assert any("account" in err.lower() for err in errors)
    
    def test_multiple_invalid_parameters(self):
        """Test validation with multiple invalid parameters."""
        errors = validate_parameters("test", "invalid-region", "invalid")
        assert len(errors) >= 3
    
    def test_all_environments_with_valid_params(self):
        """Test all environments with valid parameters."""
        for env in ["dev", "staging", "prod"]:
            errors = validate_parameters(env, "us-east-1", "123456789012")
            assert len(errors) == 0, f"Environment '{env}' should be valid"
    
    def test_all_regions_with_valid_params(self):
        """Test all supported regions with valid parameters."""
        regions = [
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
            "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2"
        ]
        for region in regions:
            errors = validate_parameters("dev", region, "123456789012")
            assert len(errors) == 0, f"Region '{region}' should be valid"


class TestEnvironmentSpecificBehavior:
    """Test environment-specific behavior."""
    
    def test_dev_has_shortest_retention(self):
        """Test that dev has the shortest log retention."""
        dev_config = DeploymentConfig("dev", "us-east-1", "123456789012")
        staging_config = DeploymentConfig("staging", "us-east-1", "123456789012")
        prod_config = DeploymentConfig("prod", "us-east-1", "123456789012")
        
        assert dev_config.env_config["log_retention_days"] < staging_config.env_config["log_retention_days"]
        assert staging_config.env_config["log_retention_days"] < prod_config.env_config["log_retention_days"]
    
    def test_prod_has_all_protections_enabled(self):
        """Test that prod has all protections enabled."""
        config = DeploymentConfig("prod", "us-east-1", "123456789012")
        assert config.env_config["enable_deletion_protection"] is True
        assert config.env_config["enable_termination_protection"] is True
    
    def test_dev_has_no_protections(self):
        """Test that dev has no protections enabled."""
        config = DeploymentConfig("dev", "us-east-1", "123456789012")
        assert config.env_config["enable_deletion_protection"] is False
        assert config.env_config["enable_termination_protection"] is False
    
    def test_staging_has_partial_protections(self):
        """Test that staging has partial protections."""
        config = DeploymentConfig("staging", "us-east-1", "123456789012")
        assert config.env_config["enable_deletion_protection"] is True
        assert config.env_config["enable_termination_protection"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
