# Certificate Generator Lambda

## Overview

The Certificate Generator Lambda implements the **Trust Phase** of the Rosetta Zero workflow. It generates cryptographically signed equivalence certificates when all test vectors pass, providing cryptographic proof of behavioral equivalence for regulatory compliance.

## Requirements

Implements requirements:
- **17.1-17.9**: Equivalence Certificate Generation
- **16.3-16.4**: Cryptographic Test Integrity
- **19.2-19.4**: Autonomous Operation and Error Handling
- **21.1-21.3**: Secure Data Transit
- **25.1-25.5**: Error Recovery

## Architecture

### Components

1. **handler.py**: Lambda handler with PowerTools decorators
2. **certificate_generation.py**: Certificate generation logic
3. **certificate_signing.py**: KMS-based cryptographic signing
4. **event_publisher.py**: EventBridge and SNS event publishing
5. **error_handler.py**: Error handling and operator alerts

### Workflow

```
1. Query all test results from DynamoDB
2. Verify all tests passed (no failures)
3. Compute SHA-256 hash of all test results
4. Collect individual test result hashes
5. Generate EquivalenceCertificate with metadata
6. Sign certificate with KMS asymmetric key (RSA-4096, RSASSA-PSS-SHA-256)
7. Store signed certificate in S3
8. Publish completion event to EventBridge
9. Send SNS notification to operators
```

## Input Event Structure

```json
{
  "workflow_id": "string",
  "legacy_artifact": {
    "identifier": "string",
    "version": "string",
    "sha256_hash": "string",
    "s3_location": "string",
    "creation_timestamp": "ISO8601"
  },
  "modern_implementation": {
    "identifier": "string",
    "version": "string",
    "sha256_hash": "string",
    "s3_location": "string",
    "creation_timestamp": "ISO8601"
  },
  "random_seed": 12345,
  "coverage_report": {
    "branch_coverage_percent": 95.5,
    "entry_points_covered": 10,
    "total_entry_points": 10,
    "uncovered_branches": []
  }
}
```

## Output Structure

```json
{
  "statusCode": 200,
  "certificate_id": "uuid",
  "s3_location": "s3://bucket/certificates/uuid/signed-certificate.json",
  "signature_valid": true,
  "total_test_vectors": 1000000,
  "test_results_hash": "sha256_hash"
}
```

## Certificate Structure

### EquivalenceCertificate

```json
{
  "certificate_id": "uuid",
  "generation_timestamp": "ISO8601",
  "legacy_artifact": {
    "identifier": "legacy-system-v1",
    "version": "1.0.0",
    "sha256_hash": "...",
    "s3_location": "s3://...",
    "creation_timestamp": "ISO8601"
  },
  "modern_implementation": {
    "identifier": "modern-lambda-v1",
    "version": "1.0.0",
    "sha256_hash": "...",
    "s3_location": "s3://...",
    "creation_timestamp": "ISO8601"
  },
  "total_test_vectors": 1000000,
  "test_execution_start": "ISO8601",
  "test_execution_end": "ISO8601",
  "test_results_hash": "sha256_hash_of_all_results",
  "individual_test_hashes": ["hash1", "hash2", ...],
  "random_seed": 12345,
  "coverage_report": {
    "branch_coverage_percent": 95.5,
    "entry_points_covered": 10,
    "total_entry_points": 10,
    "uncovered_branches": []
  }
}
```

### SignedCertificate

```json
{
  "certificate": { ... },
  "signature": "hex_encoded_signature",
  "signing_key_id": "arn:aws:kms:...",
  "signature_algorithm": "RSASSA_PSS_SHA_256",
  "signing_timestamp": "ISO8601"
}
```

## Cryptographic Signing

The certificate is signed using AWS KMS with:
- **Key Type**: Asymmetric RSA-4096
- **Algorithm**: RSASSA-PSS-SHA-256
- **Process**:
  1. Serialize certificate to canonical JSON (sorted keys)
  2. Compute SHA-256 hash of certificate bytes
  3. Sign hash with KMS
  4. Store signature with certificate

## Error Handling

### Error Types

1. **Validation Errors** (Permanent)
   - Failed tests detected
   - No test results found
   - Cannot generate certificate

2. **KMS Failures**
   - Transient: ThrottlingException, ServiceUnavailableException (retried)
   - Permanent: Key not found, access denied (operator alert)

3. **S3 Failures**
   - Transient: SlowDown, ServiceUnavailable (retried)
   - Permanent: Bucket not found, access denied (operator alert)

4. **DynamoDB Failures**
   - Transient: ProvisionedThroughputExceededException (retried)
   - Permanent: Table not found, access denied (operator alert)

5. **AWS 500-Level Errors**
   - Pause execution
   - Send operator alert via SNS
   - Require manual intervention

### Retry Strategy

- **Max Retries**: 3
- **Backoff**: Exponential (base 2 seconds)
- **Retry Sequence**: 2s, 4s, 8s

## IAM Permissions

### Required Permissions

- **DynamoDB**: `dynamodb:Scan` on test-results table
- **S3**: `s3:PutObject` on certificates bucket
- **KMS**: `kms:Sign`, `kms:Verify` on signing key
- **KMS**: `kms:Decrypt`, `kms:Encrypt` on encryption key
- **EventBridge**: `events:PutEvents` on default event bus
- **SNS**: `sns:Publish` on operator alerts topic
- **CloudWatch Logs**: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

## Environment Variables

- `TEST_RESULTS_TABLE`: DynamoDB table name for test results
- `CERTIFICATES_BUCKET`: S3 bucket for signed certificates
- `KMS_SIGNING_KEY_ID`: KMS key ID for certificate signing
- `EVENT_BUS_NAME`: EventBridge event bus name
- `SNS_TOPIC_ARN`: SNS topic ARN for operator notifications
- `POWERTOOLS_SERVICE_NAME`: Service name for PowerTools logging
- `POWERTOOLS_METRICS_NAMESPACE`: Namespace for CloudWatch metrics
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)

## CloudWatch Metrics

- `CertificateGenerated`: Count of successfully generated certificates
- `CertificateGenerationFailed`: Count of failed certificate generations

## CloudWatch Logs

All operations are logged with structured JSON including:
- Certificate ID
- Workflow ID
- Test results hash
- Total test vectors
- Coverage percentage
- Error details (if any)

## EventBridge Events

### Certificate Generation Completed

```json
{
  "Source": "rosetta-zero.certificate-generator",
  "DetailType": "Certificate Generation Completed",
  "Detail": {
    "certificate_id": "uuid",
    "s3_location": "s3://...",
    "workflow_id": "string",
    "timestamp": "ISO8601",
    "phase": "Trust",
    "status": "COMPLETED"
  }
}
```

## SNS Notifications

### Success Notification

```json
{
  "subject": "Rosetta Zero: Equivalence Certificate Generated",
  "certificate_id": "uuid",
  "s3_location": "s3://...",
  "workflow_id": "string",
  "timestamp": "ISO8601",
  "message": "Equivalence certificate {id} has been successfully generated..."
}
```

### Error Alerts

- AWS 500-Level Error
- KMS Failure
- S3 Failure
- DynamoDB Failure
- Validation Error

## Testing

Unit tests should cover:
- Certificate generation from test results
- KMS signing and verification
- Certificate storage in S3
- Event publishing to EventBridge and SNS
- Error handling for all failure scenarios

## Deployment

Deployed via AWS CDK as part of the RosettaZeroStack:
- VPC: Private isolated subnets
- Timeout: 15 minutes
- Memory: 3008 MB
- Log Retention: 7+ years (2555 days)
- Encryption: KMS customer-managed keys

## Compliance

- **Audit Trail**: All operations logged to CloudWatch with 7-year retention
- **Cryptographic Proof**: Certificates signed with RSA-4096 asymmetric keys
- **Immutability**: S3 versioning enabled for audit trail
- **Data Encryption**: All data encrypted at rest and in transit
