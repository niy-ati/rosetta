# Legacy Binary Executor Docker Container

This Docker container executes legacy binaries (COBOL, FORTRAN, mainframe) in an isolated environment with comprehensive side effect capture.

## Features

- **Legacy Runtime Support**: COBOL (GnuCOBOL), FORTRAN (gfortran)
- **Side Effect Capture**:
  - File system writes (using inotify)
  - Network operations (using tcpdump)
  - stdout/stderr capture
  - Return value capture
- **AWS Integration**: Downloads binaries from S3, uses PowerTools for logging
- **Isolated Execution**: Runs in Fargate with no internet access

## Building the Image

```bash
docker build -t rosetta-zero/legacy-executor:latest .
```

## Running Locally

```bash
# Create test vector JSON
cat > test_vector.json <<EOF
{
  "vector_id": "test-001",
  "binary_s3_bucket": "rosetta-zero-legacy-artifacts",
  "binary_s3_key": "binaries/sample.cob",
  "input_parameters": {
    "param1": "value1",
    "param2": 42
  }
}
EOF

# Run container
docker run --rm \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -e TEST_VECTOR="$(cat test_vector.json)" \
  rosetta-zero/legacy-executor:latest
```

## Pushing to ECR

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Tag image
docker tag rosetta-zero/legacy-executor:latest \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/rosetta-zero-legacy-executor:latest

# Push image
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/rosetta-zero-legacy-executor:latest
```

## Output Format

The container outputs a JSON object to stdout:

```json
{
  "test_vector_id": "test-001",
  "implementation_type": "LEGACY",
  "execution_timestamp": "2024-01-15T10:30:00.000Z",
  "return_value": 0,
  "stdout": "48656c6c6f",
  "stderr": "",
  "side_effects": {
    "file_writes": [
      {
        "timestamp": 1705318200,
        "event": "CREATE",
        "filepath": "/app/output/result.txt",
        "content_hash": "abc123...",
        "content": "base64-encoded-content"
      }
    ],
    "network_operations": [],
    "execution_duration_ms": 150
  },
  "execution_duration_ms": 150,
  "error": null
}
```

## Requirements

- Docker 20.10+
- AWS credentials with S3 read access
- ECR repository for image storage
