# Rosetta Zero - Deployment Guide

This guide provides comprehensive instructions for deploying Rosetta Zero infrastructure using AWS CDK with support for multiple environments (dev, staging, prod).

**Requirements:** 23.1, 23.2

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Deployment Methods](#deployment-methods)
4. [Common Operations](#common-operations)
5. [Multi-Region Deployment](#multi-region-deployment)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.12+**: Required for CDK application and Lambda runtime
- **Node.js 18+**: Required for AWS CDK CLI
- **AWS CDK CLI**: Install with `npm install -g aws-cdk`
- **AWS CLI v2**: Configured with appropriate credentials
- **Docker**: Required for building Lambda container images (optional)
- **Git**: For version control

### AWS Account Prerequisites

#### Account Requirements

1. **AWS Account ID**: Your 12-digit AWS account number
2. **AWS Region**: Supported regions:
   - `us-east-1` (US East - N. Virginia)
   - `us-east-2` (US East - Ohio)
   - `us-west-1` (US West - N. California)
   - `us-west-2` (US West - Oregon)
   - `eu-west-1` (Europe - Ireland)
   - `eu-central-1` (Europe - Frankfurt)
   - `ap-southeast-1` (Asia Pacific - Singapore)
   - `ap-northeast-1` (Asia Pacific - Tokyo)

3. **AWS Credentials**: Configure via one of:
   - AWS CLI: `aws configure`
   - Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - IAM role (recommended for EC2/ECS)
   - AWS SSO

#### IAM Permissions Required

The deploying user/role needs the following permissions:

**CloudFormation**:
- `cloudformation:CreateStack`
- `cloudformation:UpdateStack`
- `cloudformation:DeleteStack`
- `cloudformation:DescribeStacks`
- `cloudformation:DescribeStackEvents`

**IAM**:
- `iam:CreateRole`
- `iam:AttachRolePolicy`
- `iam:PutRolePolicy`
- `iam:PassRole`
- `iam:GetRole`
- `iam:DeleteRole`

**S3**:
- `s3:CreateBucket`
- `s3:PutBucketPolicy`
- `s3:PutBucketVersioning`
- `s3:PutEncryptionConfiguration`
- `s3:PutBucketReplication`

**Lambda**:
- `lambda:CreateFunction`
- `lambda:UpdateFunctionCode`
- `lambda:UpdateFunctionConfiguration`
- `lambda:DeleteFunction`
- `lambda:PublishVersion`

**DynamoDB**:
- `dynamodb:CreateTable`
- `dynamodb:UpdateTable`
- `dynamodb:DeleteTable`
- `dynamodb:DescribeTable`

**KMS**:
- `kms:CreateKey`
- `kms:CreateAlias`
- `kms:DescribeKey`
- `kms:EnableKeyRotation`
- `kms:PutKeyPolicy`

**VPC**:
- `ec2:CreateVpc`
- `ec2:CreateSubnet`
- `ec2:CreateSecurityGroup`
- `ec2:CreateVpcEndpoint`

**Step Functions**:
- `states:CreateStateMachine`
- `states:UpdateStateMachine`
- `states:DeleteStateMachine`

**ECS/Fargate**:
- `ecs:CreateCluster`
- `ecs:RegisterTaskDefinition`
- `ecs:DeregisterTaskDefinition`

**EventBridge**:
- `events:PutRule`
- `events:PutTargets`
- `events:DeleteRule`

**SNS**:
- `sns:CreateTopic`
- `sns:Subscribe`
- `sns:SetTopicAttributes`

**CloudWatch**:
- `logs:CreateLogGroup`
- `logs:PutRetentionPolicy`
- `cloudwatch:PutDashboard`
- `cloudwatch:PutMetricAlarm`

**Bedrock** (for runtime, not deployment):
- `bedrock:InvokeModel`
- `bedrock:Retrieve`

**Macie** (for runtime, not deployment):
- `macie2:CreateClassificationJob`
- `macie2:DescribeClassificationJob`

#### Service Quotas to Check

Before deployment, verify these service quotas are sufficient:

```bash
# Check Lambda concurrent executions quota
aws service-quotas get-service-quota \
  --service-code lambda \
  --quota-code L-B99A9384

# Check VPC quota
aws service-quotas get-service-quota \
  --service-code vpc \
  --quota-code L-F678F1CE

# Check S3 buckets quota
aws service-quotas get-service-quota \
  --service-code s3 \
  --quota-code L-DC2B2D3D

# Check DynamoDB tables quota
aws service-quotas get-service-quota \
  --service-code dynamodb \
  --quota-code L-F98FE922
```

**Recommended Quotas**:
- Lambda concurrent executions: 1000+ (default is 1000)
- VPCs per region: 5+ (default is 5)
- S3 buckets: 100+ (default is 100)
- DynamoDB tables: 256+ (default is 256)

#### Bedrock Model Access

Request access to required Bedrock models:

1. Navigate to AWS Console → Bedrock → Model access
2. Request access to:
   - **Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
3. Wait for approval (typically instant, but can take up to 24 hours)

```bash
# Verify model access
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?modelId==`anthropic.claude-3-5-sonnet-20241022-v2:0`]'
```

#### Cost Estimation

Estimated monthly costs for Rosetta Zero (varies by usage):

| Component | Development | Staging | Production |
|-----------|-------------|---------|------------|
| Lambda | $50-100 | $200-500 | $1,000-5,000 |
| Bedrock | $100-500 | $500-2,000 | $5,000-20,000 |
| S3 | $10-50 | $50-200 | $200-1,000 |
| DynamoDB | $10-50 | $50-200 | $200-1,000 |
| Fargate | $50-200 | $200-1,000 | $1,000-5,000 |
| Step Functions | $10-50 | $50-200 | $200-1,000 |
| Data Transfer | $10-50 | $50-200 | $200-1,000 |
| **Total** | **$240-1,000** | **$1,100-4,300** | **$8,000-34,000** |

**Note**: Bedrock costs dominate due to LLM usage. Costs scale with number of legacy artifacts processed.

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/rosetta-zero.git
cd rosetta-zero

# Install Python dependencies
pip install -r requirements.txt

# Install CDK CLI globally
npm install -g aws-cdk

# Verify installations
python3 --version  # Should be 3.12+
node --version     # Should be 18+
cdk --version      # Should be 2.x
aws --version      # Should be 2.x

# Configure AWS credentials
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region, Output format

# Verify AWS credentials
aws sts get-caller-identity
```

## Environment Configuration

Rosetta Zero supports three environments with different configurations:

### Development (dev)

- **Purpose**: Development and testing
- **Log Retention**: 7 days
- **Deletion Protection**: Disabled
- **Termination Protection**: Disabled
- **Use Case**: Rapid iteration and testing

### Staging (staging)

- **Purpose**: Pre-production validation
- **Log Retention**: 30 days
- **Deletion Protection**: Enabled
- **Termination Protection**: Disabled
- **Use Case**: Integration testing and validation

### Production (prod)

- **Purpose**: Production workloads
- **Log Retention**: 2555 days (7 years for compliance)
- **Deletion Protection**: Enabled
- **Termination Protection**: Enabled
- **Use Case**: Production deployments with full compliance

### Configuration Options

Rosetta Zero can be customized through the `cdk.context.json` file or environment variables.

#### Core Configuration

```json
{
  "environment": "dev",
  "region": "us-east-1",
  "account": "123456789012",
  "logRetentionDays": 7,
  "enableDeletionProtection": false,
  "enableTerminationProtection": false
}
```

#### Advanced Configuration Options

**Bedrock Configuration**:
```json
{
  "bedrockModelId": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "bedrockMaxTokens": 100000,
  "bedrockTemperature": 0.0
}
```

**Test Generation Configuration**:
```json
{
  "testVectorCount": 1000000,
  "targetBranchCoverage": 0.95,
  "randomSeed": null,
  "enablePropertyBasedTesting": true
}
```

**Lambda Configuration**:
```json
{
  "lambdaTimeout": 900,
  "lambdaMemorySize": 3008,
  "lambdaRuntime": "python3.12",
  "enableXRayTracing": true
}
```

**Fargate Configuration**:
```json
{
  "fargateTaskCpu": 2048,
  "fargateTaskMemory": 4096,
  "fargateEnableContainerInsights": true
}
```

**DynamoDB Configuration**:
```json
{
  "dynamodbBillingMode": "PAY_PER_REQUEST",
  "dynamodbPointInTimeRecovery": true,
  "dynamodbEnableStreams": false
}
```

**S3 Configuration**:
```json
{
  "s3VersioningEnabled": true,
  "s3LifecycleRules": {
    "tempObjectsExpirationDays": 30,
    "oldVersionsExpirationDays": 90
  },
  "s3IntelligentTiering": true
}
```

**Retry Configuration**:
```json
{
  "maxRetries": 3,
  "retryBackoffBase": 2,
  "retryMaxDelay": 60
}
```

**Monitoring Configuration**:
```json
{
  "enableDetailedMonitoring": true,
  "alarmEmailEndpoints": ["operator@example.com"],
  "alarmSmsEndpoints": ["+1234567890"],
  "createCloudWatchDashboard": true
}
```

**Security Configuration**:
```json
{
  "enableKmsEncryption": true,
  "kmsKeyRotation": true,
  "enableVpcEndpoints": true,
  "enablePrivateLink": true,
  "enableMaciePiiScanning": true
}
```

**Multi-Region Configuration**:
```json
{
  "enableMultiRegion": true,
  "replicaRegion": "us-west-2",
  "enableCrossRegionReplication": true
}
```

#### Environment-Specific Overrides

You can override configuration per environment:

```json
{
  "environment": "prod",
  "region": "us-east-1",
  "account": "123456789012",
  
  "dev": {
    "logRetentionDays": 7,
    "enableDeletionProtection": false,
    "lambdaMemorySize": 1024,
    "testVectorCount": 10000
  },
  
  "staging": {
    "logRetentionDays": 30,
    "enableDeletionProtection": true,
    "lambdaMemorySize": 3008,
    "testVectorCount": 100000
  },
  
  "prod": {
    "logRetentionDays": 2555,
    "enableDeletionProtection": true,
    "enableTerminationProtection": true,
    "lambdaMemorySize": 10240,
    "testVectorCount": 1000000,
    "enableMultiRegion": true,
    "alarmEmailEndpoints": ["oncall@example.com", "manager@example.com"]
  }
}
```

#### Configuration Validation

The deployment script validates all configuration before deployment:

```bash
# Validate configuration
python3 scripts/deploy.py validate \
  --env prod \
  --region us-east-1 \
  --account 123456789012

# Output:
# ✓ Environment 'prod' is valid
# ✓ Region 'us-east-1' is valid
# ✓ Account ID '123456789012' is valid (12 digits)
# ✓ Log retention days: 2555 (valid range: 1-3653)
# ✓ Lambda memory size: 10240 MB (valid range: 128-10240)
# ✓ Test vector count: 1000000 (valid range: 1000-10000000)
# ✓ All configuration options are valid
```

#### Using Environment Variables

You can also configure via environment variables (overrides `cdk.context.json`):

```bash
# Core settings
export ROSETTA_ZERO_ENV=prod
export ROSETTA_ZERO_REGION=us-east-1
export ROSETTA_ZERO_ACCOUNT=123456789012

# Bedrock settings
export ROSETTA_ZERO_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export ROSETTA_ZERO_BEDROCK_MAX_TOKENS=100000

# Test generation settings
export ROSETTA_ZERO_TEST_VECTOR_COUNT=1000000
export ROSETTA_ZERO_TARGET_BRANCH_COVERAGE=0.95

# Lambda settings
export ROSETTA_ZERO_LAMBDA_TIMEOUT=900
export ROSETTA_ZERO_LAMBDA_MEMORY_SIZE=10240

# Deploy with environment variables
python3 scripts/deploy.py deploy
```

#### Configuration Best Practices

1. **Development**:
   - Use minimal resources to reduce costs
   - Short log retention (7 days)
   - Disable deletion protection for easy cleanup
   - Reduce test vector count for faster iteration

2. **Staging**:
   - Mirror production configuration
   - Enable deletion protection
   - Use realistic test vector counts
   - Enable detailed monitoring

3. **Production**:
   - Maximum log retention (7 years for compliance)
   - Enable all protection mechanisms
   - Full test vector count (1M+)
   - Enable multi-region replication
   - Configure multiple alarm endpoints
   - Enable all security features

4. **Security**:
   - Always enable KMS encryption
   - Always enable VPC endpoints
   - Always enable Macie PII scanning
   - Never disable SSL/TLS
   - Use least-privilege IAM policies

5. **Cost Optimization**:
   - Use on-demand billing for DynamoDB in dev/staging
   - Use provisioned capacity in production if usage is predictable
   - Enable S3 Intelligent-Tiering
   - Set lifecycle rules for temporary objects
   - Destroy dev environments when not in use

## Deployment Methods

### Method 1: Using Python Script (Recommended)

The Python deployment script provides parameter validation and environment-specific configuration.

#### Bootstrap CDK (First Time Only)

```bash
python3 scripts/deploy.py bootstrap \
  --region us-east-1 \
  --account 123456789012
```

#### Synthesize CloudFormation Templates

```bash
# Development
python3 scripts/deploy.py synth \
  --env dev \
  --region us-east-1 \
  --account 123456789012

# Staging
python3 scripts/deploy.py synth \
  --env staging \
  --region us-east-1 \
  --account 123456789012

# Production
python3 scripts/deploy.py synth \
  --env prod \
  --region us-east-1 \
  --account 123456789012
```

#### Deploy Infrastructure

```bash
# Development
python3 scripts/deploy.py deploy \
  --env dev \
  --region us-east-1 \
  --account 123456789012

# Staging
python3 scripts/deploy.py deploy \
  --env staging \
  --region us-east-1 \
  --account 123456789012

# Production (requires approval)
python3 scripts/deploy.py deploy \
  --env prod \
  --region us-east-1 \
  --account 123456789012
```

#### Deploy Specific Stack

```bash
# Deploy only the main stack
python3 scripts/deploy.py deploy \
  --env dev \
  --region us-east-1 \
  --account 123456789012 \
  --stack RosettaZeroStack-dev

# Deploy only the replica bucket stack
python3 scripts/deploy.py deploy \
  --env dev \
  --region us-east-1 \
  --account 123456789012 \
  --stack CertificatesReplicaBucketStack-dev
```

#### Show Infrastructure Differences

```bash
python3 scripts/deploy.py diff \
  --env dev \
  --region us-east-1 \
  --account 123456789012
```

#### Destroy Infrastructure

```bash
# Development (requires confirmation)
python3 scripts/deploy.py destroy \
  --env dev \
  --region us-east-1 \
  --account 123456789012

# Production (requires typing 'destroy-production')
python3 scripts/deploy.py destroy \
  --env prod \
  --region us-east-1 \
  --account 123456789012
```

### Method 2: Using Shell Scripts

Convenient wrapper scripts for Unix/Linux/macOS and Windows.

#### Unix/Linux/macOS

```bash
# Make script executable
chmod +x scripts/deploy.sh

# Deploy to dev
./scripts/deploy.sh deploy --env dev --region us-east-1 --account 123456789012
```

#### Windows (PowerShell)

```powershell
# Deploy to dev
.\scripts\deploy.ps1 deploy --env dev --region us-east-1 --account 123456789012
```

### Method 3: Using Makefile

Convenient targets for common operations.

```bash
# Show available commands
make help

# Bootstrap CDK
make bootstrap REGION=us-east-1 ACCOUNT=123456789012

# Deploy to development
make deploy-dev REGION=us-east-1 ACCOUNT=123456789012

# Deploy to staging
make deploy-staging REGION=us-east-1 ACCOUNT=123456789012

# Deploy to production
make deploy-prod REGION=us-east-1 ACCOUNT=123456789012

# Deploy specific stack
make deploy-dev REGION=us-east-1 ACCOUNT=123456789012 STACK=RosettaZeroStack-dev

# Show differences
make diff-dev REGION=us-east-1 ACCOUNT=123456789012

# Destroy infrastructure
make destroy-dev REGION=us-east-1 ACCOUNT=123456789012
```

### Method 4: Direct CDK Commands

For advanced users who want direct control.

```bash
# Update context manually
cat > cdk.context.json << EOF
{
  "environment": "dev",
  "region": "us-east-1",
  "account": "123456789012"
}
EOF

# Run CDK commands
cdk synth
cdk deploy
cdk diff
cdk destroy
```

## Common Operations

### Viewing Deployed Resources

```bash
# List all stacks
cdk list

# Show stack outputs
aws cloudformation describe-stacks \
  --stack-name RosettaZeroStack-dev \
  --query 'Stacks[0].Outputs'
```

### Updating Configuration

The deployment script automatically updates `cdk.context.json` with environment-specific settings. You can also manually edit this file:

```json
{
  "environment": "dev",
  "region": "us-east-1",
  "account": "123456789012",
  "logRetentionDays": 7,
  "enableDeletionProtection": false,
  "enableTerminationProtection": false
}
```

### Hotswap Deployments (Dev Only)

For faster iteration during development, use hotswap deployments:

```bash
python3 scripts/deploy.py deploy \
  --env dev \
  --region us-east-1 \
  --account 123456789012 \
  --hotswap
```

**Warning**: Hotswap deployments bypass CloudFormation and should only be used in development.

### Skip Approval Prompts

For CI/CD pipelines, skip manual approval:

```bash
python3 scripts/deploy.py deploy \
  --env dev \
  --region us-east-1 \
  --account 123456789012 \
  --no-approval
```

## Multi-Region Deployment

Rosetta Zero automatically deploys a replica bucket in a secondary region for disaster recovery.

### Region Pairs

| Primary Region | Secondary Region |
|----------------|------------------|
| us-east-1      | us-west-2        |
| us-west-2      | us-east-1        |
| eu-west-1      | eu-central-1     |
| eu-central-1   | eu-west-1        |
| ap-southeast-1 | ap-northeast-1   |
| ap-northeast-1 | ap-southeast-1   |

### Deployment Order

1. **Deploy Replica Bucket Stack** (Secondary Region)
   ```bash
   python3 scripts/deploy.py deploy \
     --env prod \
     --region us-east-1 \
     --account 123456789012 \
     --stack CertificatesReplicaBucketStack-prod
   ```

2. **Deploy Main Stack** (Primary Region)
   ```bash
   python3 scripts/deploy.py deploy \
     --env prod \
     --region us-east-1 \
     --account 123456789012 \
     --stack RosettaZeroStack-prod
   ```

Or deploy both stacks together:

```bash
python3 scripts/deploy.py deploy \
  --env prod \
  --region us-east-1 \
  --account 123456789012
```

## Troubleshooting

### Parameter Validation Errors

The deployment script validates all parameters before deployment:

```
❌ Parameter validation failed:
  - Invalid environment 'test'. Must be one of: dev, staging, prod
  - Invalid region 'us-east-3'. Must be one of: us-east-1, us-east-2, ...
  - Invalid account ID '12345'. Must be 12 digits.
```

**Solution**: Correct the parameters according to the error messages.

### CDK Bootstrap Required

```
Error: This stack uses assets, so the toolkit stack must be deployed to the environment
```

**Solution**: Bootstrap CDK in the target account/region:

```bash
python3 scripts/deploy.py bootstrap \
  --region us-east-1 \
  --account 123456789012
```

### Insufficient IAM Permissions

```
Error: User is not authorized to perform: cloudformation:CreateStack
```

**Solution**: Ensure your AWS credentials have sufficient permissions. CDK requires:
- CloudFormation full access
- IAM role creation
- Service-specific permissions (S3, Lambda, DynamoDB, etc.)

See [IAM Permissions Required](#iam-permissions-required) section for complete list.

### Stack Already Exists

```
Error: Stack [RosettaZeroStack-dev] already exists
```

**Solution**: Use `cdk deploy` to update the existing stack, or `cdk destroy` to remove it first.

### Resource Retention

Some resources (KMS keys, S3 buckets with data) have `RemovalPolicy.RETAIN` and won't be deleted by `cdk destroy`.

**Solution**: Manually delete retained resources after destroying the stack:

```bash
# List retained S3 buckets
aws s3 ls | grep rosetta-zero

# Delete bucket (after emptying)
aws s3 rb s3://rosetta-zero-legacy-artifacts-dev --force

# Schedule KMS key deletion
aws kms schedule-key-deletion --key-id <key-id> --pending-window-in-days 7
```

### Production Destruction Protection

```
Destruction cancelled
```

**Solution**: For production, you must type `destroy-production` to confirm:

```bash
python3 scripts/deploy.py destroy \
  --env prod \
  --region us-east-1 \
  --account 123456789012
# Type: destroy-production
```

Or use `--force` flag (not recommended):

```bash
python3 scripts/deploy.py destroy \
  --env prod \
  --region us-east-1 \
  --account 123456789012 \
  --force
```

### Bedrock Model Access Denied

```
Error: AccessDeniedException: You don't have access to the model
```

**Solution**: Request model access in Bedrock console:

1. Navigate to AWS Console → Bedrock → Model access
2. Request access to Claude 3.5 Sonnet v2
3. Wait for approval (typically instant)

```bash
# Verify model access
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?modelId==`anthropic.claude-3-5-sonnet-20241022-v2:0`]'
```

### Service Quota Exceeded

```
Error: LimitExceededException: You have exceeded the maximum number of VPCs
```

**Solution**: Request service quota increase:

```bash
# Check current quota
aws service-quotas get-service-quota \
  --service-code vpc \
  --quota-code L-F678F1CE

# Request increase
aws service-quotas request-service-quota-increase \
  --service-code vpc \
  --quota-code L-F678F1CE \
  --desired-value 10
```

### CDK Synthesis Errors

```
Error: Synthesis failed
```

**Solution**: Check for errors in CDK code:

```bash
# Run synthesis with verbose output
cdk synth --verbose

# Check for Python syntax errors
python3 -m py_compile infrastructure/app.py

# Validate CDK context
cat cdk.context.json | jq .
```

### Deployment Timeout

```
Error: Stack deployment timed out
```

**Solution**: Increase timeout or check CloudFormation events:

```bash
# Check CloudFormation events
aws cloudformation describe-stack-events \
  --stack-name RosettaZeroStack-dev \
  --max-items 20

# Identify stuck resources
aws cloudformation list-stack-resources \
  --stack-name RosettaZeroStack-dev \
  --query 'StackResourceSummaries[?ResourceStatus==`CREATE_IN_PROGRESS`]'
```

### VPC Endpoint Creation Failed

```
Error: VPC endpoint creation failed
```

**Solution**: Check VPC endpoint service availability:

```bash
# List available VPC endpoint services
aws ec2 describe-vpc-endpoint-services \
  --region us-east-1 \
  --query 'ServiceNames[?contains(@, `bedrock`)]'

# Verify service is available in region
aws ec2 describe-vpc-endpoint-services \
  --region us-east-1 \
  --service-names com.amazonaws.us-east-1.bedrock
```

### Lambda Function Creation Failed

```
Error: Lambda function creation failed: Code size exceeds maximum
```

**Solution**: Optimize Lambda deployment package:

```bash
# Check package size
du -sh lambda/*/

# Remove unnecessary dependencies
pip install --target lambda/ingestion/ -r requirements-minimal.txt

# Use Lambda layers for common dependencies
cdk deploy --context useLambdaLayers=true
```

### DynamoDB Table Creation Failed

```
Error: Table already exists
```

**Solution**: Delete existing table or use different table name:

```bash
# Check if table exists
aws dynamodb describe-table \
  --table-name rosetta-zero-test-results

# Delete table (if safe to do so)
aws dynamodb delete-table \
  --table-name rosetta-zero-test-results

# Wait for deletion
aws dynamodb wait table-not-exists \
  --table-name rosetta-zero-test-results
```

### Cross-Region Replication Failed

```
Error: Replication configuration failed
```

**Solution**: Verify replica bucket exists and has correct permissions:

```bash
# Check replica bucket
aws s3 ls s3://rosetta-zero-certificates-replica-us-west-2/

# Verify replication role
aws iam get-role \
  --role-name rosetta-zero-replication-role

# Check replication status
aws s3api get-bucket-replication \
  --bucket rosetta-zero-certificates
```

## Monitoring and Operations

After successful deployment, refer to the [Operations Guide](./operations-guide.md) for:

- **Monitoring and Alerting**: CloudWatch dashboards, SNS notifications, alarms
- **Operator Intervention Procedures**: When and how to intervene
- **AWS 500-Level Error Handling**: Detailed procedures for handling AWS service errors
- **Troubleshooting Common Issues**: Runtime issues and their solutions
- **Incident Response**: Incident management workflows
- **Maintenance Procedures**: Routine maintenance tasks

### Quick Health Check

After deployment, verify system health:

```bash
# Check Lambda functions
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `rosetta-zero`)].[FunctionName, State, LastModified]' \
  --output table

# Check Step Functions state machines
aws stepfunctions list-state-machines \
  --query 'stateMachines[?contains(name, `rosetta-zero`)].[name, status, creationDate]' \
  --output table

# Check DynamoDB tables
aws dynamodb list-tables \
  --query 'TableNames[?contains(@, `rosetta-zero`)]' \
  --output table

# Check S3 buckets
aws s3 ls | grep rosetta-zero

# Check VPC
aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=RosettaZeroVPC*" \
  --query 'Vpcs[].[VpcId, State, Tags[?Key==`Name`].Value | [0]]' \
  --output table

# Check CloudWatch log groups
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/rosetta-zero \
  --query 'logGroups[].[logGroupName, retentionInDays]' \
  --output table

# Check SNS topics
aws sns list-topics \
  --query 'Topics[?contains(TopicArn, `rosetta-zero`)]' \
  --output table

# Check EventBridge rules
aws events list-rules \
  --name-prefix rosetta-zero \
  --query 'Rules[].[Name, State, EventPattern]' \
  --output table
```

### Verify Deployment Outputs

```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name RosettaZeroStack-dev \
  --query 'Stacks[0].Outputs' \
  --output table

# Example outputs:
# - VpcId: vpc-xxxxx
# - IngestionEngineLambdaArn: arn:aws:lambda:...
# - TestResultsTableName: rosetta-zero-test-results
# - CertificatesBucketName: rosetta-zero-certificates-dev
# - OperatorNotificationTopicArn: arn:aws:sns:...
```

### Test Basic Functionality

```bash
# Test Ingestion Engine Lambda
aws lambda invoke \
  --function-name rosetta-zero-ingestion-engine \
  --payload '{"test": true}' \
  --cli-binary-format raw-in-base64-out \
  response.json

cat response.json

# Check CloudWatch Logs
aws logs tail /aws/lambda/rosetta-zero-ingestion-engine --follow

# Test SNS notifications
aws sns publish \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:rosetta-zero-operator-notifications \
  --subject "Test Notification" \
  --message "This is a test notification from Rosetta Zero deployment"
```

## Best Practices

### Development Workflow

1. **Synthesize First**: Always run `synth` to check for errors
2. **Review Diff**: Use `diff` to see what will change
3. **Deploy to Dev**: Test changes in dev environment first
4. **Validate**: Run integration tests
5. **Deploy to Staging**: Validate in staging environment
6. **Deploy to Prod**: Deploy to production with approval

### CI/CD Integration

```bash
# In CI/CD pipeline
python3 scripts/deploy.py synth --env staging --region us-east-1 --account 123456789012
python3 scripts/deploy.py deploy --env staging --region us-east-1 --account 123456789012 --no-approval
```

### Cost Management

- **Dev**: Destroy when not in use to save costs
- **Staging**: Keep running for continuous testing
- **Prod**: Always running with full compliance

### Security

- **Never commit** `cdk.context.json` with real account IDs to version control
- **Use IAM roles** for CI/CD instead of access keys
- **Enable MFA** for production deployments
- **Review changes** before deploying to production

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Rosetta Zero Architecture](../README.md)
- [Multi-Region Deployment Guide](./multi-region-deployment.md)
- [DEPLOYMENT.md](../DEPLOYMENT.md)
