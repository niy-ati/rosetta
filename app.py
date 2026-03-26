#!/usr/bin/env python3
"""
Rosetta Zero CDK Application Entry Point.

This application deploys the Rosetta Zero infrastructure with support for
multiple environments (dev, staging, prod) and multi-region deployment.

Requirements: 23.1, 23.2
"""

import aws_cdk as cdk
from infrastructure.rosetta_zero_stack import RosettaZeroStack
from infrastructure.certificates_replica_bucket import CertificatesReplicaBucketStack

app = cdk.App()

# Get configuration from context
environment = app.node.try_get_context("environment") or "dev"
primary_region = app.node.try_get_context("region") or "us-east-1"
account = app.node.try_get_context("account")

# Validate required parameters
if not account:
    raise ValueError(
        "AWS account ID is required. "
        "Set in cdk.context.json or pass with -c account=123456789012"
    )

# Environment-specific tags
tags = {
    "Project": "RosettaZero",
    "Environment": environment,
    "ManagedBy": "CDK",
}

# Map primary regions to secondary regions for disaster recovery
region_pairs = {
    "us-east-1": "us-west-2",
    "us-west-2": "us-east-1",
    "eu-west-1": "eu-central-1",
    "eu-central-1": "eu-west-1",
    "ap-southeast-1": "ap-northeast-1",
    "ap-northeast-1": "ap-southeast-1",
}

secondary_region = region_pairs.get(primary_region, "us-west-2")

# Deploy replica bucket stack to secondary region (Requirements 27.2, 27.3)
# This should be deployed first before the main stack
replica_stack = CertificatesReplicaBucketStack(
    app,
    f"CertificatesReplicaBucketStack-{environment}",
    primary_region=primary_region,
    description=f"Rosetta Zero - Certificates Replica Bucket for Disaster Recovery ({environment})",
    env=cdk.Environment(
        account=account,
        region=secondary_region
    )
)

# Apply tags
for key, value in tags.items():
    cdk.Tags.of(replica_stack).add(key, value)

# Deploy main Rosetta Zero stack to primary region
main_stack = RosettaZeroStack(
    app,
    f"RosettaZeroStack-{environment}",
    description=f"Rosetta Zero - Legacy Code Modernization with Behavioral Equivalence Proof ({environment})",
    env=cdk.Environment(
        account=account,
        region=primary_region
    )
)

# Apply tags
for key, value in tags.items():
    cdk.Tags.of(main_stack).add(key, value)

app.synth()
