"""Helper module for creating certificates replica bucket in secondary region.

This module provides functionality to create the destination bucket for cross-region
replication of equivalence certificates. The destination bucket must be created
before enabling replication on the source bucket.

Requirements: 27.2, 27.3
"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_kms as kms,
    aws_iam as iam,
)
from constructs import Construct


class CertificatesReplicaBucketStack(Stack):
    """CDK stack for certificates replica bucket in secondary region.
    
    This stack creates the destination bucket for cross-region replication
    of equivalence certificates. It should be deployed to the secondary region
    before deploying the main RosettaZeroStack.
    
    Requirements: 27.2, 27.3
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        primary_region: str,
        **kwargs
    ) -> None:
        """Initialize the replica bucket stack.
        
        Args:
            scope: CDK scope
            construct_id: Construct identifier
            primary_region: The primary region where the main stack is deployed
            **kwargs: Additional stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create KMS key for replica bucket encryption
        replica_kms_key = kms.Key(
            self,
            "ReplicaEncryptionKey",
            description="KMS key for certificates replica bucket encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        replica_kms_key.add_alias("alias/rosetta-zero-certificates-replica")

        # Create replica bucket
        replica_bucket = s3.Bucket(
            self,
            "CertificatesReplicaBucket",
            bucket_name=f"rosetta-zero-certificates-replica-{self.account}-{self.region}",
            versioned=True,  # Required for replication
            encryption=s3.BucketEncryption.KMS,
            encryption_key=replica_kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,  # Retain for disaster recovery
        )

        # Grant S3 service permission to write replicated objects
        replica_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                actions=[
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                ],
                resources=[replica_bucket.arn_for_objects("*")],
            )
        )

        self.replica_bucket = replica_bucket
        self.replica_kms_key = replica_kms_key
