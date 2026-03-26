# Ingestion Engine Lambda - Discovery Phase

## Overview

The Ingestion Engine is the first phase (Discovery Phase) of the Rosetta Zero system. It analyzes legacy artifacts (COBOL, FORTRAN, mainframe binaries) and extracts behavioral logic into implementation-agnostic Logic Maps.

## Components

### 1. Handler (`handler.py`)
- Lambda entry point with PowerTools decorators
- Handles event parsing and response formatting
- Integrates logging, tracing, and metrics

### 2. Ingestion Engine (`ingestion.py`)
- Main orchestration class
- Coordinates artifact ingestion workflow
- Generates SHA-256 hashes for integrity
- Stores artifact metadata

### 3. PII Scanner (`pii_scanner.py`)
- Amazon Macie integration for PII detection
- Automatic PII redaction before analysis
- PII detection report generation
- Requirements: 20.1, 20.2, 20.3, 20.4, 20.5

### 4. Logic Map Extractor (`logic_map_extractor.py`)
- Amazon Bedrock integration (Claude 3.5 Sonnet)
- Structured prompt construction for behavioral analysis
- Logic Map parsing and validation
- S3 storage with versioning
- Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7

### 5. EARS Generator (`ears_generator.py`)
- EARS-compliant requirements generation
- Structured format: WHEN/WHERE/IF ... THE system SHALL ...
- Markdown document generation
- S3 storage
- Requirements: 3.1, 3.2, 3.3, 3.4

### 6. Error Handler (`error_handler.py`)
- Retry logic with exponential backoff
- Bedrock throttling handling
- AWS 500-level error detection and operator alerts
- Macie error handling
- Requirements: 19.2, 19.3, 19.4, 25.1, 25.2, 25.3, 25.4, 25.5

## Workflow

1. **Artifact Ingestion**
   - Read artifact from S3
   - Generate SHA-256 hash
   - Store metadata

2. **PII Detection & Redaction**
   - Scan with Amazon Macie
   - Redact detected PII
   - Store PII report

3. **Logic Map Extraction**
   - Invoke Bedrock with structured prompt
   - Parse response into LogicMap dataclass
   - Validate completeness
   - Store in S3

4. **EARS Generation**
   - Generate EARS requirements from Logic Map
   - Format as markdown
   - Store in S3

## Configuration

Environment variables:
- `AWS_REGION`: AWS region
- `LOGIC_MAPS_BUCKET`: S3 bucket for Logic Maps
- `EARS_BUCKET`: S3 bucket for EARS documents
- `KMS_KEY_ID`: KMS key for encryption
- `POWERTOOLS_SERVICE_NAME`: Service name for PowerTools
- `POWERTOOLS_METRICS_NAMESPACE`: Metrics namespace
- `LOG_LEVEL`: Logging level

## Lambda Configuration

- **Runtime**: Python 3.12
- **Timeout**: 15 minutes
- **Memory**: 3008 MB
- **VPC**: Private isolated subnets
- **Log Retention**: 10 years (7+ for compliance)

## IAM Permissions

- S3 read: legacy-artifacts bucket
- S3 write: logic-maps, ears-requirements buckets
- Bedrock: InvokeModel for Claude 3.5 Sonnet
- Macie: Classification jobs and findings
- CloudWatch Logs: Create and write logs
- KMS: Encrypt/decrypt with customer-managed key
- SNS: Publish operator alerts
- SSM: Read parameter for SNS topic ARN

## Error Handling

- **Transient errors**: Retry up to 3 times with exponential backoff
- **AWS 500 errors**: Notify operators via SNS, retry
- **Bedrock throttling**: Exponential backoff retry
- **Macie failures**: Exponential backoff retry
- **Permanent errors**: Log and fail

## Testing

Unit tests should cover:
- Artifact ingestion with valid COBOL, FORTRAN, binary files
- PII detection and redaction
- Logic Map extraction and validation
- EARS generation
- Error handling for invalid artifacts

## Requirements Satisfied

- 1.1, 1.2, 1.3, 1.4: Legacy code ingestion
- 2.1-2.7: Structural analysis and Logic Map extraction
- 3.1-3.4: EARS requirements generation
- 4.1-4.6: Side effect detection
- 19.2, 19.3, 19.4: Autonomous operation and error handling
- 20.1-20.5: PII data scrubbing
- 21.1, 21.2, 21.3: Secure data transit
- 25.1-25.5: Error recovery
