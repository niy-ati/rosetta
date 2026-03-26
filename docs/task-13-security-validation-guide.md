# Task 13: Security Hardening and Final Validation Guide

## Overview

This document provides comprehensive guidance for executing Task 13 of the Rosetta Zero implementation plan: Security hardening and final validation. This task ensures that all security controls are properly configured and the system meets all 30 requirements.

## Validation Scripts

Task 13 includes six validation scripts that verify different aspects of the system's security and compliance:

### 1. Security Best Practices Validation (`security_validation.py`)

**Purpose**: Validates AWS security best practices are implemented correctly.

**Checks**:
- ✓ All S3 buckets have public access blocked
- ✓ All S3 buckets use KMS encryption
- ✓ All DynamoDB tables use KMS encryption
- ✓ All CloudWatch Logs use KMS encryption
- ✓ VPC has no internet gateway
- ✓ VPC has no NAT gateway
- ✓ All Lambda functions use VPC configuration

**Usage**:
```bash
python scripts/security_validation.py --stack-name RosettaZeroStack-dev
```

**Requirements Validated**: 21.1, 21.2, 21.3, 21.4, 21.5

---

### 2. IAM Policy Validation (`iam_policy_validation.py`)

**Purpose**: Validates IAM policies follow least-privilege principle.

**Checks**:
- ✓ No wildcard permissions except where required
- ✓ No overly broad resource access
- ✓ No overly permissive principals
- ✓ IAM Access Analyzer findings reviewed

**Acceptable Wildcard Actions**:
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
- `kms:Decrypt`, `kms:Encrypt`, `kms:GenerateDataKey`
- `ec2:CreateNetworkInterface`, `ec2:DescribeNetworkInterfaces`, `ec2:DeleteNetworkInterface`

**Usage**:
```bash
python scripts/iam_policy_validation.py --stack-name RosettaZeroStack-dev
```

**Requirements Validated**: 21.1, 21.2

---

### 3. PII Data Scrubbing Validation (`pii_validation.py`)

**Purpose**: Validates PII detection and scrubbing functionality.

**Checks**:
- ✓ PII detection works correctly (SSN, email, phone, credit card, names)
- ✓ PII is properly redacted before analysis
- ✓ PII is replaced with synthetic data in test vectors
- ✓ PII detection events are logged to CloudWatch
- ✓ Amazon Macie is configured

**PII Types Detected**:
- Social Security Numbers (SSN): `123-45-6789`
- Email addresses: `user@example.com`
- Phone numbers: `555-123-4567`
- Credit card numbers: `4532-1234-5678-9010`
- Names: `John Smith`

**Usage**:
```bash
python scripts/pii_validation.py --stack-name RosettaZeroStack-dev
```

**Requirements Validated**: 20.1, 20.2, 20.3, 20.4, 20.5

---

### 4. Cryptographic Implementation Validation (`crypto_validation.py`)

**Purpose**: Validates cryptographic implementations use correct algorithms.

**Checks**:
- ✓ Symmetric KMS keys use AES-256 (SYMMETRIC_DEFAULT)
- ✓ Asymmetric KMS keys use RSA-4096
- ✓ Certificate signatures use RSASSA-PSS-SHA-256
- ✓ All hashes use SHA-256
- ✓ Signature verification works correctly

**Usage**:
```bash
python scripts/crypto_validation.py --stack-name RosettaZeroStack-dev
```

**Requirements Validated**: 16.1, 16.2, 16.3, 16.4, 17.7

---

### 5. Security Audit (`security_audit.py`)

**Purpose**: Performs comprehensive security audit using AWS services.

**Checks**:
- ✓ AWS Security Hub findings (HIGH and CRITICAL)
- ✓ AWS Inspector Lambda function scans
- ✓ CloudTrail logs for suspicious activity
- ✓ Network isolation (no internet/NAT gateways, no 0.0.0.0/0 ingress)

**Suspicious Events Monitored**:
- DeleteBucket, DeleteTable, DeleteKey
- PutBucketPolicy, PutBucketAcl
- CreateAccessKey, DeleteAccessKey
- AttachUserPolicy, AttachRolePolicy

**Usage**:
```bash
python scripts/security_audit.py --stack-name RosettaZeroStack-dev --region us-east-1
```

**Requirements Validated**: 21.1, 21.2, 21.3, 21.4, 21.5

---

### 6. Complete System Validation (`system_validation.py`)

**Purpose**: Validates the complete system against all 30 requirements.

**Checks**:
- ✓ Legacy code ingestion infrastructure
- ✓ Test result storage with PITR
- ✓ Immutable audit logging (7-year retention)
- ✓ Secure data transit
- ✓ Monitoring and logging operational
- ✓ All security controls in place

**Usage**:
```bash
python scripts/system_validation.py --stack-name RosettaZeroStack-dev
```

**Requirements Validated**: All 30 requirements (summary)

---

## Master Validation Script

The `run_all_validations.py` script runs all validation scripts in sequence:

```bash
python scripts/run_all_validations.py --stack-name RosettaZeroStack-dev
```

**Options**:
- `--skip-security`: Skip security best practices validation
- `--skip-iam`: Skip IAM policy validation
- `--skip-pii`: Skip PII validation
- `--skip-crypto`: Skip cryptographic validation
- `--skip-audit`: Skip security audit

**Example - Skip optional checks**:
```bash
python scripts/run_all_validations.py --skip-audit --skip-pii
```

---

## Validation Workflow

### Step 1: Deploy to Staging Environment

```bash
# Deploy the stack
cdk deploy RosettaZeroStack-dev --require-approval never

# Wait for deployment to complete
aws cloudformation wait stack-create-complete --stack-name RosettaZeroStack-dev
```

### Step 2: Run Security Validations

```bash
# Run all validations
python scripts/run_all_validations.py --stack-name RosettaZeroStack-dev

# Or run individually
python scripts/security_validation.py --stack-name RosettaZeroStack-dev
python scripts/iam_policy_validation.py --stack-name RosettaZeroStack-dev
python scripts/pii_validation.py --stack-name RosettaZeroStack-dev
python scripts/crypto_validation.py --stack-name RosettaZeroStack-dev
python scripts/security_audit.py --stack-name RosettaZeroStack-dev
```

### Step 3: Run End-to-End Tests

```bash
# Run complete end-to-end test suite
pytest tests/test_e2e_sample_artifacts.py -v

# Run integration tests
pytest tests/test_verification_integration.py -v
pytest tests/test_workflow_orchestration_integration.py -v
```

### Step 4: Verify All Requirements

```bash
# Run system validation
python scripts/system_validation.py --stack-name RosettaZeroStack-dev
```

### Step 5: Generate Compliance Report

```bash
# Generate compliance report (if compliance reporter is deployed)
aws lambda invoke \
  --function-name RosettaZeroStack-dev-compliance-reporter \
  --payload '{"workflow_id": "validation-test"}' \
  response.json

# View report
cat response.json
```

---

## Expected Results

### All Validations Should Pass

When the system is properly configured, all validation scripts should report:

```
================================================================================
  ✓ ALL VALIDATIONS PASSED
================================================================================
```

### Common Issues and Resolutions

#### Issue: S3 Bucket Public Access Not Blocked

**Error**: `Public access not fully blocked for bucket X`

**Resolution**:
```bash
aws s3api put-public-access-block \
  --bucket BUCKET_NAME \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

#### Issue: CloudWatch Logs Not Encrypted

**Error**: `Log group X does not use KMS encryption`

**Resolution**: Update CDK stack to add KMS encryption to log groups.

#### Issue: IAM Policy Too Permissive

**Error**: `Action '*' grants all permissions`

**Resolution**: Update IAM policies to use specific actions instead of wildcards.

#### Issue: VPC Has Internet Gateway

**Error**: `VPC X has internet gateway attached`

**Resolution**: Remove internet gateway from VPC (ensure VPC endpoints are configured).

---

## Security Controls Checklist

Use this checklist to verify all security controls are in place:

### Data Encryption
- [ ] All S3 buckets use KMS encryption
- [ ] All DynamoDB tables use KMS encryption
- [ ] All CloudWatch Logs use KMS encryption
- [ ] All data in transit uses TLS 1.3

### Network Security
- [ ] VPC has no internet gateway
- [ ] VPC has no NAT gateway
- [ ] All Lambda functions use VPC configuration
- [ ] VPC endpoints configured for all AWS services
- [ ] Security groups follow least-privilege

### Access Control
- [ ] IAM policies follow least-privilege principle
- [ ] No wildcard permissions except where required
- [ ] IAM Access Analyzer shows no findings
- [ ] All resources have appropriate resource policies

### Audit and Compliance
- [ ] CloudWatch Logs configured with 7-year retention
- [ ] All API calls logged to CloudTrail
- [ ] PII detection and redaction working
- [ ] Test results stored with PITR enabled
- [ ] Cryptographic signatures use correct algorithms

### Monitoring
- [ ] CloudWatch dashboards created
- [ ] EventBridge rules configured
- [ ] SNS notifications set up for critical events
- [ ] Security Hub enabled and monitored
- [ ] Inspector scans configured for Lambda functions

---

## Troubleshooting

### Validation Script Fails to Run

**Symptom**: Script exits with import errors

**Resolution**:
```bash
# Install required dependencies
pip install -r requirements.txt

# Ensure boto3 is up to date
pip install --upgrade boto3
```

### AWS Credentials Not Found

**Symptom**: `Unable to locate credentials`

**Resolution**:
```bash
# Configure AWS credentials
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### Stack Not Found

**Symptom**: `Stack RosettaZeroStack-dev does not exist`

**Resolution**:
```bash
# List available stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Use correct stack name
python scripts/security_validation.py --stack-name YOUR_STACK_NAME
```

---

## Continuous Validation

### Automated Validation in CI/CD

Add validation scripts to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
name: Security Validation
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run validations
        run: python scripts/run_all_validations.py
```

### Scheduled Validation

Run validations on a schedule using AWS EventBridge:

```python
# Create EventBridge rule to run validations daily
rule = events.Rule(
    self, "DailyValidation",
    schedule=events.Schedule.cron(hour="2", minute="0"),
    targets=[targets.LambdaFunction(validation_function)]
)
```

---

## Compliance Reporting

### Generate Compliance Report

The system validation results can be used to generate compliance reports for auditors:

```bash
# Run all validations and save results
python scripts/run_all_validations.py > validation_results.txt

# Generate compliance report
python scripts/system_validation.py > compliance_report.txt
```

### Compliance Report Contents

A complete compliance report should include:

1. **Executive Summary**: Pass/fail status for all validations
2. **Security Controls**: Detailed results from security_validation.py
3. **IAM Policies**: Results from iam_policy_validation.py
4. **PII Protection**: Results from pii_validation.py
5. **Cryptography**: Results from crypto_validation.py
6. **Security Audit**: Results from security_audit.py
7. **System Validation**: Results from system_validation.py
8. **Test Results**: End-to-end test results
9. **Recommendations**: Any issues found and remediation steps

---

## Next Steps

After completing Task 13:

1. **Review Results**: Ensure all validations pass
2. **Address Issues**: Fix any failures found by validation scripts
3. **Document Findings**: Create compliance report for auditors
4. **Deploy to Production**: If all validations pass, proceed with production deployment
5. **Continuous Monitoring**: Set up automated validation in CI/CD pipeline

---

## Support

For questions or issues with Task 13 validation:

1. Check the troubleshooting section above
2. Review the validation script source code in `scripts/`
3. Check CloudWatch Logs for detailed error messages
4. Review AWS service documentation for specific services

---

## Summary

Task 13 provides comprehensive security validation for Rosetta Zero:

- **6 validation scripts** covering all security aspects
- **Automated checks** for 30+ security controls
- **Compliance reporting** for regulatory requirements
- **Continuous validation** support for CI/CD pipelines

All validation scripts are designed to be:
- **Automated**: Run without manual intervention
- **Comprehensive**: Cover all security requirements
- **Actionable**: Provide clear error messages and remediation steps
- **Repeatable**: Can be run multiple times safely

By completing Task 13, you ensure that Rosetta Zero meets all security and compliance requirements for production deployment.
