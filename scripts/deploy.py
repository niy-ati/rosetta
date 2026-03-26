#!/usr/bin/env python3
"""
CDK Deployment Script for Rosetta Zero.

This script provides a convenient interface for deploying Rosetta Zero infrastructure
with environment-specific configurations and parameter validation.

Requirements: 23.1, 23.2
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


class DeploymentConfig:
    """Configuration for CDK deployment."""
    
    # Valid AWS regions
    VALID_REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2"
    ]
    
    # Environment-specific configurations
    ENVIRONMENTS = {
        "dev": {
            "description": "Development environment",
            "log_retention_days": 7,
            "enable_deletion_protection": False,
            "enable_termination_protection": False,
        },
        "staging": {
            "description": "Staging environment",
            "log_retention_days": 30,
            "enable_deletion_protection": True,
            "enable_termination_protection": False,
        },
        "prod": {
            "description": "Production environment",
            "log_retention_days": 2555,  # 7 years for compliance
            "enable_deletion_protection": True,
            "enable_termination_protection": True,
        }
    }
    
    def __init__(self, environment: str, region: str, account: str):
        """Initialize deployment configuration."""
        self.environment = environment
        self.region = region
        self.account = account
        self.env_config = self.ENVIRONMENTS[environment]
    
    @classmethod
    def validate_environment(cls, environment: str) -> List[str]:
        """Validate environment parameter."""
        errors = []
        if environment not in cls.ENVIRONMENTS:
            errors.append(
                f"Invalid environment '{environment}'. "
                f"Must be one of: {', '.join(cls.ENVIRONMENTS.keys())}"
            )
        return errors
    
    @classmethod
    def validate_region(cls, region: str) -> List[str]:
        """Validate AWS region parameter."""
        errors = []
        if region not in cls.VALID_REGIONS:
            errors.append(
                f"Invalid region '{region}'. "
                f"Must be one of: {', '.join(cls.VALID_REGIONS)}"
            )
        return errors
    
    @classmethod
    def validate_account(cls, account: str) -> List[str]:
        """Validate AWS account ID parameter."""
        errors = []
        if not account:
            errors.append("AWS account ID is required")
        elif not account.isdigit():
            errors.append(f"Invalid account ID '{account}'. Must be numeric.")
        elif len(account) != 12:
            errors.append(f"Invalid account ID '{account}'. Must be 12 digits.")
        return errors
    
    def to_cdk_context(self) -> Dict[str, any]:
        """Convert configuration to CDK context."""
        return {
            "environment": self.environment,
            "region": self.region,
            "account": self.account,
            "logRetentionDays": self.env_config["log_retention_days"],
            "enableDeletionProtection": self.env_config["enable_deletion_protection"],
            "enableTerminationProtection": self.env_config["enable_termination_protection"],
        }


def validate_parameters(
    environment: str,
    region: str,
    account: str
) -> List[str]:
    """
    Validate deployment parameters.
    
    Requirements: 23.1, 23.2
    
    Args:
        environment: Target environment (dev, staging, prod)
        region: AWS region
        account: AWS account ID
    
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    errors.extend(DeploymentConfig.validate_environment(environment))
    errors.extend(DeploymentConfig.validate_region(region))
    errors.extend(DeploymentConfig.validate_account(account))
    
    return errors


def update_cdk_context(config: DeploymentConfig) -> None:
    """
    Update cdk.context.json with deployment configuration.
    
    Args:
        config: Deployment configuration
    """
    context_file = Path("cdk.context.json")
    
    # Read existing context
    if context_file.exists():
        with open(context_file, "r") as f:
            context = json.load(f)
    else:
        context = {}
    
    # Update with deployment config
    context.update(config.to_cdk_context())
    
    # Write updated context
    with open(context_file, "w") as f:
        json.dump(context, f, indent=2)
    
    print(f"✓ Updated cdk.context.json with {config.environment} configuration")


def run_cdk_command(command: str, args: List[str] = None) -> int:
    """
    Run a CDK command.
    
    Args:
        command: CDK command (synth, deploy, destroy, diff)
        args: Additional arguments for the command
    
    Returns:
        Exit code from CDK command
    """
    cmd = ["cdk", command]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd)
    return result.returncode


def synth(config: DeploymentConfig, stack: Optional[str] = None) -> int:
    """
    Synthesize CloudFormation templates.
    
    Args:
        config: Deployment configuration
        stack: Optional specific stack to synthesize
    
    Returns:
        Exit code
    """
    print(f"\n🔨 Synthesizing CloudFormation templates for {config.environment}...")
    update_cdk_context(config)
    
    args = []
    if stack:
        args.append(stack)
    
    return run_cdk_command("synth", args)


def deploy(
    config: DeploymentConfig,
    stack: Optional[str] = None,
    require_approval: bool = True,
    hotswap: bool = False
) -> int:
    """
    Deploy infrastructure.
    
    Args:
        config: Deployment configuration
        stack: Optional specific stack to deploy
        require_approval: Whether to require manual approval for changes
        hotswap: Enable hotswap deployments for faster iteration (dev only)
    
    Returns:
        Exit code
    """
    print(f"\n🚀 Deploying Rosetta Zero to {config.environment} ({config.region})...")
    update_cdk_context(config)
    
    # Validate hotswap usage
    if hotswap and config.environment != "dev":
        print("⚠️  Warning: Hotswap deployments are only recommended for dev environment")
        response = input("Continue anyway? (yes/no): ")
        if response.lower() != "yes":
            print("Deployment cancelled")
            return 1
    
    args = []
    if stack:
        args.append(stack)
    
    if not require_approval:
        args.append("--require-approval=never")
    
    if hotswap:
        args.append("--hotswap")
    
    return run_cdk_command("deploy", args)


def destroy(
    config: DeploymentConfig,
    stack: Optional[str] = None,
    force: bool = False
) -> int:
    """
    Destroy infrastructure.
    
    Args:
        config: Deployment configuration
        stack: Optional specific stack to destroy
        force: Skip confirmation prompt
    
    Returns:
        Exit code
    """
    print(f"\n🗑️  Destroying Rosetta Zero infrastructure in {config.environment}...")
    
    # Extra confirmation for production
    if config.environment == "prod" and not force:
        print("\n⚠️  WARNING: You are about to destroy PRODUCTION infrastructure!")
        print("This action cannot be undone.")
        response = input("Type 'destroy-production' to confirm: ")
        if response != "destroy-production":
            print("Destruction cancelled")
            return 1
    
    update_cdk_context(config)
    
    args = []
    if stack:
        args.append(stack)
    
    if force:
        args.append("--force")
    
    return run_cdk_command("destroy", args)


def diff(config: DeploymentConfig, stack: Optional[str] = None) -> int:
    """
    Show differences between deployed and local infrastructure.
    
    Args:
        config: Deployment configuration
        stack: Optional specific stack to diff
    
    Returns:
        Exit code
    """
    print(f"\n📊 Showing infrastructure differences for {config.environment}...")
    update_cdk_context(config)
    
    args = []
    if stack:
        args.append(stack)
    
    return run_cdk_command("diff", args)


def bootstrap(region: str, account: str) -> int:
    """
    Bootstrap CDK in the target account/region.
    
    Args:
        region: AWS region
        account: AWS account ID
    
    Returns:
        Exit code
    """
    print(f"\n🥾 Bootstrapping CDK in account {account}, region {region}...")
    
    args = [
        f"aws://{account}/{region}",
        "--cloudformation-execution-policies",
        "arn:aws:iam::aws:policy/AdministratorAccess"
    ]
    
    return run_cdk_command("bootstrap", args)


def main():
    """Main entry point for deployment script."""
    parser = argparse.ArgumentParser(
        description="Deploy Rosetta Zero infrastructure with CDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Synthesize templates for dev environment
  python scripts/deploy.py synth --env dev --region us-east-1 --account 123456789012
  
  # Deploy to staging
  python scripts/deploy.py deploy --env staging --region us-east-1 --account 123456789012
  
  # Deploy specific stack to production
  python scripts/deploy.py deploy --env prod --region us-east-1 --account 123456789012 --stack RosettaZeroStack
  
  # Show differences before deploying
  python scripts/deploy.py diff --env dev --region us-east-1 --account 123456789012
  
  # Destroy dev environment
  python scripts/deploy.py destroy --env dev --region us-east-1 --account 123456789012
  
  # Bootstrap CDK
  python scripts/deploy.py bootstrap --region us-east-1 --account 123456789012
        """
    )
    
    parser.add_argument(
        "command",
        choices=["synth", "deploy", "destroy", "diff", "bootstrap"],
        help="CDK command to execute"
    )
    
    parser.add_argument(
        "--env",
        "--environment",
        dest="environment",
        choices=["dev", "staging", "prod"],
        help="Target environment (required for synth, deploy, destroy, diff)"
    )
    
    parser.add_argument(
        "--region",
        required=True,
        help="AWS region (e.g., us-east-1)"
    )
    
    parser.add_argument(
        "--account",
        required=True,
        help="AWS account ID (12 digits)"
    )
    
    parser.add_argument(
        "--stack",
        help="Specific stack to operate on (optional)"
    )
    
    parser.add_argument(
        "--no-approval",
        action="store_true",
        help="Skip approval prompts (deploy only)"
    )
    
    parser.add_argument(
        "--hotswap",
        action="store_true",
        help="Enable hotswap deployments for faster iteration (dev only)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts (destroy only)"
    )
    
    args = parser.parse_args()
    
    # Bootstrap doesn't require environment
    if args.command == "bootstrap":
        # Validate region and account
        errors = []
        errors.extend(DeploymentConfig.validate_region(args.region))
        errors.extend(DeploymentConfig.validate_account(args.account))
        
        if errors:
            print("❌ Parameter validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        
        return bootstrap(args.region, args.account)
    
    # Other commands require environment
    if not args.environment:
        print("❌ Error: --env is required for this command")
        parser.print_help()
        return 1
    
    # Validate parameters
    errors = validate_parameters(args.environment, args.region, args.account)
    if errors:
        print("❌ Parameter validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    
    # Create configuration
    config = DeploymentConfig(args.environment, args.region, args.account)
    
    # Execute command
    if args.command == "synth":
        return synth(config, args.stack)
    elif args.command == "deploy":
        return deploy(
            config,
            args.stack,
            require_approval=not args.no_approval,
            hotswap=args.hotswap
        )
    elif args.command == "destroy":
        return destroy(config, args.stack, args.force)
    elif args.command == "diff":
        return diff(config, args.stack)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
