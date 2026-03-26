# Multi-Region Deployment Guide for Rosetta Zero

This guide explains how to deploy Rosetta Zero with cross-region replication for disaster recovery.

## Overview

Rosetta Zero implements multi-region support to comply with data sovereignty requirements and provide disaster recovery capabilities (Requirements 27.1, 27.2, 27.3). Equivalence certificates are automatically replicated to a secondary AWS region.

## Architecture

- **Primary Region**: Hosts all Rosetta Zero infrastructure and services
- **Secondary Region**: Hosts replica bucket for equivalence certificates
- **Replication**: Automatic, asynchronous replication of all certificate objects

## Region Pairs

The system uses the following region pairs for disaster recovery:

| Primary Region | Secondary Region |
|---------------|------------------|
| us-east-1     | us-west-2       |
| us-west-2     | us-east-1       |
| eu-west-1     | eu-central-1    |
| eu-central-1  | eu-west-1       |
| ap-southeast-1| ap-northeast-1  |
| ap-northeast-1| ap-southeast-1  |

If your primary region is not listed, the system defaults to `us-west-2` as the secondary region.

## Deployment Steps

### Step 1: Deploy Replica Bucket Stack (Secondary Region)

First, deploy the replica bucket stack to the secondary region:

```bash
# Set your primary region
export PRIMARY_REGION=us-east-1

# Determine secondary region (use the mapping above)
export SECONDARY_REGION=us-west-2

# Deploy replica bucket stack to secondary region
cd infrastructure
cdk deploy CertificatesReplicaBucketStack \
  --region $SECONDARY_REGION \
  --context primaryRegion=$PRIMARY_REGION
```

This creates:
- KMS key for replica bucket encryption
- S3 bucket for certificate replicas
- Bucket policies for replication

### Step 2: Deploy Main Stack (Primary Region)

Deploy the main Rosetta Zero stack to the primary region:

```bash
# Deploy main stack to primary region
cdk deploy RosettaZeroStack --region $PRIMARY_REGION
```

This creates:
- All Rosetta Zero infrastructure
- Source certificates bucket with replication enabled
- IAM role for S3 replication
- Replication rules to secondary region

### Step 3: Verify Replication

After deployment, verify that replication is configured:

```bash
# Check replication configuration on source bucket
aws s3api get-bucket-replication \
  --bucket rosetta-zero-certificates-${AWS_ACCOUNT_ID}-${PRIMARY_REGION} \
  --region $PRIMARY_REGION

# Upload a test certificate
aws s3 cp test-certificate.json \
  s3://rosetta-zero-certificates-${AWS_ACCOUNT_ID}-${PRIMARY_REGION}/test/ \
  --region $PRIMARY_REGION

# Wait a few minutes, then check replica bucket
aws s3 ls \
  s3://rosetta-zero-certificates-replica-${AWS_ACCOUNT_ID}-${SECONDARY_REGION}/test/ \
  --region $SECONDARY_REGION
```

## Replication Behavior

### What Gets Replicated

- All objects in the certificates bucket
- Object metadata and tags
- Delete markers (when objects are deleted)

### Replication Timing

- Replication is asynchronous
- Most objects replicate within 15 minutes
- Large objects may take longer

### Storage Class

Replicated objects use `STANDARD_IA` (Infrequent Access) storage class for cost optimization, as certificates are primarily for compliance and disaster recovery.

## Disaster Recovery Procedures

### Scenario 1: Primary Region Unavailable

If the primary region becomes unavailable:

1. **Access Certificates**: Retrieve certificates from replica bucket
   ```bash
   aws s3 cp \
     s3://rosetta-zero-certificates-replica-${AWS_ACCOUNT_ID}-${SECONDARY_REGION}/certificates/ \
     ./recovered-certificates/ \
     --recursive \
     --region $SECONDARY_REGION
   ```

2. **Verify Signatures**: Use KMS in the secondary region to verify certificate signatures
   ```bash
   # Certificates are signed with KMS keys from primary region
   # Signature verification requires access to primary region KMS
   # For true disaster recovery, consider exporting public keys
   ```

3. **Restore Operations**: Deploy a new Rosetta Zero stack in an available region and restore from backups

### Scenario 2: Data Corruption in Primary Region

If data corruption occurs in the primary region:

1. **Identify Corruption**: Check CloudWatch Logs and S3 versioning
2. **Restore from Replica**: Copy uncorrupted versions from replica bucket
3. **Verify Integrity**: Validate certificate signatures and hashes

## Monitoring Replication

### CloudWatch Metrics

Monitor replication health using S3 replication metrics:

```bash
# Enable replication metrics
aws s3api put-bucket-replication \
  --bucket rosetta-zero-certificates-${AWS_ACCOUNT_ID}-${PRIMARY_REGION} \
  --replication-configuration file://replication-config.json \
  --region $PRIMARY_REGION
```

### Key Metrics

- `ReplicationLatency`: Time to replicate objects
- `BytesPendingReplication`: Bytes waiting to be replicated
- `OperationsPendingReplication`: Number of operations pending

### Alarms

Set up CloudWatch alarms for replication issues:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name rosetta-zero-replication-lag \
  --alarm-description "Alert when replication lag exceeds 1 hour" \
  --metric-name ReplicationLatency \
  --namespace AWS/S3 \
  --statistic Maximum \
  --period 3600 \
  --threshold 3600 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1
```

## Cost Considerations

### Replication Costs

- **Data Transfer**: Cross-region data transfer charges apply
- **Storage**: Replica bucket uses STANDARD_IA storage class
- **Requests**: PUT requests for each replicated object

### Estimated Costs

For a system generating 100 certificates per month (average 1 MB each):

- Data transfer: ~$2/month (100 MB × $0.02/GB)
- Storage: ~$0.0125/month (0.1 GB × $0.0125/GB)
- Requests: ~$0.01/month (100 PUT requests)

**Total**: ~$2.02/month

## Security Considerations

### Encryption

- Source bucket: Encrypted with customer-managed KMS key
- Replica bucket: Encrypted with KMS key in secondary region
- In-transit: TLS 1.3 for all replication traffic

### Access Control

- Replication role has minimal permissions
- Replica bucket blocks all public access
- SSL enforcement on both buckets

### Compliance

- Replication supports data sovereignty requirements (Requirement 27.1)
- Audit logs maintained in both regions
- 7-year retention for compliance

## Troubleshooting

### Replication Not Working

1. **Check IAM Role**: Verify replication role has correct permissions
2. **Check KMS Permissions**: Ensure replication role can decrypt/encrypt
3. **Check Bucket Versioning**: Both buckets must have versioning enabled
4. **Check Bucket Policies**: Verify replica bucket allows replication

### Replication Lag

1. **Check Object Size**: Large objects take longer to replicate
2. **Check Region Health**: Verify both regions are operational
3. **Check Metrics**: Review ReplicationLatency metric

### Missing Objects

1. **Check Replication Status**: Use S3 API to check object replication status
   ```bash
   aws s3api head-object \
     --bucket rosetta-zero-certificates-${AWS_ACCOUNT_ID}-${PRIMARY_REGION} \
     --key certificates/cert-123/signed-certificate.json \
     --region $PRIMARY_REGION
   ```

2. **Check Filters**: Verify replication rules don't exclude the object
3. **Check Timing**: Allow sufficient time for replication to complete

## References

- [AWS S3 Replication Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html)
- [AWS Multi-Region Best Practices](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/disaster-recovery-options-in-the-cloud.html)
- Rosetta Zero Requirements: 27.1, 27.2, 27.3
