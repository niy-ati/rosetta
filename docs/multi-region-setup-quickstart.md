# Multi-Region Setup Quick Start

This guide provides a quick reference for setting up cross-region replication for Rosetta Zero certificates.

## Overview

Rosetta Zero automatically replicates equivalence certificates to a secondary AWS region for disaster recovery (Requirements 27.1, 27.2, 27.3).

## Quick Setup

### 1. Choose Your Regions

The system automatically pairs regions:

```
us-east-1 ↔ us-west-2
eu-west-1 ↔ eu-central-1
ap-southeast-1 ↔ ap-northeast-1
```

### 2. Deploy Both Stacks

```bash
# Set your AWS account and primary region
export CDK_DEFAULT_ACCOUNT=123456789012
export CDK_DEFAULT_REGION=us-east-1

# Deploy both stacks (replica first, then main)
cdk deploy CertificatesReplicaBucketStack
cdk deploy RosettaZeroStack
```

### 3. Verify Replication

```bash
# Check replication status
aws s3api get-bucket-replication \
  --bucket rosetta-zero-certificates-${CDK_DEFAULT_ACCOUNT}-${CDK_DEFAULT_REGION}
```

## What Gets Replicated

- ✅ All equivalence certificates
- ✅ Certificate metadata and tags
- ✅ Delete markers
- ✅ Object versions

## Storage Class

Replicated certificates use `STANDARD_IA` (Infrequent Access) storage for cost optimization.

## Monitoring

Key metrics to monitor:
- `ReplicationLatency`: Time to replicate objects
- `BytesPendingReplication`: Bytes waiting to replicate
- `OperationsPendingReplication`: Operations pending

## Disaster Recovery

If primary region fails:

```bash
# Access certificates from replica
aws s3 cp \
  s3://rosetta-zero-certificates-replica-${ACCOUNT}-${SECONDARY_REGION}/certificates/ \
  ./recovered/ \
  --recursive \
  --region ${SECONDARY_REGION}
```

## Cost Estimate

For 100 certificates/month (1 MB each):
- Data transfer: ~$2/month
- Storage: ~$0.01/month
- Requests: ~$0.01/month
- **Total: ~$2.02/month**

## Troubleshooting

### Replication Not Working

1. Verify both buckets have versioning enabled
2. Check IAM role permissions
3. Verify KMS key permissions
4. Check CloudWatch Logs for errors

### High Replication Lag

1. Check object sizes (large objects take longer)
2. Verify both regions are healthy
3. Review `ReplicationLatency` metric

## Security

- ✅ TLS 1.3 for data in transit
- ✅ KMS encryption at rest (both regions)
- ✅ No public access
- ✅ IAM least-privilege access

## References

- Full deployment guide: [multi-region-deployment.md](./multi-region-deployment.md)
- Requirements: 27.1, 27.2, 27.3
