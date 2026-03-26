# Bedrock Architect Lambda

The Bedrock Architect is responsible for synthesizing modern AWS Lambda functions from Logic Maps while preserving exact behavioral semantics.

## Overview

The Bedrock Architect uses Amazon Bedrock with Claude 3.5 Sonnet to generate Python 3.12 Lambda functions that:
- Preserve all behavioral logic from the Logic Map
- Maintain arithmetic precision (fixed-point and floating-point)
- Replicate all side effects (file I/O, database operations, etc.)
- Follow AWS Lambda best practices
- Include comprehensive error handling and logging

## Components

### handler.py
Lambda entry point with PowerTools decorators for logging, tracing, and metrics.

### synthesis.py
Main BedrockArchitect class that orchestrates the synthesis process:
1. Reads Logic Map from S3
2. Queries Bedrock Knowledge Bases for language documentation
3. Preserves arithmetic precision requirements
4. Preserves timing behavior
5. Generates Lambda code using Bedrock
6. Validates faithful transpilation
7. Stores generated code in S3
8. Generates CDK infrastructure code

### knowledge_base.py
Bedrock Knowledge Base integration for querying COBOL, FORTRAN, and mainframe documentation.

**Requirements:** 5.1, 5.2, 5.3, 5.4

### precision.py
Arithmetic precision preservation to ensure fixed-point and floating-point operations match legacy system behavior.

**Requirements:** 8.1, 8.2, 8.3, 8.4

### faithful_transpilation.py
Validation to ensure generated code implements only Logic Map behaviors with no feature addition or unauthorized optimization.

**Requirements:** 7.1, 7.2, 7.3, 7.4, 7.5

### timing.py
Timing behavior preservation for legacy systems with timing-dependent logic.

**Requirements:** 22.1, 22.2

### cdk_generator.py
CDK infrastructure code generation for deploying modern Lambda functions.

**Requirements:** 6.7

### error_handler.py
Error handling and retry logic with exponential backoff for Bedrock API failures.

**Requirements:** 19.2, 19.3, 19.4, 25.1, 25.2, 25.3, 25.4, 25.5

## Environment Variables

- `MODERN_IMPLEMENTATIONS_BUCKET`: S3 bucket for generated Lambda code
- `CDK_INFRASTRUCTURE_BUCKET`: S3 bucket for CDK infrastructure code
- `KMS_KEY_ID`: KMS key ID for encryption
- `BEDROCK_MODEL_ID`: Bedrock model ID (default: Claude 3.5 Sonnet)
- `COBOL_KB_ID`: Bedrock Knowledge Base ID for COBOL documentation
- `FORTRAN_KB_ID`: Bedrock Knowledge Base ID for FORTRAN documentation
- `MAINFRAME_KB_ID`: Bedrock Knowledge Base ID for mainframe documentation
- `POWERTOOLS_SERVICE_NAME`: Service name for PowerTools logging
- `POWERTOOLS_METRICS_NAMESPACE`: Namespace for CloudWatch metrics
- `LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR)

## Event Structure

```json
{
  "logic_map_s3_bucket": "rosetta-zero-logic-maps-...",
  "logic_map_s3_key": "logic-maps/artifact-id/version/logic-map.json"
}
```

## Response Structure

```json
{
  "statusCode": 200,
  "body": {
    "artifact_id": "...",
    "modern_implementation_s3_key": "modern-implementations/.../lambda.py",
    "cdk_infrastructure_s3_key": "cdk-infrastructure/.../stack.py",
    "synthesis_timestamp": "2024-01-01T00:00:00Z"
  }
}
```

## IAM Permissions

The Bedrock Architect Lambda requires:
- S3 read access to logic-maps bucket
- S3 write access to modern-implementations and cdk-infrastructure buckets
- `bedrock:InvokeModel` permission for Claude 3.5 Sonnet
- `bedrock:Retrieve` permission for Knowledge Bases
- CloudWatch Logs permissions
- KMS decrypt/encrypt permissions
- SNS publish for operator alerts

## Error Handling

The Bedrock Architect implements comprehensive error handling:

1. **Transient Errors**: Automatically retried with exponential backoff (max 3 attempts)
   - Bedrock throttling
   - Network timeouts
   - AWS 500-level errors

2. **Permanent Errors**: Logged and raised immediately
   - Validation errors
   - Access denied
   - Resource not found

3. **AWS 500-level Errors**: Trigger operator alerts via SNS

## Faithful Transpilation

The Bedrock Architect enforces faithful transpilation constraints:
- No feature addition beyond Logic Map
- No algorithm optimization that changes observable behavior
- No data precision modifications
- All side effects must be preserved

Validation failures halt the pipeline and generate detailed error reports.

## Arithmetic Precision

The Bedrock Architect preserves arithmetic precision:
- Fixed-point operations use Python's `decimal` module
- Floating-point precision matches legacy system (32-bit, 64-bit, 128-bit)
- Rounding modes are preserved (ROUND_HALF_UP, ROUND_HALF_EVEN, etc.)

All arithmetic decisions are documented in generated code comments.

## Timing Behavior

The Bedrock Architect preserves timing behavior:
- Deliberate delays are implemented using `time.sleep()`
- Timing constraints are documented in code comments
- Latency characteristics are simulated when necessary

## Logging

All synthesis decisions are logged to CloudWatch for audit trails:
- Logic Map loaded
- Language documentation queried
- Lambda code generated
- Faithful transpilation validated
- Code stored in S3

Logs are retained for 7+ years for regulatory compliance.

## Testing

Unit tests are located in `tests/test_bedrock_architect.py`.

Run tests:
```bash
pytest tests/test_bedrock_architect.py -v
```

## Deployment

The Bedrock Architect Lambda is deployed via CDK:
```bash
cdk deploy RosettaZeroStack
```

## Monitoring

CloudWatch metrics:
- `SynthesisSuccess`: Count of successful syntheses
- `SynthesisError`: Count of failed syntheses
- `SynthesisDuration`: Duration of synthesis operations

CloudWatch alarms:
- High error rate (>5% of requests)
- Long synthesis duration (>10 minutes)
- AWS 500-level errors

## Requirements Traceability

- **6.1**: Synthesize AWS Lambda functions in Python 3.12
- **6.2**: Follow AWS Lambda best practices
- **6.3**: Implement error handling using AWS Lambda error patterns
- **6.4**: Implement logging using AWS Lambda PowerTools
- **6.5**: Preserve all behavioral logic from Logic Map
- **6.6**: Preserve all side effects identified in Logic Map
- **6.7**: Generate Infrastructure as Code using AWS CDK
- **6.8**: Store Modern_Implementation in Amazon S3
- **7.1-7.5**: Faithful transpilation constraints
- **8.1-8.4**: Arithmetic precision preservation
- **19.2-19.4**: Autonomous operation with retry logic
- **22.1-22.2**: Timing behavior preservation
- **25.1-25.5**: Error recovery with exponential backoff
