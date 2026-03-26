# Workflow Phase Completion Event Publishing

## Overview

This document describes the implementation of workflow phase completion event publishing for Rosetta Zero. When a workflow phase completes (Discovery, Synthesis, Aggression, Validation, Trust), the system publishes an event to Amazon EventBridge to enable event-driven orchestration of subsequent phases.

**Requirements:** 24.6

## Architecture

### Components

1. **WorkflowPhaseTracker** (`rosetta_zero/utils/workflow.py`)
   - Tracks workflow phase status in DynamoDB
   - Publishes phase completion events to EventBridge
   - Manages phase transitions

2. **EventBridgeManager** (`rosetta_zero/utils/monitoring.py`)
   - Publishes events to EventBridge
   - Provides `publish_phase_completion_event()` method

3. **DynamoDB Table** (`rosetta-zero-workflow-phases`)
   - Stores workflow phase status
   - Schema: `workflow_id` (PK), `phase_name` (SK)
   - Tracks: status, start_time, end_time, completion_details

### Workflow Phases

The system tracks five sequential phases:

1. **Discovery** - Ingestion Engine extracts Logic Maps
2. **Synthesis** - Bedrock Architect generates modern Lambda code
3. **Aggression** - Hostile Auditor generates test vectors
4. **Validation** - Verification Environment executes tests
5. **Trust** - Certificate Generator produces equivalence certificate

## Implementation

### Complete Phase Method

The `complete_phase()` method performs three key operations:

```python
def complete_phase(
    self,
    workflow_id: str,
    phase: WorkflowPhase,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Mark a phase as completed and publish completion event to EventBridge.
    
    Requirements: 24.6
    
    Args:
        workflow_id: Workflow identifier
        phase: Phase to complete
        details: Phase completion details (e.g., artifact locations, metrics)
        
    Returns:
        Phase completion result including event publication details
    """
```

#### Operation 1: Update DynamoDB

Updates the phase status in DynamoDB:

```python
self.table.update_item(
    Key={
        'workflow_id': workflow_id,
        'phase_name': phase.value
    },
    UpdateExpression='SET #status = :status, end_time = :end_time, updated_at = :updated_at, completion_details = :details',
    ExpressionAttributeNames={
        '#status': 'status'
    },
    ExpressionAttributeValues={
        ':status': PhaseStatus.COMPLETED.value,
        ':end_time': timestamp,
        ':updated_at': timestamp,
        ':details': details or {}
    },
    ReturnValues='ALL_NEW'
)
```

#### Operation 2: Publish EventBridge Event

Publishes phase completion event:

```python
event_result = self.event_manager.publish_phase_completion_event(
    workflow_id=workflow_id,
    phase_name=phase.value,
    status='SUCCESS',
    details={
        'completion_timestamp': timestamp,
        'phase_details': details or {},
        'next_phase': self._get_next_phase(phase)
    }
)
```

#### Operation 3: Return Result

Returns comprehensive result:

```python
return {
    'workflow_id': workflow_id,
    'phase': phase.value,
    'status': PhaseStatus.COMPLETED.value,
    'end_time': timestamp,
    'event_published': True,
    'event_id': event_result.get('event_id'),
    'next_phase': self._get_next_phase(phase)
}
```

### Event Structure

EventBridge events have the following structure:

```json
{
  "Source": "rosetta-zero.workflow",
  "DetailType": "Workflow Phase Completed",
  "Detail": {
    "workflow_id": "workflow-123",
    "phase_name": "Discovery",
    "status": "SUCCESS",
    "details": {
      "completion_timestamp": "2024-01-15T10:30:00.000000",
      "phase_details": {
        "logic_map_location": "s3://bucket/logic-maps/test.json",
        "artifacts_processed": 1
      },
      "next_phase": "Synthesis"
    },
    "timestamp": "2024-01-15T10:30:00.000000"
  }
}
```

## Usage Examples

### Example 1: Complete Discovery Phase

```python
from rosetta_zero.utils.workflow import WorkflowPhaseTracker, WorkflowPhase

tracker = WorkflowPhaseTracker()

result = tracker.complete_phase(
    workflow_id='workflow-cobol-banking-001',
    phase=WorkflowPhase.DISCOVERY,
    details={
        'logic_map_location': 's3://rosetta-zero-logic-maps/cobol-banking-001/logic-map.json',
        'ears_document_location': 's3://rosetta-zero-ears-requirements/cobol-banking-001/ears.md',
        'artifacts_processed': 1,
        'side_effects_detected': 12,
        'entry_points_found': 8
    }
)

print(f"Phase: {result['phase']}")
print(f"Status: {result['status']}")
print(f"Event published: {result['event_published']}")
print(f"Next phase: {result['next_phase']}")
```

### Example 2: Complete Synthesis Phase

```python
result = tracker.complete_phase(
    workflow_id='workflow-cobol-banking-001',
    phase=WorkflowPhase.SYNTHESIS,
    details={
        'lambda_code_location': 's3://rosetta-zero-modern-implementations/cobol-banking-001/lambda.py',
        'functions_generated': 8,
        'arithmetic_precision_preserved': True
    }
)
```

### Example 3: Complete All Phases

```python
phases = [
    (WorkflowPhase.DISCOVERY, {'logic_map_location': 's3://...'}),
    (WorkflowPhase.SYNTHESIS, {'lambda_code_location': 's3://...'}),
    (WorkflowPhase.AGGRESSION, {'test_vectors_generated': 1000000}),
    (WorkflowPhase.VALIDATION, {'tests_passed': 1000000}),
    (WorkflowPhase.TRUST, {'certificate_id': 'cert-001'})
]

for phase, details in phases:
    tracker.start_phase(workflow_id, phase)
    result = tracker.complete_phase(workflow_id, phase, details)
    print(f"Completed: {result['phase']}")
```

## Event-Driven Orchestration

### EventBridge Rules

Configure EventBridge rules to automatically trigger the next phase:

#### Rule 1: Discovery → Synthesis

```json
{
  "Name": "rosetta-zero-discovery-to-synthesis",
  "EventPattern": {
    "source": ["rosetta-zero.workflow"],
    "detail-type": ["Workflow Phase Completed"],
    "detail": {
      "phase_name": ["Discovery"],
      "status": ["SUCCESS"]
    }
  },
  "Targets": [
    {
      "Arn": "arn:aws:lambda:us-east-1:123456789012:function:bedrock-architect",
      "Input": {
        "workflow_id": "$.detail.workflow_id",
        "phase": "Synthesis"
      }
    }
  ]
}
```

#### Rule 2: Synthesis → Aggression

```json
{
  "Name": "rosetta-zero-synthesis-to-aggression",
  "EventPattern": {
    "source": ["rosetta-zero.workflow"],
    "detail-type": ["Workflow Phase Completed"],
    "detail": {
      "phase_name": ["Synthesis"],
      "status": ["SUCCESS"]
    }
  },
  "Targets": [
    {
      "Arn": "arn:aws:lambda:us-east-1:123456789012:function:hostile-auditor"
    }
  ]
}
```

#### Rule 3: Aggression → Validation

```json
{
  "Name": "rosetta-zero-aggression-to-validation",
  "EventPattern": {
    "source": ["rosetta-zero.workflow"],
    "detail-type": ["Workflow Phase Completed"],
    "detail": {
      "phase_name": ["Aggression"],
      "status": ["SUCCESS"]
    }
  },
  "Targets": [
    {
      "Arn": "arn:aws:states:us-east-1:123456789012:stateMachine:verification-orchestrator"
    }
  ]
}
```

#### Rule 4: Validation → Trust

```json
{
  "Name": "rosetta-zero-validation-to-trust",
  "EventPattern": {
    "source": ["rosetta-zero.workflow"],
    "detail-type": ["Workflow Phase Completed"],
    "detail": {
      "phase_name": ["Validation"],
      "status": ["SUCCESS"]
    }
  },
  "Targets": [
    {
      "Arn": "arn:aws:lambda:us-east-1:123456789012:function:certificate-generator"
    }
  ]
}
```

### Workflow Sequence

```
┌─────────────┐
│  Discovery  │ ──┐
└─────────────┘   │
                  ▼
            EventBridge Event
                  │
                  ▼
┌─────────────┐   │
│  Synthesis  │ ◄─┘
└─────────────┘   │
                  ▼
            EventBridge Event
                  │
                  ▼
┌─────────────┐   │
│ Aggression  │ ◄─┘
└─────────────┘   │
                  ▼
            EventBridge Event
                  │
                  ▼
┌─────────────┐   │
│ Validation  │ ◄─┘
└─────────────┘   │
                  ▼
            EventBridge Event
                  │
                  ▼
┌─────────────┐   │
│    Trust    │ ◄─┘
└─────────────┘
```

## Integration with Lambda Functions

### Ingestion Engine Lambda

```python
def lambda_handler(event, context):
    """Ingestion Engine Lambda handler."""
    
    # Extract Logic Map
    logic_map = extract_logic_map(artifact)
    
    # Store Logic Map in S3
    s3_location = store_logic_map(logic_map)
    
    # Complete Discovery phase
    tracker = WorkflowPhaseTracker()
    result = tracker.complete_phase(
        workflow_id=event['workflow_id'],
        phase=WorkflowPhase.DISCOVERY,
        details={
            'logic_map_location': s3_location,
            'artifacts_processed': 1
        }
    )
    
    return result
```

### Bedrock Architect Lambda

```python
def lambda_handler(event, context):
    """Bedrock Architect Lambda handler."""
    
    # Triggered by Discovery completion event
    workflow_id = event['detail']['workflow_id']
    
    # Generate modern Lambda code
    lambda_code = synthesize_lambda(logic_map)
    
    # Store code in S3
    s3_location = store_lambda_code(lambda_code)
    
    # Complete Synthesis phase
    tracker = WorkflowPhaseTracker()
    result = tracker.complete_phase(
        workflow_id=workflow_id,
        phase=WorkflowPhase.SYNTHESIS,
        details={
            'lambda_code_location': s3_location,
            'functions_generated': 8
        }
    )
    
    return result
```

## Testing

Unit tests are provided in `tests/test_workflow_phase_completion.py`:

```bash
python -m pytest tests/test_workflow_phase_completion.py -v
```

Test coverage includes:
- DynamoDB update verification
- EventBridge event publishing
- Result structure validation
- Phase sequence verification
- Error handling
- Edge cases (last phase, no details)

## Monitoring

### CloudWatch Logs

All phase completions are logged:

```json
{
  "level": "INFO",
  "message": "Phase completed",
  "workflow_id": "workflow-123",
  "phase": "Discovery",
  "status": "COMPLETED",
  "timestamp": "2024-01-15T10:30:00.000000"
}
```

### CloudWatch Metrics

Publish custom metrics for phase completion:

```python
from aws_lambda_powertools import Metrics

metrics = Metrics()
metrics.add_metric(name="PhaseCompleted", unit="Count", value=1)
metrics.add_dimension(name="Phase", value=phase.value)
```

### EventBridge Event History

Query EventBridge for phase completion events:

```bash
aws events list-archives \
  --event-source-arn arn:aws:events:us-east-1:123456789012:event-bus/default \
  --name-prefix rosetta-zero
```

## Error Handling

### DynamoDB Errors

```python
try:
    result = tracker.complete_phase(workflow_id, phase, details)
except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceNotFoundException':
        # Workflow not found
        logger.error("Workflow not found", extra={'workflow_id': workflow_id})
    elif e.response['Error']['Code'] == 'ConditionalCheckFailedException':
        # Phase already completed
        logger.warning("Phase already completed", extra={'phase': phase.value})
    else:
        # Other errors
        raise
```

### EventBridge Errors

EventBridge errors are logged and re-raised:

```python
try:
    event_result = self.event_manager.publish_phase_completion_event(...)
except ClientError as e:
    log_error(
        component='workflow_phase_tracker',
        error_type=e.response['Error']['Code'],
        error_message=str(e)
    )
    raise
```

## Best Practices

1. **Always include details**: Provide comprehensive phase completion details for audit trails
2. **Check next_phase**: Use the returned `next_phase` to verify workflow sequence
3. **Monitor events**: Set up CloudWatch alarms for failed phase completions
4. **Idempotency**: Ensure phase completion is idempotent (safe to retry)
5. **Error handling**: Always handle DynamoDB and EventBridge errors

## Related Documentation

- [Workflow Phase Tracking](./WORKFLOW.md)
- [EventBridge Integration](./MONITORING.md)
- [DynamoDB Schema](../../infrastructure/README.md)
- [Requirements 24.6](../../.kiro/specs/rosetta-zero/requirements.md)

## References

- AWS EventBridge: https://docs.aws.amazon.com/eventbridge/
- AWS DynamoDB: https://docs.aws.amazon.com/dynamodb/
- AWS Lambda: https://docs.aws.amazon.com/lambda/
