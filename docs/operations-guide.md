# Rosetta Zero - Operations Guide

This guide provides operational procedures for monitoring, troubleshooting, and managing the Rosetta Zero system in production.

**Requirements:** 19.3, 19.4

## Table of Contents

1. [Monitoring and Alerting](#monitoring-and-alerting)
2. [Operator Intervention Procedures](#operator-intervention-procedures)
3. [AWS 500-Level Error Handling](#aws-500-level-error-handling)
4. [Troubleshooting Common Issues](#troubleshooting-common-issues)
5. [Incident Response](#incident-response)
6. [Maintenance Procedures](#maintenance-procedures)

---

## Monitoring and Alerting

### CloudWatch Dashboards

Rosetta Zero provides pre-configured CloudWatch dashboards for monitoring system health:

1. **Test Execution Dashboard**: Monitors test execution rate, pass/fail rates, and throughput
2. **System Health Dashboard**: Monitors Lambda function errors, Step Functions execution status, and resource utilization
3. **Performance Dashboard**: Tracks execution duration, API latency, and resource consumption

#### Accessing Dashboards

```bash
# Open CloudWatch console
aws cloudwatch get-dashboard --dashboard-name rosetta-zero-monitoring

# Or navigate to:
# AWS Console → CloudWatch → Dashboards → rosetta-zero-monitoring
```

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| Test Execution Rate | < 100 tests/min | Investigate Step Functions throttling |
| Test Pass Rate | < 100% | Review discrepancy reports |
| Lambda Error Rate | > 1% | Check CloudWatch Logs for errors |
| Step Functions Failed Executions | > 0 | Review execution history |
| DynamoDB Throttled Requests | > 0 | Increase provisioned capacity |
| S3 4xx Errors | > 0 | Check IAM permissions |
| S3 5xx Errors | > 0 | **Trigger operator intervention** |

### SNS Notifications

Rosetta Zero sends notifications to the `rosetta-zero-operator-notifications` SNS topic for critical events:

- **AWS 500-Level Errors**: Immediate notification when any AWS service returns a 500-level error
- **Behavioral Discrepancies**: Notification when test outputs don't match
- **Certificate Generation**: Notification when equivalence certificate is generated
- **Workflow Phase Completion**: Notification when each workflow phase completes

#### Subscribing to Notifications

```bash
# Subscribe email to SNS topic
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:rosetta-zero-operator-notifications \
  --protocol email \
  --notification-endpoint operator@example.com

# Subscribe SMS
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:rosetta-zero-operator-notifications \
  --protocol sms \
  --notification-endpoint +1234567890

# Subscribe Lambda function for automated response
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:rosetta-zero-operator-notifications \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:REGION:ACCOUNT:function:incident-handler
```

### CloudWatch Alarms

Pre-configured alarms monitor critical system conditions:

```bash
# List all Rosetta Zero alarms
aws cloudwatch describe-alarms --alarm-name-prefix rosetta-zero

# View alarm history
aws cloudwatch describe-alarm-history \
  --alarm-name rosetta-zero-aws-500-errors \
  --max-records 10
```

#### Critical Alarms

1. **AWS 500 Errors**: Triggers on any AWS service 500-level error
2. **Lambda Function Errors**: Triggers when Lambda error rate exceeds threshold
3. **Step Functions Failures**: Triggers on Step Functions execution failures
4. **DynamoDB Throttling**: Triggers on throttled requests
5. **Certificate Generation Failures**: Triggers when certificate generation fails

---

## Operator Intervention Procedures

### When Operator Intervention is Required

Rosetta Zero operates autonomously but requires operator intervention in these scenarios:

1. **AWS 500-Level Errors** (Requirements 19.3, 19.4)
2. **Behavioral Discrepancies** (test failures)
3. **Resource Exhaustion** (quota limits, capacity issues)
4. **Security Incidents** (unauthorized access attempts)
5. **Data Integrity Issues** (corrupted artifacts, missing data)

### Notification Channels

When operator intervention is required, you will receive notifications via:

- **SNS Email**: Detailed alert with error context
- **SNS SMS**: Brief alert for immediate attention
- **CloudWatch Logs**: Complete error details and stack traces
- **EventBridge Events**: Structured event data for automation

### Response Time Expectations

| Severity | Response Time | Resolution Time |
|----------|---------------|-----------------|
| Critical (AWS 500 errors) | 15 minutes | 1 hour |
| High (Behavioral discrepancies) | 1 hour | 4 hours |
| Medium (Resource issues) | 4 hours | 1 business day |
| Low (Informational) | 1 business day | As needed |

---

## AWS 500-Level Error Handling

**Requirements:** 19.3, 19.4

When any AWS service returns a 500-level error (500, 502, 503, 504), Rosetta Zero automatically:

1. **Logs the error** to CloudWatch with full context
2. **Publishes an SNS notification** to operators
3. **Publishes an EventBridge event** for automation
4. **Pauses execution** until operator intervention
5. **Does NOT retry** (to prevent cascading failures)

### Identifying AWS 500 Errors

#### CloudWatch Logs

```bash
# Search for AWS 500 errors in CloudWatch Logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/rosetta-zero-ingestion-engine \
  --filter-pattern "\"AWS 500 Error\"" \
  --start-time $(date -u -d '1 hour ago' +%s)000

# Search across all Rosetta Zero log groups
for log_group in $(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/rosetta-zero --query 'logGroups[].logGroupName' --output text); do
  echo "Checking $log_group..."
  aws logs filter-log-events \
    --log-group-name "$log_group" \
    --filter-pattern "\"AWS 500 Error\"" \
    --start-time $(date -u -d '1 hour ago' +%s)000
done
```

#### EventBridge Events

```bash
# Query EventBridge for AWS 500 error events
aws events put-rule \
  --name rosetta-zero-500-error-query \
  --event-pattern '{
    "source": ["rosetta-zero"],
    "detail-type": ["AWS 500 Error"]
  }'

# View recent events (requires CloudTrail or EventBridge archive)
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutEvents \
  --max-results 10
```

#### SNS Notifications

Check your email or SMS for notifications with subject line:

```
Rosetta Zero: AWS 500-level error in [Service Name]
```

### AWS 500 Error Response Procedure

#### Step 1: Acknowledge the Alert

Acknowledge receipt of the alert within 15 minutes:

```bash
# Log acknowledgment
aws logs put-log-events \
  --log-group-name /aws/rosetta-zero/operator-actions \
  --log-stream-name $(date +%Y-%m-%d) \
  --log-events timestamp=$(date +%s)000,message="Operator acknowledged AWS 500 error alert: [ERROR_ID]"
```

#### Step 2: Identify the Affected Service

The SNS notification includes:

- **Service Name**: Which AWS service returned the error (Bedrock, S3, DynamoDB, KMS, etc.)
- **Error Code**: Specific HTTP status code (500, 502, 503, 504)
- **Context ID**: Workflow ID, test vector ID, or artifact ID
- **Timestamp**: When the error occurred
- **Error Message**: Full error details

Example notification:

```
Alert Type: AWS 500-level error in Bedrock
Error: BedrockServiceException: Internal server error
Error Type: BedrockServiceException
Context ID: workflow-abc123
Timestamp: 2024-01-15T10:30:45.123Z

Operator intervention required. System execution paused.
```

#### Step 3: Check AWS Service Health

```bash
# Check AWS Service Health Dashboard
# Navigate to: https://health.aws.amazon.com/health/status

# Or use AWS Health API
aws health describe-events \
  --filter eventTypeCategories=issue \
  --max-results 10

# Check specific service status
aws health describe-event-details \
  --event-arns $(aws health describe-events \
    --filter eventTypeCategories=issue,services=BEDROCK \
    --query 'events[0].arn' \
    --output text)
```

#### Step 4: Determine Root Cause

Common causes of AWS 500 errors:

1. **AWS Service Outage**: Regional or service-wide issue
2. **Throttling**: Rate limits exceeded (though usually returns 429)
3. **Resource Exhaustion**: Service capacity limits reached
4. **Transient Failure**: Temporary issue that may resolve itself

#### Step 5: Take Corrective Action

##### If AWS Service Outage:

1. **Wait for AWS to resolve**: Monitor AWS Service Health Dashboard
2. **Consider failover**: If multi-region is configured, failover to secondary region
3. **Document incident**: Record outage details for post-mortem

```bash
# Document incident
cat > incident-$(date +%Y%m%d-%H%M%S).md << EOF
# AWS Service Outage Incident

**Date**: $(date)
**Service**: [Service Name]
**Error**: [Error Message]
**Context**: [Context ID]
**Status**: Waiting for AWS resolution
**AWS Health Dashboard**: [Link to health event]

## Timeline
- $(date): Error detected
- $(date): Operator acknowledged
- $(date): AWS service outage confirmed

## Actions Taken
- Monitored AWS Service Health Dashboard
- Notified stakeholders
- Waiting for AWS resolution

## Next Steps
- Resume workflow after AWS confirms resolution
- Verify system health
- Complete pending work
EOF
```

##### If Transient Failure:

1. **Wait 5-10 minutes**: Allow AWS service to recover
2. **Check service health**: Verify service is operational
3. **Resume workflow**: Manually trigger workflow continuation

```bash
# Resume workflow after transient failure
# Identify the paused workflow
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:rosetta-zero-verification \
  --status-filter FAILED \
  --max-results 10

# Get execution details
aws stepfunctions describe-execution \
  --execution-arn [EXECUTION_ARN]

# Restart from last successful state
# Option 1: Restart entire workflow
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:rosetta-zero-verification \
  --input '{"workflowId": "[WORKFLOW_ID]", "resumeFrom": "[LAST_SUCCESSFUL_STATE]"}'

# Option 2: Manually invoke failed Lambda function
aws lambda invoke \
  --function-name rosetta-zero-ingestion-engine \
  --payload '{"artifactId": "[ARTIFACT_ID]"}' \
  response.json
```

##### If Resource Exhaustion:

1. **Increase quotas**: Request service quota increase
2. **Optimize usage**: Reduce concurrent executions or batch size
3. **Scale resources**: Increase provisioned capacity

```bash
# Check current service quotas
aws service-quotas list-service-quotas \
  --service-code lambda \
  --query 'Quotas[?QuotaName==`Concurrent executions`]'

# Request quota increase
aws service-quotas request-service-quota-increase \
  --service-code lambda \
  --quota-code L-B99A9384 \
  --desired-value 2000

# Increase DynamoDB capacity (if using provisioned mode)
aws dynamodb update-table \
  --table-name rosetta-zero-test-results \
  --provisioned-throughput ReadCapacityUnits=1000,WriteCapacityUnits=1000
```

#### Step 6: Resume Workflow Execution

After resolving the root cause:

```bash
# Verify AWS service is healthy
aws bedrock invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":100,"messages":[{"role":"user","content":"test"}]}' \
  --cli-binary-format raw-in-base64-out \
  response.json

# Resume workflow
# The specific command depends on where the workflow paused
# Consult the workflow state machine definition for resume points

# For Ingestion Engine failures:
aws lambda invoke \
  --function-name rosetta-zero-ingestion-engine \
  --payload file://resume-payload.json \
  response.json

# For Verification Environment failures:
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:rosetta-zero-verification \
  --input file://resume-input.json

# For Certificate Generation failures:
aws lambda invoke \
  --function-name rosetta-zero-certificate-generator \
  --payload file://resume-payload.json \
  response.json
```

#### Step 7: Verify System Health

After resuming:

```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace RosettaZero \
  --metric-name TestsExecuted \
  --start-time $(date -u -d '10 minutes ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 300 \
  --statistics Sum

# Check recent Lambda invocations
aws lambda get-function \
  --function-name rosetta-zero-ingestion-engine \
  --query 'Configuration.LastModified'

# Check Step Functions executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:rosetta-zero-verification \
  --status-filter RUNNING \
  --max-results 10

# Verify no new errors
aws logs tail /aws/lambda/rosetta-zero-ingestion-engine --follow
```

#### Step 8: Document Resolution

```bash
# Update incident report
cat >> incident-$(date +%Y%m%d-%H%M%S).md << EOF

## Resolution
- $(date): Root cause identified: [CAUSE]
- $(date): Corrective action taken: [ACTION]
- $(date): Workflow resumed
- $(date): System health verified

## Outcome
- Workflow completed successfully
- No data loss
- Total downtime: [DURATION]

## Lessons Learned
- [LESSON 1]
- [LESSON 2]

## Follow-up Actions
- [ ] Update runbooks
- [ ] Implement additional monitoring
- [ ] Request quota increases
EOF
```

### AWS 500 Error Prevention

To minimize AWS 500 errors:

1. **Implement exponential backoff**: Already implemented for transient errors
2. **Monitor service quotas**: Set up alarms for quota utilization
3. **Use multiple regions**: Deploy multi-region for failover
4. **Implement circuit breakers**: Prevent cascading failures
5. **Regular health checks**: Proactively monitor service health

```bash
# Set up quota monitoring
aws cloudwatch put-metric-alarm \
  --alarm-name rosetta-zero-lambda-concurrent-executions \
  --alarm-description "Alert when Lambda concurrent executions exceed 80% of quota" \
  --metric-name ConcurrentExecutions \
  --namespace AWS/Lambda \
  --statistic Maximum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 800 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:REGION:ACCOUNT:rosetta-zero-operator-notifications
```

---

## Troubleshooting Common Issues

### Issue: Behavioral Discrepancy Detected

**Symptom**: Test fails with outputs that don't match between legacy and modern implementations.

**Diagnosis**:

```bash
# Find discrepancy report
aws s3 ls s3://rosetta-zero-discrepancy-reports/ --recursive

# Download report
aws s3 cp s3://rosetta-zero-discrepancy-reports/[REPORT_ID]/report.json .

# View report
cat report.json | jq .
```

**Resolution**:

1. Review discrepancy report to understand the difference
2. Analyze Logic Map to verify behavioral requirements
3. Review modern implementation code
4. Determine if issue is in:
   - Logic Map extraction (incorrect behavioral analysis)
   - Modern code synthesis (incorrect implementation)
   - Test vector generation (invalid test input)
5. Correct the issue and re-run workflow

### Issue: Test Vector Generation Slow

**Symptom**: Hostile Auditor takes too long to generate test vectors.

**Diagnosis**:

```bash
# Check Lambda execution duration
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=rosetta-zero-hostile-auditor \
  --start-time $(date -u -d '1 hour ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 300 \
  --statistics Average,Maximum

# Check Lambda memory usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=rosetta-zero-hostile-auditor \
  --start-time $(date -u -d '1 hour ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 300 \
  --statistics Average,Maximum
```

**Resolution**:

1. Increase Lambda memory allocation (increases CPU proportionally)
2. Reduce target test vector count
3. Optimize test generation strategies
4. Use parallel Lambda invocations for batch generation

```bash
# Update Lambda memory
aws lambda update-function-configuration \
  --function-name rosetta-zero-hostile-auditor \
  --memory-size 10240 \
  --timeout 900
```

### Issue: Step Functions Execution Timeout

**Symptom**: Step Functions execution times out before completing.

**Diagnosis**:

```bash
# Check execution history
aws stepfunctions get-execution-history \
  --execution-arn [EXECUTION_ARN] \
  --max-results 100

# Identify slow states
aws stepfunctions get-execution-history \
  --execution-arn [EXECUTION_ARN] \
  --max-results 100 | jq '.events[] | select(.type | contains("StateEntered") or contains("StateExited"))'
```

**Resolution**:

1. Increase Step Functions timeout
2. Optimize slow Lambda functions
3. Reduce batch size for parallel executions
4. Use Express Workflows for high-throughput scenarios

### Issue: DynamoDB Throttling

**Symptom**: DynamoDB returns `ProvisionedThroughputExceededException`.

**Diagnosis**:

```bash
# Check throttled requests
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=rosetta-zero-test-results \
  --start-time $(date -u -d '1 hour ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 300 \
  --statistics Sum
```

**Resolution**:

1. Enable DynamoDB auto-scaling (already configured)
2. Switch to on-demand billing mode
3. Implement exponential backoff in application code
4. Batch write operations

```bash
# Switch to on-demand mode
aws dynamodb update-table \
  --table-name rosetta-zero-test-results \
  --billing-mode PAY_PER_REQUEST
```

### Issue: S3 Access Denied

**Symptom**: Lambda functions cannot read/write S3 objects.

**Diagnosis**:

```bash
# Check Lambda execution role
aws lambda get-function \
  --function-name rosetta-zero-ingestion-engine \
  --query 'Configuration.Role'

# Check role policies
aws iam list-attached-role-policies \
  --role-name [ROLE_NAME]

# Check bucket policy
aws s3api get-bucket-policy \
  --bucket rosetta-zero-legacy-artifacts
```

**Resolution**:

1. Verify IAM role has correct S3 permissions
2. Check bucket policy allows access from Lambda role
3. Verify KMS key policy allows Lambda role to decrypt objects
4. Check VPC endpoint policy allows S3 access

### Issue: Bedrock Model Not Available

**Symptom**: Bedrock returns `ModelNotFoundException` or `AccessDeniedException`.

**Diagnosis**:

```bash
# List available models
aws bedrock list-foundation-models \
  --region us-east-1

# Check model access
aws bedrock get-foundation-model \
  --model-identifier anthropic.claude-3-5-sonnet-20241022-v2:0
```

**Resolution**:

1. Request model access in Bedrock console
2. Verify region supports the model
3. Check IAM permissions for Bedrock access
4. Wait for model access approval (can take 24 hours)

---

## Incident Response

### Incident Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| **P0 - Critical** | System down, data loss risk | Immediate response, all hands on deck |
| **P1 - High** | Major functionality impaired | Response within 15 minutes |
| **P2 - Medium** | Minor functionality impaired | Response within 1 hour |
| **P3 - Low** | Cosmetic or informational | Response within 1 business day |

### Incident Response Workflow

1. **Detection**: Alert received via SNS, CloudWatch, or monitoring
2. **Acknowledgment**: Operator acknowledges within SLA
3. **Triage**: Assess severity and impact
4. **Investigation**: Identify root cause
5. **Mitigation**: Implement temporary fix
6. **Resolution**: Implement permanent fix
7. **Verification**: Confirm system health
8. **Documentation**: Document incident and lessons learned
9. **Post-Mortem**: Conduct blameless post-mortem

### Incident Communication

```bash
# Create incident channel (Slack, Teams, etc.)
# Post status updates every 30 minutes

# Example status update template:
cat > status-update.md << EOF
## Incident Status Update - $(date)

**Incident ID**: INC-$(date +%Y%m%d-%H%M%S)
**Severity**: P1
**Status**: Investigating
**Impact**: Test execution paused
**ETA**: 30 minutes

**Current Actions**:
- Investigating AWS 500 error in Bedrock
- Checking AWS Service Health Dashboard
- Preparing failover to secondary region

**Next Update**: $(date -d '+30 minutes')
EOF
```

### Escalation Path

1. **Level 1**: On-call operator
2. **Level 2**: Senior operator or team lead
3. **Level 3**: Engineering manager
4. **Level 4**: AWS Support (Enterprise Support required)

```bash
# Open AWS Support case
aws support create-case \
  --subject "Rosetta Zero: AWS 500 error in Bedrock" \
  --service-code "bedrock" \
  --severity-code "urgent" \
  --category-code "api-issue" \
  --communication-body "Experiencing persistent 500 errors from Bedrock API. Workflow paused. Need immediate assistance."
```

---

## Maintenance Procedures

### Routine Maintenance

#### Daily Tasks

- Review CloudWatch dashboards
- Check SNS notifications
- Verify test execution metrics
- Monitor resource utilization

```bash
# Daily health check script
#!/bin/bash
echo "=== Rosetta Zero Daily Health Check ==="
echo "Date: $(date)"
echo ""

echo "1. Lambda Function Errors (last 24 hours):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=rosetta-zero-ingestion-engine \
  --start-time $(date -u -d '24 hours ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 86400 \
  --statistics Sum

echo ""
echo "2. Step Functions Failed Executions (last 24 hours):"
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:REGION:ACCOUNT:stateMachine:rosetta-zero-verification \
  --status-filter FAILED \
  --max-results 10

echo ""
echo "3. DynamoDB Throttled Requests (last 24 hours):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=rosetta-zero-test-results \
  --start-time $(date -u -d '24 hours ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 86400 \
  --statistics Sum

echo ""
echo "4. S3 5xx Errors (last 24 hours):"
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name 5xxErrors \
  --dimensions Name=BucketName,Value=rosetta-zero-legacy-artifacts \
  --start-time $(date -u -d '24 hours ago' --iso-8601=seconds) \
  --end-time $(date -u --iso-8601=seconds) \
  --period 86400 \
  --statistics Sum

echo ""
echo "=== Health Check Complete ==="
```

#### Weekly Tasks

- Review and archive old logs
- Check service quota utilization
- Review security findings
- Update documentation

```bash
# Weekly maintenance script
#!/bin/bash
echo "=== Rosetta Zero Weekly Maintenance ==="
echo "Date: $(date)"
echo ""

echo "1. Service Quota Utilization:"
aws service-quotas list-service-quotas \
  --service-code lambda \
  --query 'Quotas[?QuotaName==`Concurrent executions`]'

echo ""
echo "2. S3 Bucket Sizes:"
for bucket in $(aws s3 ls | grep rosetta-zero | awk '{print $3}'); do
  size=$(aws s3 ls s3://$bucket --recursive --summarize | grep "Total Size" | awk '{print $3}')
  echo "$bucket: $size bytes"
done

echo ""
echo "3. DynamoDB Table Sizes:"
aws dynamodb describe-table \
  --table-name rosetta-zero-test-results \
  --query 'Table.TableSizeBytes'

echo ""
echo "=== Weekly Maintenance Complete ==="
```

#### Monthly Tasks

- Review and optimize costs
- Update Lambda function code
- Rotate KMS keys (if required)
- Conduct security audit
- Review and update runbooks

### Backup and Recovery

#### S3 Versioning

All S3 buckets have versioning enabled. To recover a deleted object:

```bash
# List object versions
aws s3api list-object-versions \
  --bucket rosetta-zero-legacy-artifacts \
  --prefix artifacts/

# Restore specific version
aws s3api copy-object \
  --bucket rosetta-zero-legacy-artifacts \
  --copy-source rosetta-zero-legacy-artifacts/artifacts/file.bin?versionId=VERSION_ID \
  --key artifacts/file.bin
```

#### DynamoDB Point-in-Time Recovery

DynamoDB tables have point-in-time recovery enabled. To restore:

```bash
# Restore table to specific time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name rosetta-zero-test-results \
  --target-table-name rosetta-zero-test-results-restored \
  --restore-date-time $(date -u -d '1 hour ago' --iso-8601=seconds)
```

#### Cross-Region Replication

Equivalence certificates are automatically replicated to a secondary region. To verify:

```bash
# Check replication status
aws s3api get-bucket-replication \
  --bucket rosetta-zero-certificates

# List objects in replica bucket
aws s3 ls s3://rosetta-zero-certificates-replica-REGION/ --recursive
```

### Log Management

#### Log Retention

- **Development**: 7 days
- **Staging**: 30 days
- **Production**: 2555 days (7 years)

#### Log Export

```bash
# Export logs to S3 for long-term archival
aws logs create-export-task \
  --log-group-name /aws/lambda/rosetta-zero-ingestion-engine \
  --from $(date -u -d '30 days ago' +%s)000 \
  --to $(date -u +%s)000 \
  --destination rosetta-zero-log-archive \
  --destination-prefix lambda-logs/ingestion-engine/
```

### Security Maintenance

#### KMS Key Rotation

```bash
# Enable automatic key rotation
aws kms enable-key-rotation \
  --key-id [KEY_ID]

# Check rotation status
aws kms get-key-rotation-status \
  --key-id [KEY_ID]
```

#### IAM Access Review

```bash
# List IAM roles used by Rosetta Zero
aws iam list-roles \
  --query 'Roles[?contains(RoleName, `rosetta-zero`)]'

# Review role policies
aws iam list-attached-role-policies \
  --role-name [ROLE_NAME]

# Review last used date
aws iam get-role \
  --role-name [ROLE_NAME] \
  --query 'Role.RoleLastUsed'
```

---

## Additional Resources

- [Deployment Guide](./deployment-guide.md)
- [Multi-Region Deployment](./multi-region-deployment.md)
- [AWS Service Health Dashboard](https://health.aws.amazon.com/health/status)
- [AWS Support](https://console.aws.amazon.com/support/)
- [Rosetta Zero Architecture](../README.md)