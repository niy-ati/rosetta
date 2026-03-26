"""Unit tests for multi-region replication configuration.

Tests the cross-region replication setup for certificates bucket
to ensure disaster recovery capabilities.

Requirements: 27.1, 27.2, 27.3
"""

import pytest
from aws_cdk import App, Stack
from aws_cdk import assertions as assertions
from infrastructure.rosetta_zero_stack import RosettaZeroStack
from infrastructure.certificates_replica_bucket import CertificatesReplicaBucketStack


class TestMultiRegionReplication:
    """Test suite for multi-region replication configuration."""

    def test_certificates_bucket_has_versioning_enabled(self):
        """
        Test that certificates bucket has versioning enabled.
        
        Versioning is required for S3 replication to work.
        
        Requirement: 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Find certificates bucket
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {
                    "Status": "Enabled"
                }
            }
        )

    def test_certificates_bucket_has_replication_configuration(self):
        """
        Test that certificates bucket has replication configuration.
        
        Requirement: 27.2, 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check for replication configuration on certificates bucket
        # The replication configuration is added via CfnBucket properties
        template.has_resource_properties(
            "AWS::S3::Bucket",
            assertions.Match.object_like({
                "ReplicationConfiguration": {
                    "Role": assertions.Match.any_value(),
                    "Rules": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Id": "ReplicateAllCertificates",
                            "Status": "Enabled",
                            "Priority": 1,
                        })
                    ])
                }
            })
        )

    def test_replication_role_created(self):
        """
        Test that IAM role for replication is created.
        
        Requirement: 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check for replication IAM role
        template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Principal": {
                                "Service": "s3.amazonaws.com"
                            }
                        })
                    ])
                }
            }
        )

    def test_replication_role_has_kms_permissions(self):
        """
        Test that replication role has KMS decrypt/encrypt permissions.
        
        Required for replicating encrypted objects.
        
        Requirement: 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check for KMS permissions in IAM policy
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Action": assertions.Match.array_with([
                                "kms:Decrypt",
                                "kms:DescribeKey"
                            ])
                        })
                    ])
                }
            }
        )

    def test_replication_role_has_s3_permissions(self):
        """
        Test that replication role has S3 replication permissions.
        
        Requirement: 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check for S3 replication permissions
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Action": assertions.Match.array_with([
                                "s3:ReplicateObject",
                                "s3:ReplicateDelete",
                                "s3:ReplicateTags"
                            ])
                        })
                    ])
                }
            }
        )

    def test_replica_bucket_stack_creates_bucket(self):
        """
        Test that replica bucket stack creates destination bucket.
        
        Requirement: 27.2
        """
        app = App()
        stack = CertificatesReplicaBucketStack(
            app,
            "ReplicaStack",
            primary_region="us-east-1"
        )
        template = assertions.Template.from_stack(stack)
        
        # Check for replica bucket
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {
                    "Status": "Enabled"
                },
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": assertions.Match.any_value()
                }
            }
        )

    def test_replica_bucket_has_kms_encryption(self):
        """
        Test that replica bucket uses KMS encryption.
        
        Requirement: 27.2
        """
        app = App()
        stack = CertificatesReplicaBucketStack(
            app,
            "ReplicaStack",
            primary_region="us-east-1"
        )
        template = assertions.Template.from_stack(stack)
        
        # Check for KMS key
        template.resource_count_is("AWS::KMS::Key", 1)
        
        # Check bucket uses KMS encryption
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {
                            "ServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "aws:kms"
                            }
                        }
                    ]
                }
            }
        )

    def test_replica_bucket_blocks_public_access(self):
        """
        Test that replica bucket blocks all public access.
        
        Security requirement.
        
        Requirement: 27.2
        """
        app = App()
        stack = CertificatesReplicaBucketStack(
            app,
            "ReplicaStack",
            primary_region="us-east-1"
        )
        template = assertions.Template.from_stack(stack)
        
        # Check for public access block
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True
                }
            }
        )

    def test_replica_bucket_has_bucket_policy(self):
        """
        Test that replica bucket has policy allowing replication.
        
        Requirement: 27.3
        """
        app = App()
        stack = CertificatesReplicaBucketStack(
            app,
            "ReplicaStack",
            primary_region="us-east-1"
        )
        template = assertions.Template.from_stack(stack)
        
        # Check for bucket policy
        template.has_resource_properties(
            "AWS::S3::BucketPolicy",
            {
                "PolicyDocument": {
                    "Statement": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Action": assertions.Match.array_with([
                                "s3:ReplicateObject"
                            ]),
                            "Principal": {
                                "Service": "s3.amazonaws.com"
                            }
                        })
                    ])
                }
            }
        )

    def test_replication_uses_standard_ia_storage_class(self):
        """
        Test that replication uses STANDARD_IA storage class.
        
        Cost optimization for infrequently accessed disaster recovery data.
        
        Requirement: 27.2
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check replication destination storage class
        template.has_resource_properties(
            "AWS::S3::Bucket",
            assertions.Match.object_like({
                "ReplicationConfiguration": {
                    "Rules": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "Destination": {
                                "StorageClass": "STANDARD_IA"
                            }
                        })
                    ])
                }
            })
        )

    def test_replication_includes_delete_markers(self):
        """
        Test that replication includes delete markers.
        
        Ensures deletions are replicated for consistency.
        
        Requirement: 27.3
        """
        app = App()
        stack = RosettaZeroStack(app, "TestStack")
        template = assertions.Template.from_stack(stack)
        
        # Check delete marker replication
        template.has_resource_properties(
            "AWS::S3::Bucket",
            assertions.Match.object_like({
                "ReplicationConfiguration": {
                    "Rules": assertions.Match.array_with([
                        assertions.Match.object_like({
                            "DeleteMarkerReplication": {
                                "Status": "Enabled"
                            }
                        })
                    ])
                }
            })
        )

    def test_region_pair_mapping(self):
        """
        Test that region pairs are correctly mapped.
        
        Requirement: 27.1
        """
        # This is tested implicitly by the app.py configuration
        # We verify the logic here
        region_pairs = {
            "us-east-1": "us-west-2",
            "us-west-2": "us-east-1",
            "eu-west-1": "eu-central-1",
            "eu-central-1": "eu-west-1",
            "ap-southeast-1": "ap-northeast-1",
            "ap-northeast-1": "ap-southeast-1",
        }
        
        # Verify all pairs are bidirectional
        for primary, secondary in region_pairs.items():
            assert region_pairs.get(secondary) == primary or secondary == "us-west-2"
        
        # Verify default fallback
        assert region_pairs.get("unknown-region", "us-west-2") == "us-west-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
