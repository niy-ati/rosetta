"""Configuration data models and parser."""

import json
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class RosettaZeroConfig:
    """System configuration."""
    
    # AWS Configuration
    aws_region: str
    s3_bucket_prefix: str
    kms_key_id: str
    vpc_id: str
    private_subnet_ids: List[str]
    
    # Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    knowledge_base_ids: Dict[str, str] = None
    
    # Test Generation Configuration
    test_vector_count: int = 1_000_000
    random_seed: Optional[int] = None
    target_branch_coverage: float = 0.95
    
    # Execution Configuration
    legacy_container_uri: str = ""
    modern_lambda_timeout_seconds: int = 900
    fargate_cpu: int = 2048
    fargate_memory_mb: int = 4096
    
    # Retry Configuration
    max_retries: int = 3
    retry_backoff_base_seconds: int = 2
    
    # Logging Configuration
    log_retention_days: int = 2555  # 7 years

    def __post_init__(self):
        """Initialize default values."""
        if self.knowledge_base_ids is None:
            self.knowledge_base_ids = {}

    def to_json(self) -> str:
        """Serialize configuration to JSON."""
        data = {
            'aws_region': self.aws_region,
            's3_bucket_prefix': self.s3_bucket_prefix,
            'kms_key_id': self.kms_key_id,
            'vpc_id': self.vpc_id,
            'private_subnet_ids': self.private_subnet_ids,
            'bedrock_model_id': self.bedrock_model_id,
            'knowledge_base_ids': self.knowledge_base_ids,
            'test_vector_count': self.test_vector_count,
            'random_seed': self.random_seed,
            'target_branch_coverage': self.target_branch_coverage,
            'legacy_container_uri': self.legacy_container_uri,
            'modern_lambda_timeout_seconds': self.modern_lambda_timeout_seconds,
            'fargate_cpu': self.fargate_cpu,
            'fargate_memory_mb': self.fargate_memory_mb,
            'max_retries': self.max_retries,
            'retry_backoff_base_seconds': self.retry_backoff_base_seconds,
            'log_retention_days': self.log_retention_days,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'RosettaZeroConfig':
        """Deserialize configuration from JSON."""
        data = json.loads(json_str)
        return cls(
            aws_region=data['aws_region'],
            s3_bucket_prefix=data['s3_bucket_prefix'],
            kms_key_id=data['kms_key_id'],
            vpc_id=data['vpc_id'],
            private_subnet_ids=data['private_subnet_ids'],
            bedrock_model_id=data.get('bedrock_model_id', "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            knowledge_base_ids=data.get('knowledge_base_ids', {}),
            test_vector_count=data.get('test_vector_count', 1_000_000),
            random_seed=data.get('random_seed'),
            target_branch_coverage=data.get('target_branch_coverage', 0.95),
            legacy_container_uri=data.get('legacy_container_uri', ''),
            modern_lambda_timeout_seconds=data.get('modern_lambda_timeout_seconds', 900),
            fargate_cpu=data.get('fargate_cpu', 2048),
            fargate_memory_mb=data.get('fargate_memory_mb', 4096),
            max_retries=data.get('max_retries', 3),
            retry_backoff_base_seconds=data.get('retry_backoff_base_seconds', 2),
            log_retention_days=data.get('log_retention_days', 2555),
        )

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []
        
        # Validate required fields
        if not self.aws_region:
            errors.append("aws_region is required")
        
        if not self.s3_bucket_prefix:
            errors.append("s3_bucket_prefix is required")
        
        if not self.kms_key_id:
            errors.append("kms_key_id is required")
        
        if not self.vpc_id:
            errors.append("vpc_id is required")
        
        if not self.private_subnet_ids:
            errors.append("private_subnet_ids is required and must not be empty")
        
        if not self.bedrock_model_id:
            errors.append("bedrock_model_id is required")
        
        # Validate numeric constraints
        if self.test_vector_count <= 0:
            errors.append("test_vector_count must be positive")
        
        if self.target_branch_coverage < 0.0 or self.target_branch_coverage > 1.0:
            errors.append("target_branch_coverage must be between 0.0 and 1.0")
        
        if self.modern_lambda_timeout_seconds <= 0:
            errors.append("modern_lambda_timeout_seconds must be positive")
        
        if self.modern_lambda_timeout_seconds > 900:
            errors.append("modern_lambda_timeout_seconds cannot exceed 900 (AWS Lambda limit)")
        
        if self.fargate_cpu not in [256, 512, 1024, 2048, 4096]:
            errors.append("fargate_cpu must be one of: 256, 512, 1024, 2048, 4096")
        
        if self.fargate_memory_mb < 512 or self.fargate_memory_mb > 30720:
            errors.append("fargate_memory_mb must be between 512 and 30720")
        
        if self.max_retries < 0:
            errors.append("max_retries must be non-negative")
        
        if self.retry_backoff_base_seconds <= 0:
            errors.append("retry_backoff_base_seconds must be positive")
        
        if self.log_retention_days <= 0:
            errors.append("log_retention_days must be positive")
        
        # Validate AWS region format
        if self.aws_region and not self._is_valid_aws_region(self.aws_region):
            errors.append(f"invalid aws_region format: {self.aws_region}")
        
        # Validate VPC ID format
        if self.vpc_id and not self.vpc_id.startswith('vpc-'):
            errors.append(f"invalid vpc_id format: {self.vpc_id}")
        
        # Validate subnet IDs format
        for subnet_id in self.private_subnet_ids:
            if not subnet_id.startswith('subnet-'):
                errors.append(f"invalid subnet_id format: {subnet_id}")
        
        return errors

    @staticmethod
    def _is_valid_aws_region(region: str) -> bool:
        """Check if region string matches AWS region format."""
        # Basic validation: region should match pattern like us-east-1, eu-west-2, etc.
        parts = region.split('-')
        if len(parts) < 3:
            return False
        
        # First part should be a valid region prefix
        valid_prefixes = ['us', 'eu', 'ap', 'sa', 'ca', 'me', 'af']
        if parts[0] not in valid_prefixes:
            return False
        
        # Second part should be a direction
        valid_directions = ['east', 'west', 'north', 'south', 'central', 'northeast', 'southeast']
        if parts[1] not in valid_directions:
            return False
        
        # Third part should be a number
        try:
            int(parts[2])
            return True
        except ValueError:
            return False


def parse_configuration(config_str: str) -> RosettaZeroConfig:
    """
    Parse configuration string into RosettaZeroConfig object.
    
    Args:
        config_str: JSON string containing configuration
        
    Returns:
        RosettaZeroConfig object
        
    Raises:
        ValueError: If configuration is invalid
    """
    try:
        config = RosettaZeroConfig.from_json(config_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    except KeyError as e:
        raise ValueError(f"Missing required field: {e}")
    
    # Validate configuration
    errors = config.validate()
    if errors:
        raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
    
    return config


def format_configuration(config: RosettaZeroConfig) -> str:
    """
    Format RosettaZeroConfig object into JSON string.
    
    Args:
        config: RosettaZeroConfig object
        
    Returns:
        JSON string representation
    """
    return config.to_json()
