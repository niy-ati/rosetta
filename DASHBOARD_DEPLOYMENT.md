# Rosetta Zero Dashboard Deployment Guide

This guide walks through deploying the Rosetta Zero Web Dashboard, including the frontend, backend API, and authentication.

## Architecture

The dashboard consists of:

1. **Frontend**: React app hosted on S3 + CloudFront
2. **Backend API**: Lambda functions behind API Gateway
3. **Authentication**: AWS Cognito User Pool
4. **Integration**: Connects to existing Rosetta Zero infrastructure

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)
- Node.js 18+ and npm
- Python 3.12+
- Existing Rosetta Zero backend deployed

## Step 1: Deploy Backend Infrastructure

Deploy the dashboard stack using CDK:

```bash
# From project root
cdk deploy DashboardStack
```

This creates:
- Cognito User Pool for authentication
- API Gateway REST API
- Lambda function for API endpoints
- S3 bucket for frontend hosting
- CloudFront distribution

**Save the outputs** - you'll need them for frontend configuration:
- `UserPoolId`
- `UserPoolClientId`
- `ApiUrl`
- `DistributionUrl`
- `FrontendBucket`

## Step 2: Create Admin User

Create an admin user in Cognito:

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId from Step 1> \
  --username admin@example.com \
  --user-attributes Name=email,Value=admin@example.com \
  --temporary-password TempPassword123! \
  --message-action SUPPRESS
```

The user will need to change their password on first login.

## Step 3: Configure Frontend

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment configuration:
```bash
cp .env.example .env
```

4. Edit `.env` with values from Step 1:
```env
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=<UserPoolId from Step 1>
VITE_USER_POOL_CLIENT_ID=<UserPoolClientId from Step 1>
VITE_API_URL=<ApiUrl from Step 1>
```

## Step 4: Build and Deploy Frontend

1. Build the production bundle:
```bash
npm run build
```

2. Deploy to S3:
```bash
aws s3 sync dist/ s3://<FrontendBucket from Step 1>/ --delete
```

3. Invalidate CloudFront cache:
```bash
# Get distribution ID
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Origins.Items[0].DomainName=='<FrontendBucket>.s3.amazonaws.com'].Id" \
  --output text)

# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id $DIST_ID \
  --paths "/*"
```

## Step 5: Access the Dashboard

1. Open the CloudFront URL from Step 1 in your browser
2. Log in with the admin credentials from Step 2
3. You'll be prompted to change your password on first login

## Configuration

### Adding More Users

```bash
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com \
  --temporary-password TempPassword123!
```

### Updating API Permissions

The Dashboard API Lambda needs permissions to access Rosetta Zero resources. Update the IAM role in `infrastructure/dashboard_stack.py` if needed.

### Customizing Authentication

Edit the Cognito User Pool configuration in `infrastructure/dashboard_stack.py`:
- Password policy
- MFA requirements
- Account recovery options
- User attributes

## Monitoring

### CloudWatch Logs

Dashboard API logs are in:
```
/aws/lambda/DashboardStack-dashboard-api
```

View logs:
```bash
aws logs tail /aws/lambda/DashboardStack-dashboard-api --follow
```

### API Gateway Metrics

Monitor API Gateway in CloudWatch:
- Request count
- Latency
- 4XX/5XX errors

### Cognito Metrics

Monitor authentication in CloudWatch:
- Sign-in attempts
- Failed authentications
- User registrations

## Troubleshooting

### Issue: Can't log in

**Symptoms**: Login fails with "User does not exist" or "Incorrect username or password"

**Solutions**:
1. Verify user exists in Cognito:
```bash
aws cognito-idp admin-get-user \
  --user-pool-id <UserPoolId> \
  --username user@example.com
```

2. Check user status (should be CONFIRMED):
```bash
aws cognito-idp admin-get-user \
  --user-pool-id <UserPoolId> \
  --username user@example.com \
  --query 'UserStatus'
```

3. Reset password if needed:
```bash
aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username user@example.com \
  --password NewPassword123! \
  --permanent
```

### Issue: API calls return 401 Unauthorized

**Symptoms**: Dashboard loads but API calls fail with 401

**Solutions**:
1. Check Cognito configuration in `.env`
2. Verify API Gateway authorizer is configured correctly
3. Check CloudWatch Logs for Lambda errors
4. Verify CORS is enabled on API Gateway

### Issue: Frontend shows blank page

**Symptoms**: CloudFront URL loads but shows blank page

**Solutions**:
1. Check browser console for errors
2. Verify S3 bucket has correct files:
```bash
aws s3 ls s3://<FrontendBucket>/ --recursive
```

3. Check CloudFront error responses configuration
4. Verify index.html exists in S3 bucket

### Issue: Upload fails

**Symptoms**: Artifact upload returns error

**Solutions**:
1. Check Lambda timeout (increase if needed)
2. Verify S3 bucket permissions
3. Check file size limits
4. Review CloudWatch Logs for Lambda errors

## Security Best Practices

1. **Enable MFA**: Require MFA for all users
```bash
aws cognito-idp set-user-pool-mfa-config \
  --user-pool-id <UserPoolId> \
  --mfa-configuration OPTIONAL \
  --software-token-mfa-configuration Enabled=true
```

2. **Restrict API Access**: Update API Gateway resource policy to limit access by IP or VPC

3. **Enable CloudTrail**: Log all API calls for audit trail

4. **Rotate Credentials**: Regularly rotate IAM credentials and Cognito app client secrets

5. **Monitor Failed Logins**: Set up CloudWatch alarms for failed authentication attempts

## Updating the Dashboard

### Update Frontend

1. Make changes to frontend code
2. Build: `npm run build`
3. Deploy: `aws s3 sync dist/ s3://<FrontendBucket>/ --delete`
4. Invalidate cache: `aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"`

### Update Backend API

1. Make changes to Lambda code in `rosetta_zero/lambdas/dashboard_api/`
2. Deploy: `cdk deploy DashboardStack`

### Update Infrastructure

1. Make changes to `infrastructure/dashboard_stack.py`
2. Deploy: `cdk deploy DashboardStack`

## Cleanup

To remove all dashboard resources:

```bash
# Delete CloudFormation stack
cdk destroy DashboardStack

# Verify S3 buckets are deleted
aws s3 ls | grep DashboardStack
```

## Cost Estimation

Approximate monthly costs (us-east-1):

- **Cognito**: $0.0055 per MAU (first 50,000 free)
- **API Gateway**: $3.50 per million requests
- **Lambda**: $0.20 per million requests + compute time
- **S3**: $0.023 per GB storage + $0.09 per GB transfer
- **CloudFront**: $0.085 per GB transfer (first 10 TB)

**Estimated total**: $10-50/month for typical usage

## Support

For issues or questions:
1. Check CloudWatch Logs
2. Review AWS service quotas
3. Verify IAM permissions
4. Check AWS service health dashboard

## Next Steps

After deployment:
1. Create additional users
2. Configure custom domain (optional)
3. Set up monitoring and alerts
4. Enable AWS WAF for additional security (optional)
5. Configure backup and disaster recovery
