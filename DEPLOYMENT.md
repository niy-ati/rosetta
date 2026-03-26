# Rosetta Zero - Deployment Guide

This guide walks through deploying the Rosetta Zero AWS infrastructure using AWS CDK.

## Prerequisites

### Required Software
- **Python 3.12+**: [Download Python](https://www.python.org/downloads/)
- **Node.js 18+**: Required for AWS CDK CLI
- **AWS CDK CLI**: Install with `npm install -g aws-cdk`
- **AWS CLI**: [Install AWS CLI](https://aws.amazon.com/cli/)

### AWS Requirements
- AWS account with appropriate permissions
- AWS credentials configured (access key and secret key)
- Permissions to create: VPC, KMS keys, S3 buckets, DynamoDB tables, VPC endpoints

## Setup Steps

### 1. Clone and Navigate to Project
```bash
cd rosetta-zero
```

### 2. Run Setup Script

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows PowerShell:**
```powershell
.\setup.ps1
```

**Manual Setup (if scripts fail):**
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure AWS Credentials

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-east-1)
- Default output format (json)

### 4. Update Configuration

Edit `cdk.context.json` with your AWS account details:

```json
{
  "region": "us-east-1",
  "account": "YOUR_AWS_ACCOUNT_ID"
}
```

To find your AWS account ID:
```bash
aws sts get-caller-identity --query Account --output text
```

### 5. Bootstrap CDK (First Time Only)

Bootstrap CDK in your AWS account and region:

```bash
cdk bootstrap aws://YOUR_ACCOUNT_ID/YOUR_REGION
```

Example:
```bash
cdk bootstrap aws://123456789012/us-east-1
```

This creates the necessary S3 bucket and IAM roles for CDK deployments.

### 6. Synthesize CloudFormation Template

Generate the CloudFormation template to verify the infrastructure:

```bash
cdk synth
```

This creates a `cdk.out` directory with the CloudFormation template. Review the template to ensure it matches your expectations.

### 7. Deploy Infrastructure

Deploy the infrastructure to AWS:

```bash
cdk deploy
```

You'll see a summary of resources to be created. Type `y` to confirm.

**Deployment time:** Approximately 10-15 minutes

The deployment creates:
- 1 VPC with 3 private subnets across 3 AZs
- 6 VPC endpoints (Bedrock, S3, DynamoDB, KMS, CloudWatch Logs, EventBridge)
- 2 KMS keys (encryption and signing)
- 9 S3 buckets (versioned and encrypted)
- 2 DynamoDB tables (with PITR enabled)

### 8. Verify Deployment

After deployment completes, verify the resources:

```bash
# List S3 buckets
aws s3 ls | grep rosetta-zero

# List DynamoDB tables
aws dynamodb list-tables --query 'TableNames[?contains(@, `rosetta-zero`)]'

# List KMS keys
aws kms list-aliases --query 'Aliases[?contains(AliasName, `rosetta-zero`)]'

# Describe VPC
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=RosettaZeroStack/RosettaZeroVPC"
```

## Post-Deployment Configuration

### Security Group Configuration

The VPC endpoints are created with default security groups. For production deployments, configure security groups with least-privilege rules:

```bash
# Get VPC endpoint IDs
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=YOUR_VPC_ID"

# Update security group rules as needed
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 443 \
  --source-group sg-yyyyy
```

### KMS Key Policies

The KMS keys are created with default policies. For production, update key policies to grant access only to specific IAM roles:

```bash
# Get KMS key IDs
aws kms list-aliases --query 'Aliases[?contains(AliasName, `rosetta-zero`)]'

# Update key policy (create policy.json first)
aws kms put-key-policy \
  --key-id YOUR_KEY_ID \
  --policy-name default \
  --policy file://policy.json
```

### S3 Bucket Policies

For production, add bucket policies to restrict access:

```bash
# Example: Add bucket policy to legacy-artifacts bucket
aws s3api put-bucket-policy \
  --bucket rosetta-zero-legacy-artifacts-ACCOUNT-REGION \
  --policy file://bucket-policy.json
```

## Updating Infrastructure

### View Changes Before Deployment

```bash
cdk diff
```

This shows what will change if you deploy.

### Deploy Updates

```bash
cdk deploy
```

CDK will only update changed resources.

## Monitoring and Logging

### CloudWatch Logs

All VPC endpoint traffic is logged to CloudWatch Logs. View logs:

```bash
aws logs describe-log-groups --log-group-name-prefix /aws/vpc
```

### CloudWatch Metrics

Monitor infrastructure metrics in the AWS Console:
1. Navigate to CloudWatch
2. Select "Dashboards"
3. Look for "RosettaZeroDashboard" (created in future tasks)

## Troubleshooting

### CDK Bootstrap Fails

**Error:** "Unable to resolve AWS account to use"

**Solution:** Ensure AWS credentials are configured:
```bash
aws configure
aws sts get-caller-identity
```

### Deployment Fails - Insufficient Permissions

**Error:** "User is not authorized to perform: ..."

**Solution:** Ensure your IAM user/role has permissions for:
- VPC creation and management
- KMS key creation
- S3 bucket creation
- DynamoDB table creation
- IAM role creation (for CDK)

### VPC Endpoint Creation Fails

**Error:** "Service not available in region"

**Solution:** Some VPC endpoint services may not be available in all regions. Check service availability:
```bash
aws ec2 describe-vpc-endpoint-services --region YOUR_REGION
```

### Resource Limit Exceeded

**Error:** "LimitExceededException"

**Solution:** Request limit increases through AWS Support:
- VPC limit (default: 5 per region)
- S3 bucket limit (default: 100 per account)
- KMS key limit (default: 1000 per region)

## Cleanup

### Destroy Infrastructure

To remove all infrastructure:

```bash
cdk destroy
```

**Warning:** Resources with `RemovalPolicy.RETAIN` will not be deleted:
- KMS keys
- S3 buckets (with data)
- DynamoDB tables (with data)

### Manual Cleanup of Retained Resources

After `cdk destroy`, manually delete retained resources:

```bash
# Delete S3 buckets (empties and deletes)
aws s3 rb s3://rosetta-zero-legacy-artifacts-ACCOUNT-REGION --force
aws s3 rb s3://rosetta-zero-logic-maps-ACCOUNT-REGION --force
# ... repeat for all buckets

# Schedule KMS key deletion (7-30 day waiting period)
aws kms schedule-key-deletion --key-id YOUR_KEY_ID --pending-window-in-days 7

# Delete DynamoDB tables
aws dynamodb delete-table --table-name rosetta-zero-test-results
aws dynamodb delete-table --table-name rosetta-zero-workflow-phases
```

## Cost Estimation

### Monthly Cost Breakdown (Estimated)

**VPC and Networking:**
- VPC: Free
- VPC Endpoints: ~$21.60/month (6 endpoints × $0.01/hour × 720 hours)
- Data transfer: Variable based on usage

**KMS:**
- 2 customer-managed keys: $2.00/month
- API requests: $0.03 per 10,000 requests

**S3:**
- Storage: Variable based on data volume
- Requests: Variable based on usage
- Versioning: Additional storage for versions

**DynamoDB:**
- PAY_PER_REQUEST: $1.25 per million write requests, $0.25 per million read requests
- Storage: $0.25 per GB-month
- Point-in-time recovery: Additional cost

**Total Estimated Base Cost:** ~$25-50/month (excluding data storage and transfer)

### Cost Optimization Tips

1. **Use S3 Lifecycle Policies:** Archive old data to S3 Glacier
2. **Monitor DynamoDB Usage:** Consider provisioned capacity if usage is predictable
3. **Delete Unused VPC Endpoints:** Remove endpoints for services not in use
4. **Enable Cost Allocation Tags:** Track costs by resource

## Security Best Practices

1. **Enable CloudTrail:** Log all API calls for audit
2. **Enable AWS Config:** Track configuration changes
3. **Enable GuardDuty:** Detect security threats
4. **Rotate KMS Keys:** Use automatic key rotation
5. **Review IAM Policies:** Follow principle of least privilege
6. **Enable MFA:** Require MFA for sensitive operations
7. **Use VPC Flow Logs:** Monitor network traffic

## Support

For issues or questions:
1. Check AWS CDK documentation: https://docs.aws.amazon.com/cdk/
2. Review CloudFormation events in AWS Console
3. Check CloudWatch Logs for error messages
4. Consult AWS Support (if you have a support plan)

## Next Steps

After infrastructure deployment:
1. Deploy Lambda functions (Task 2)
2. Configure Step Functions workflows (Task 3)
3. Set up EventBridge rules (Task 4)
4. Deploy Fargate containers (Task 5)
5. Configure monitoring and alerting (Task 6)
