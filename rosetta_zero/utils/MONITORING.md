# Rosetta Zero Monitoring, Logging, and Event Infrastructure

This document describes the monitoring, logging, and event infrastructure for Rosetta Zero.

## Overview

The monitoring infrastructure provides:
- **CloudWatch Logs** with 7-year retention and KMS encryption
- **Immutable audit logging** for all component decisions
- **EventBridge** event bus and rules for event-driven notifications
- **SNS topics** for operator alerts
- **Performance metrics** publishing to CloudWatch
- **CloudWatch dashboards** for system monitoring

## Requirements Coverage

- **18.1-18.7**: Immutable audit logging with 7-year retention and KMS encryption
- **17.9**: EventBridge events for certificate generation
- **19.3, 19.4**: SNS notifications for AWS 500-level errors
- **24.6**: EventBridge events for workflow phase completion
- **25.5**: EventBridge events for error recovery
- **29.1-29.5**: Performance metrics and CloudWatch dashboards

## Components

### 1. CloudWatch Logs Manager

**Module**: `rosetta_zero.utils.monitoring.CloudWatchLogsManager`

Manages CloudWatch Log Groups with encryption and retention.

**Features**:
- Creates log groups with 7-year retention (2555 days)
- Enables KMS encryption for all log groups
- Configures structured JSON logging format
- Automatic log group configuration for all Lambda functions

**Usage**:
```python
from rosetta_zero.utils.monitoring import CloudWatchLogsManager

logs_manager = CloudWatchLogsManager(
    kms_key_id="arn:aws:kms:...",
    retention_days=2555
)

# Configure log group
result = logs_manager.configure_log_group(
    log_group_name="/aws/lambda/rosetta-zero-ingestion-engine"
)
```

### 2. Immutable Audit Logging

**Module**: `rosetta_zero.utils.logging`

Provides immutable audit logging functions for all components.

**Features**:
- Logs all Ingestion Engine decisions
- Logs all Bedrock Architect decisions
- Logs all Hostile Auditor decisions
- Logs all Verification Environment decisions
- Logs test failures before any correction attempts
- Structured JSON format with timestamps
- Automatic CloudWatch integration

**Usage**:
```python
from rosetta_zero.utils.logging import (
    log_ingestion_engine_decision,
    log_bedrock_architect_decision,
    log_hostile_auditor_decision,
    log_verification_environment_decision,
    log_test_failure_immutable
)

# Log Ingestion Engine decision
log_ingestion_engine_decision(
    artifact_id="artifact-123",
    decision_type="logic_map_extraction",
    decision="extracted_logic_map",
    details={
        "entry_points": 5,
        "data_structures": 12,
        "side_effects": 3
    }
)

# Log test failure (MUST be called before any correction attempts)
log_test_failure_immutable(
    test_vector_id="test-456",
    legacy_result_hash="abc123...",
    modern_result_hash="def456...",
    discrepancy_report_id="discrepancy-789",
    differences={
        "return_value_match": False,
        "stdout_match": True,
        "stderr_match": True
    }
)
```

### 3. EventBridge Manager

**Module**: `rosetta_zero.utils.monitoring.EventBridgeManager`

Manages EventBridge event publishing and rules.

**Features**:
- Publishes certificate generation events
- Publishes AWS 500-level error events
- Publishes behavioral discrepancy events
- Publishes workflow phase completion events
- Automatic SNS notification triggering

**Usage**:
```python
from rosetta_zero.utils.monitoring import EventBridgeManager

events_manager = EventBridgeManager(event_bus_name="default")

# Publish certificate generation event
events_manager.publish_certificate_event(
    certificate_id="cert-123",
    s3_location="s3://bucket/certificates/cert-123.json",
    total_tests=1000000,
    coverage_percent=98.5
)

# Publish AWS 500-level error event
events_manager.publish_error_event(
    service="bedrock",
    error_code="InternalServerError",
    error_message="Service temporarily unavailable",
    context={"operation": "InvokeModel"}
)

# Publish workflow phase completion event
events_manager.publish_phase_completion_event(
    workflow_id="workflow-123",
    phase_name="Discovery",
    status="SUCCESS",
    details={"artifacts_processed": 1}
)
```

### 4. SNS Notification Manager

**Module**: `rosetta_zero.utils.monitoring.SNSNotificationManager`

Manages SNS notifications for operators.

**Features**:
- Publishes operator alerts with severity levels
- Publishes AWS 500-level error alerts
- Automatic email/SMS notification delivery
- Structured alert messages

**Usage**:
```python
from rosetta_zero.utils.monitoring import SNSNotificationManager

sns_manager = SNSNotificationManager(
    topic_arn="arn:aws:sns:us-east-1:123456789012:rosetta-zero-operator-alerts"
)

# Publish operator alert
sns_manager.publish_operator_alert(
    subject="Test Failure Detected",
    message="Behavioral discrepancy found in test vector test-456",
    severity="HIGH",
    context={"test_vector_id": "test-456"}
)

# Publish AWS 500-level error alert
sns_manager.publish_aws_500_error_alert(
    service="bedrock",
    operation="InvokeModel",
    error_code="InternalServerError",
    error_message="Service temporarily unavailable",
    context={"retry_count": 3}
)
```

### 5. Performance Metrics Publisher

**Module**: `rosetta_zero.utils.monitoring.PerformanceMetricsPublisher`

Publishes performance metrics to CloudWatch.

**Features**:
- Test execution duration metrics
- Test throughput metrics
- AWS service API latency metrics
- Resource utilization metrics
- Automatic CloudWatch integration

**Usage**:
```python
from rosetta_zero.utils.monitoring import PerformanceMetricsPublisher

metrics_publisher = PerformanceMetricsPublisher(namespace="RosettaZero")

# Publish test execution duration
metrics_publisher.publish_test_execution_duration(
    test_id="test-123",
    duration_ms=1500,
    implementation_type="legacy"
)

# Publish test throughput
metrics_publisher.publish_test_throughput(
    tests_per_second=100.5,
    component="verification-environment"
)

# Publish API latency
metrics_publisher.publish_api_latency(
    service="bedrock",
    operation="InvokeModel",
    latency_ms=2500
)

# Publish resource utilization
metrics_publisher.publish_resource_utilization(
    resource_type="CPU",
    utilization_percent=75.5,
    component="hostile-auditor"
)
```

## EventBridge Rules

The following EventBridge rules are configured:

### 1. Certificate Generation Rule
- **Name**: `rosetta-zero-certificate-generated`
- **Event Pattern**: `source: rosetta-zero.certificate-generator, detail-type: Certificate Generated`
- **Target**: SNS topic for operator notification
- **Purpose**: Notify operators when equivalence certificate is generated

### 2. AWS 500-Level Error Rule
- **Name**: `rosetta-zero-aws-500-error`
- **Event Pattern**: `source: rosetta-zero.*, detail-type: AWS 500-Level Error`
- **Target**: SNS topic for critical operator alert
- **Purpose**: Notify operators of AWS service failures requiring intervention

### 3. Behavioral Discrepancy Rule
- **Name**: `rosetta-zero-behavioral-discrepancy`
- **Event Pattern**: `source: rosetta-zero.verification-environment, detail-type: Behavioral Discrepancy Detected`
- **Target**: SNS topic for operator notification
- **Purpose**: Notify operators when test failures are detected

### 4. Workflow Phase Completion Rule
- **Name**: `rosetta-zero-phase-completion`
- **Event Pattern**: `source: rosetta-zero.workflow, detail-type: Workflow Phase Completed`
- **Target**: SNS topic for operator notification
- **Purpose**: Notify operators of workflow progress

## CloudWatch Dashboards

### Main Dashboard: `RosettaZero-Main`

The main dashboard includes the following widgets:

1. **Test Execution Rate**
   - Metric: `RosettaZero/TestThroughput`
   - Shows tests executed per second
   - 5-minute average

2. **Test Pass Rate**
   - Calculated metric: `(pass / (pass + fail)) * 100`
   - Shows percentage of tests passing
   - 5-minute aggregation

3. **Lambda Performance Metrics**
   - Metric: `AWS/Lambda/Duration`
   - Shows average execution duration for all Lambda functions
   - 5-minute average

4. **Fargate Resource Utilization**
   - Metrics: `AWS/ECS/CPUUtilization`, `AWS/ECS/MemoryUtilization`
   - Shows CPU and memory usage for legacy executor
   - 5-minute average

5. **Error Rates by Component**
   - Metric: `AWS/Lambda/Errors`
   - Shows error count for all Lambda functions
   - 5-minute sum

6. **AWS Service API Latency**
   - Metric: `RosettaZero/APILatency`
   - Shows latency for Bedrock, S3, and DynamoDB API calls
   - 5-minute average

## SNS Topics

### Operator Alerts Topic
- **Name**: `rosetta-zero-operator-alerts`
- **Encryption**: KMS encryption enabled
- **Subscriptions**: Configure email/SMS subscriptions manually
- **Purpose**: Deliver critical alerts to operators

**To subscribe operators**:
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:rosetta-zero-operator-alerts \
  --protocol email \
  --notification-endpoint operator@example.com
```

## Log Retention and Encryption

All CloudWatch Log Groups are configured with:
- **Retention**: 2555 days (7 years) for regulatory compliance
- **Encryption**: KMS encryption using customer-managed key
- **Format**: Structured JSON with AWS Lambda PowerTools
- **Immutability**: Logs cannot be modified after creation

## Best Practices

1. **Always log decisions**: Use the immutable audit logging functions for all component decisions
2. **Log failures immediately**: Call `log_test_failure_immutable()` before any correction attempts
3. **Publish events**: Use EventBridge for event-driven notifications
4. **Monitor metrics**: Regularly review CloudWatch dashboards
5. **Subscribe operators**: Ensure operators are subscribed to SNS topics
6. **Review alerts**: Respond to AWS 500-level error alerts promptly

## Troubleshooting

### Logs not appearing in CloudWatch
- Check Lambda function has CloudWatch Logs permissions
- Verify KMS key grants decrypt permissions to CloudWatch Logs
- Check log group retention policy is set

### Events not triggering SNS notifications
- Verify EventBridge rule is enabled
- Check SNS topic has correct permissions
- Verify event pattern matches published events

### Metrics not appearing in dashboards
- Check metrics are being published with correct namespace
- Verify metric dimensions match dashboard configuration
- Allow 5-10 minutes for metrics to appear

## References

- [AWS Lambda PowerTools Documentation](https://docs.powertools.aws.dev/lambda/python/)
- [CloudWatch Logs Encryption](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/encrypt-log-data-kms.html)
- [EventBridge Event Patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html)
- [SNS Message Filtering](https://docs.aws.amazon.com/sns/latest/dg/sns-message-filtering.html)
