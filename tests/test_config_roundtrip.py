"""
Property-based tests for configuration round-trip consistency.

**Validates: Requirements 23.4**

This test verifies that parse(format(config)) == config for all valid configurations.
"""

import pytest
from hypothesis import given, strategies as st, settings
from rosetta_zero.models.config import (
    RosettaZeroConfig,
    parse_configuration,
    format_configuration,
)


# Hypothesis strategies for generating valid configurations

@st.composite
def aws_region_strategy(draw):
    """Generate valid AWS region strings."""
    prefix = draw(st.sampled_from(['us', 'eu', 'ap', 'sa', 'ca', 'me', 'af']))
    direction = draw(st.sampled_from(['east', 'west', 'north', 'south', 'central', 'northeast', 'southeast']))
    number = draw(st.integers(min_value=1, max_value=9))
    return f"{prefix}-{direction}-{number}"


@st.composite
def vpc_id_strategy(draw):
    """Generate valid VPC ID strings."""
    suffix = draw(st.text(alphabet='0123456789abcdef', min_size=8, max_size=17))
    return f"vpc-{suffix}"


@st.composite
def subnet_id_strategy(draw):
    """Generate valid subnet ID strings."""
    suffix = draw(st.text(alphabet='0123456789abcdef', min_size=8, max_size=17))
    return f"subnet-{suffix}"


@st.composite
def kms_key_id_strategy(draw):
    """Generate valid KMS key ID strings."""
    # Can be key ID, ARN, or alias
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        # Key ID format
        return draw(st.text(alphabet='0123456789abcdef-', min_size=36, max_size=36))
    elif choice == 1:
        # ARN format
        region = draw(aws_region_strategy())
        account = draw(st.text(alphabet='0123456789', min_size=12, max_size=12))
        key_id = draw(st.text(alphabet='0123456789abcdef-', min_size=36, max_size=36))
        return f"arn:aws:kms:{region}:{account}:key/{key_id}"
    else:
        # Alias format
        alias_name = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_', min_size=1, max_size=32))
        return f"alias/{alias_name}"


@st.composite
def valid_config_strategy(draw):
    """Generate valid RosettaZeroConfig objects."""
    aws_region = draw(aws_region_strategy())
    s3_bucket_prefix = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-', min_size=3, max_size=20))
    kms_key_id = draw(kms_key_id_strategy())
    vpc_id = draw(vpc_id_strategy())
    
    # Generate 1-5 subnet IDs
    num_subnets = draw(st.integers(min_value=1, max_value=5))
    private_subnet_ids = [draw(subnet_id_strategy()) for _ in range(num_subnets)]
    
    # Bedrock configuration
    bedrock_model_id = draw(st.sampled_from([
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "anthropic.claude-3-sonnet-20240229-v1:0",
        "anthropic.claude-3-haiku-20240307-v1:0",
    ]))
    
    # Knowledge base IDs (0-3 entries)
    num_kb = draw(st.integers(min_value=0, max_value=3))
    kb_languages = draw(st.lists(
        st.sampled_from(['COBOL', 'FORTRAN', 'MAINFRAME']),
        min_size=num_kb,
        max_size=num_kb,
        unique=True
    ))
    knowledge_base_ids = {
        lang: draw(st.text(alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', min_size=10, max_size=10))
        for lang in kb_languages
    }
    
    # Test generation configuration
    test_vector_count = draw(st.integers(min_value=1000, max_value=10_000_000))
    random_seed = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=2**31-1)))
    target_branch_coverage = draw(st.floats(min_value=0.5, max_value=1.0))
    
    # Execution configuration
    legacy_container_uri = draw(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-.:/', min_size=0, max_size=100))
    modern_lambda_timeout_seconds = draw(st.integers(min_value=1, max_value=900))
    fargate_cpu = draw(st.sampled_from([256, 512, 1024, 2048, 4096]))
    
    # Memory must be compatible with CPU
    if fargate_cpu == 256:
        fargate_memory_mb = draw(st.integers(min_value=512, max_value=2048))
    elif fargate_cpu == 512:
        fargate_memory_mb = draw(st.integers(min_value=1024, max_value=4096))
    elif fargate_cpu == 1024:
        fargate_memory_mb = draw(st.integers(min_value=2048, max_value=8192))
    elif fargate_cpu == 2048:
        fargate_memory_mb = draw(st.integers(min_value=4096, max_value=16384))
    else:  # 4096
        fargate_memory_mb = draw(st.integers(min_value=8192, max_value=30720))
    
    # Retry configuration
    max_retries = draw(st.integers(min_value=0, max_value=10))
    retry_backoff_base_seconds = draw(st.integers(min_value=1, max_value=10))
    
    # Logging configuration
    log_retention_days = draw(st.integers(min_value=1, max_value=3653))
    
    return RosettaZeroConfig(
        aws_region=aws_region,
        s3_bucket_prefix=s3_bucket_prefix,
        kms_key_id=kms_key_id,
        vpc_id=vpc_id,
        private_subnet_ids=private_subnet_ids,
        bedrock_model_id=bedrock_model_id,
        knowledge_base_ids=knowledge_base_ids,
        test_vector_count=test_vector_count,
        random_seed=random_seed,
        target_branch_coverage=target_branch_coverage,
        legacy_container_uri=legacy_container_uri,
        modern_lambda_timeout_seconds=modern_lambda_timeout_seconds,
        fargate_cpu=fargate_cpu,
        fargate_memory_mb=fargate_memory_mb,
        max_retries=max_retries,
        retry_backoff_base_seconds=retry_backoff_base_seconds,
        log_retention_days=log_retention_days,
    )


class TestConfigurationRoundTrip:
    """
    Property 1: Configuration Round-Trip Consistency
    
    **Validates: Requirements 23.4**
    
    For all valid RosettaZeroConfig objects, the following property must hold:
        parse(format(config)) == config
    
    This ensures that configuration serialization and deserialization are inverse operations.
    """
    
    @given(config=valid_config_strategy())
    @settings(max_examples=100, deadline=None)
    def test_config_roundtrip_property(self, config: RosettaZeroConfig):
        """
        Test that parse(format(config)) == config for all valid configurations.
        
        This property ensures that:
        1. Configuration can be serialized to JSON
        2. The JSON can be parsed back to a configuration object
        3. The parsed configuration is equal to the original
        """
        # Format configuration to JSON
        formatted = format_configuration(config)
        
        # Parse JSON back to configuration
        parsed = parse_configuration(formatted)
        
        # Verify round-trip consistency
        assert parsed.aws_region == config.aws_region
        assert parsed.s3_bucket_prefix == config.s3_bucket_prefix
        assert parsed.kms_key_id == config.kms_key_id
        assert parsed.vpc_id == config.vpc_id
        assert parsed.private_subnet_ids == config.private_subnet_ids
        assert parsed.bedrock_model_id == config.bedrock_model_id
        assert parsed.knowledge_base_ids == config.knowledge_base_ids
        assert parsed.test_vector_count == config.test_vector_count
        assert parsed.random_seed == config.random_seed
        assert parsed.target_branch_coverage == config.target_branch_coverage
        assert parsed.legacy_container_uri == config.legacy_container_uri
        assert parsed.modern_lambda_timeout_seconds == config.modern_lambda_timeout_seconds
        assert parsed.fargate_cpu == config.fargate_cpu
        assert parsed.fargate_memory_mb == config.fargate_memory_mb
        assert parsed.max_retries == config.max_retries
        assert parsed.retry_backoff_base_seconds == config.retry_backoff_base_seconds
        assert parsed.log_retention_days == config.log_retention_days
    
    @given(config=valid_config_strategy())
    @settings(max_examples=50, deadline=None)
    def test_config_validation_passes(self, config: RosettaZeroConfig):
        """Test that all generated configurations pass validation."""
        errors = config.validate()
        assert len(errors) == 0, f"Generated config should be valid, but got errors: {errors}"
    
    @given(config=valid_config_strategy())
    @settings(max_examples=50, deadline=None)
    def test_double_roundtrip(self, config: RosettaZeroConfig):
        """Test that double round-trip produces the same result."""
        # First round-trip
        formatted1 = format_configuration(config)
        parsed1 = parse_configuration(formatted1)
        
        # Second round-trip
        formatted2 = format_configuration(parsed1)
        parsed2 = parse_configuration(formatted2)
        
        # Both should be equal
        assert parsed1.aws_region == parsed2.aws_region
        assert parsed1.s3_bucket_prefix == parsed2.s3_bucket_prefix
        assert parsed1.kms_key_id == parsed2.kms_key_id
        assert parsed1.vpc_id == parsed2.vpc_id
        assert parsed1.private_subnet_ids == parsed2.private_subnet_ids


class TestConfigurationValidation:
    """Test configuration validation edge cases."""
    
    def test_missing_required_fields(self):
        """Test that missing required fields are caught."""
        invalid_json = '{}'
        
        with pytest.raises(ValueError) as exc_info:
            parse_configuration(invalid_json)
        
        assert "Missing required field" in str(exc_info.value) or "required" in str(exc_info.value).lower()
    
    def test_invalid_json(self):
        """Test that invalid JSON is caught."""
        invalid_json = '{ invalid json }'
        
        with pytest.raises(ValueError) as exc_info:
            parse_configuration(invalid_json)
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_invalid_test_vector_count(self):
        """Test that invalid test_vector_count is caught."""
        config = RosettaZeroConfig(
            aws_region='us-east-1',
            s3_bucket_prefix='test',
            kms_key_id='alias/test',
            vpc_id='vpc-12345678',
            private_subnet_ids=['subnet-12345678'],
            test_vector_count=-1,  # Invalid
        )
        
        errors = config.validate()
        assert any('test_vector_count' in err for err in errors)
    
    def test_invalid_branch_coverage(self):
        """Test that invalid target_branch_coverage is caught."""
        config = RosettaZeroConfig(
            aws_region='us-east-1',
            s3_bucket_prefix='test',
            kms_key_id='alias/test',
            vpc_id='vpc-12345678',
            private_subnet_ids=['subnet-12345678'],
            target_branch_coverage=1.5,  # Invalid (> 1.0)
        )
        
        errors = config.validate()
        assert any('target_branch_coverage' in err for err in errors)
    
    def test_invalid_lambda_timeout(self):
        """Test that invalid Lambda timeout is caught."""
        config = RosettaZeroConfig(
            aws_region='us-east-1',
            s3_bucket_prefix='test',
            kms_key_id='alias/test',
            vpc_id='vpc-12345678',
            private_subnet_ids=['subnet-12345678'],
            modern_lambda_timeout_seconds=1000,  # Invalid (> 900)
        )
        
        errors = config.validate()
        assert any('timeout' in err.lower() for err in errors)
    
    def test_invalid_fargate_cpu(self):
        """Test that invalid Fargate CPU is caught."""
        config = RosettaZeroConfig(
            aws_region='us-east-1',
            s3_bucket_prefix='test',
            kms_key_id='alias/test',
            vpc_id='vpc-12345678',
            private_subnet_ids=['subnet-12345678'],
            fargate_cpu=1000,  # Invalid (not in allowed values)
        )
        
        errors = config.validate()
        assert any('fargate_cpu' in err for err in errors)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
