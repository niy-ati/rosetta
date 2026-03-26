# Verification Environment

The Verification Environment executes legacy and modern implementations in parallel and compares outputs byte-by-byte to detect behavioral discrepancies.

## Components

### 1. Legacy Binary Executor (Fargate)
- **Location**: `docker/legacy-executor/`
- **Purpose**: Executes legacy binaries in isolated containers
- **Requirements**: 11.2, 11.5, 11.6, 12.1-12.5

**Features**:
- COBOL and FORTRAN runtime support
- File system write capture (inotify)
- Network operation capture (tcpdump)
- stdout/stderr capture
- Return value capture
- Side effect instrumentation

**IAM Permissions**:
- S3 read access to `legacy-artifacts` bucket
- KMS decrypt for S3 objects
- CloudWatch Logs write access

### 2. Modern Lambda Executor
- **Location**: `modern_executor.py`
- **Purpose**: Executes modern Lambda implementations
- **Requirements**: 11.3, 11.5, 11.6

**Features**:
- Lambda invocation with test vectors
- CloudWatch Logs retrieval for stdout/stderr
- Side effect capture (S3, DynamoDB operations)
- Execution duration tracking

### 3. Output Comparator
- **Location**: `comparator.py`
- **Purpose**: Compares outputs byte-by-byte
- **Requirements**: 13.1-13.6, 16.1, 16.2

**Features**:
- Return value comparison
- stdout/stderr byte-by-byte comparison
- Side effect comparison
- Byte-level diff generation with context
- SHA-256 hash computation for integrity

**IAM Permissions**:
- DynamoDB read/write access to `test-results` table
- S3 write access to `discrepancy-reports` bucket
- KMS encrypt/decrypt permissions
- EventBridge PutEvents permission

### 4. Discrepancy Reporter
- **Location**: `discrepancy_reporter.py`
- **Purpose**: Generates detailed reports on test failures
- **Requirements**: 14.1-14.9

**Features**:
- Comprehensive discrepancy reports with:
  - Test vector inputs
  - Legacy and modern outputs
  - Byte-level diffs
  - Execution timestamps
  - Side effects
- S3 storage with KMS encryption
- CloudWatch Logs integration
- EventBridge event publishing
- Pipeline halting on discrepancies

### 5. Test Result Storage
- **Location**: `test_result_storage.py`
- **Purpose**: Stores test results in DynamoDB
- **Requirements**: 15.1-15.6, 16.1, 16.2

**Features**:
- Test result storage with:
  - Test ID and execution timestamp
  - Test vector inputs
  - Execution output hashes (SHA-256)
  - Pass/fail status
  - Execution timestamps
  - Complete test result hash
- DynamoDB with point-in-time recovery
- KMS encryption

### 6. Orchestrator
- **Location**: `orchestrator.py`
- **Purpose**: Orchestrates parallel test execution
- **Requirements**: 11.1, 11.4

**Features**:
- Reads test vector batches from S3
- Invokes Step Functions for each test vector
- Handles parallel execution (configurable limit)
- Aggregates test results
- Throttling and backoff

### 7. Error Handler
- **Location**: `error_handler.py`
- **Purpose**: Handles verification errors
- **Requirements**: 19.2, 19.3, 19.4, 25.1-25.5

**Features**:
- Fargate failure handling
- Lambda failure handling
- Step Functions error handling
- AWS 500-level error detection
- Operator alert publishing (SNS)
- Execution failure report generation
- Pipeline halting on behavioral discrepancies
- Retry logic for transient errors

## Step Functions State Machine

**Location**: Defined in CDK stack (`infrastructure/rosetta_zero_stack.py`)

**Workflow**:
1. **Parallel Execution**:
   - Branch 1: Execute legacy binary in Fargate
   - Branch 2: Execute modern Lambda
2. **Compare Outputs**: Invoke comparator Lambda
3. **Check Match Status**: Choice state
4. **On Pass**: Success state (result stored by comparator)
5. **On Fail**: Fail state (discrepancy report generated, pipeline halted)

**Requirements**: 11.1, 11.4, 11.7, 18.5, 18.6

**IAM Permissions**:
- ECS RunTask, StopTask, DescribeTasks
- Lambda Invoke
- IAM PassRole for Fargate task roles
- CloudWatch Logs write access

## IAM Roles and Policies

### Fargate Task Execution Role
**Purpose**: Allows ECS to pull container images and write logs

**Permissions**:
- ECR pull permissions (AmazonECSTaskExecutionRolePolicy)
- CloudWatch Logs write access
- KMS decrypt for CloudWatch Logs

### Fargate Task Role
**Purpose**: Allows container to access AWS services

**Permissions** (Requirement 21.1):
- S3 read access to `legacy-artifacts` bucket
- KMS decrypt for S3 objects

### Comparator Lambda Role
**Purpose**: Allows comparator to store results and generate reports

**Permissions** (Requirements 21.1, 21.2, 21.3):
- DynamoDB read/write access to `test-results` table
- S3 write access to `discrepancy-reports` bucket
- CloudWatch Logs write access
- KMS encrypt/decrypt permissions
- EventBridge PutEvents permission
- VPC execution permissions

### Step Functions Execution Role
**Purpose**: Allows state machine to invoke Lambda and run Fargate tasks

**Permissions** (Requirement 21.3):
- ECS RunTask, StopTask, DescribeTasks
- Lambda Invoke
- IAM PassRole for Fargate task roles
- CloudWatch Logs write access

## Environment Variables

### Comparator Lambda
- `TEST_RESULTS_TABLE`: DynamoDB table name
- `DISCREPANCY_BUCKET`: S3 bucket for discrepancy reports
- `KMS_KEY_ID`: KMS key ID for encryption
- `EVENT_BUS_NAME`: EventBridge event bus name
- `POWERTOOLS_SERVICE_NAME`: Service name for logging
- `LOG_LEVEL`: Logging level

### Orchestrator Lambda
- `TEST_VECTORS_BUCKET`: S3 bucket for test vectors
- `STATE_MACHINE_ARN`: Step Functions state machine ARN
- `MAX_PARALLEL_EXECUTIONS`: Maximum parallel executions

### Error Handler
- `OPERATOR_ALERTS_TOPIC_ARN`: SNS topic ARN for operator alerts
- `EVENT_BUS_NAME`: EventBridge event bus name
- `DISCREPANCY_BUCKET`: S3 bucket for failure reports

## Deployment

The Verification Environment is deployed using AWS CDK:

```bash
# Deploy infrastructure
cdk deploy

# Build and push Docker image
cd docker/legacy-executor
docker build -t rosetta-zero/legacy-executor:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag rosetta-zero/legacy-executor:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/rosetta-zero-legacy-executor:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/rosetta-zero-legacy-executor:latest
```

## Testing

Run verification tests:

```bash
pytest tests/test_verification.py -v
```

## Monitoring

- **CloudWatch Logs**: All Lambda functions and Fargate tasks log to CloudWatch with 7-year retention
- **CloudWatch Metrics**: Custom metrics published for test execution rate, pass rate, duration
- **EventBridge Events**: Events published for discrepancies, failures, and AWS 500 errors
- **SNS Alerts**: Operator alerts for AWS 500-level errors

## Security

- **Network Isolation**: All resources run in VPC private subnets with no internet access
- **Encryption at Rest**: All data encrypted with KMS customer-managed keys
- **Encryption in Transit**: All AWS API calls use TLS 1.3
- **Least Privilege IAM**: All roles follow least-privilege principle
- **Audit Logging**: All decisions logged to CloudWatch with 7-year retention
