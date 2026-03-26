"""
Autonomous Workflow Orchestrator Lambda Handler.

Coordinates all five workflow phases without human intervention:
1. Discovery (Ingestion Engine)
2. Synthesis (Bedrock Architect)
3. Aggression (Hostile Auditor)
4. Validation (Verification Environment)
5. Trust (Certificate Generator)

Requirements: 19.1
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

from rosetta_zero.utils.logging import logger, log_error
from rosetta_zero.utils.workflow import WorkflowPhaseTracker, WorkflowPhase
from rosetta_zero.utils.retry import RetryStrategy, TransientError
from rosetta_zero.utils.error_recovery import EnhancedRetryStrategy

# Initialize utilities
tracer = Tracer()
# Use enhanced retry strategy with AWS 500-level error detection and SNS notifications
# Requirements: 19.2, 19.3, 19.4, 19.5, 25.1, 25.2, 25.3, 25.4, 25.5
retry_strategy = EnhancedRetryStrategy(
    max_retries=3,
    base_delay_seconds=2,
    component_name='workflow_orchestrator'
)

# Lazy-load AWS clients to avoid initialization issues during testing
_lambda_client = None
_s3_client = None
_workflow_tracker = None


def get_lambda_client():
    """Get or create Lambda client."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client('lambda')
    return _lambda_client


def get_s3_client():
    """Get or create S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client


def get_workflow_tracker():
    """Get or create workflow tracker."""
    global _workflow_tracker
    if _workflow_tracker is None:
        _workflow_tracker = WorkflowPhaseTracker()
    return _workflow_tracker


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def orchestrator_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main orchestrator handler for autonomous workflow execution.
    
    Handles two types of events:
    1. S3 upload events (artifact upload) - triggers Discovery phase
    2. EventBridge phase completion events - triggers next phase
    
    Args:
        event: Lambda event (S3 or EventBridge)
        context: Lambda context
        
    Returns:
        Orchestration result
    """
    logger.info("Orchestrator invoked", extra={"event": event})
    
    try:
        # Determine event type and route accordingly
        if "Records" in event and event["Records"]:
            # S3 upload event - trigger Discovery phase
            return handle_artifact_upload(event)
        elif "detail-type" in event and event["detail-type"] == "Workflow Phase Completed":
            # EventBridge phase completion event - trigger next phase
            return handle_phase_completion(event)
        else:
            logger.error("Unknown event type", extra={"event": event})
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Unknown event type"})
            }
    
    except Exception as e:
        log_error(
            component='workflow_orchestrator',
            error_type=type(e).__name__,
            error_message=str(e),
            context={'event': event}
        )
        raise


def handle_artifact_upload(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle S3 artifact upload event and trigger Discovery phase.
    
    Requirements: 19.1
    
    Args:
        event: S3 upload event
        
    Returns:
        Discovery phase trigger result
    """
    logger.info("Handling artifact upload event")
    
    # Extract S3 information from event
    record = event["Records"][0]
    bucket_name = record["s3"]["bucket"]["name"]
    object_key = record["s3"]["object"]["key"]
    
    # Generate workflow ID
    workflow_id = f"workflow-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{object_key.split('/')[-1]}"
    artifact_id = object_key.split('/')[-1]
    
    logger.info(
        "Artifact uploaded",
        extra={
            "workflow_id": workflow_id,
            "artifact_id": artifact_id,
            "bucket": bucket_name,
            "key": object_key
        }
    )
    
    # Create workflow and initialize phases
    get_workflow_tracker().create_workflow(
        workflow_id=workflow_id,
        artifact_id=artifact_id,
        metadata={
            "s3_bucket": bucket_name,
            "s3_key": object_key,
            "upload_timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Start Discovery phase
    get_workflow_tracker().start_phase(workflow_id, WorkflowPhase.DISCOVERY)
    
    # Trigger Ingestion Engine Lambda
    ingestion_result = trigger_ingestion_engine(
        workflow_id=workflow_id,
        bucket_name=bucket_name,
        object_key=object_key
    )
    
    logger.info(
        "Discovery phase triggered",
        extra={
            "workflow_id": workflow_id,
            "ingestion_request_id": ingestion_result.get("request_id")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "phase": "Discovery",
            "status": "triggered",
            "ingestion_request_id": ingestion_result.get("request_id")
        })
    }


def handle_phase_completion(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle workflow phase completion event and trigger next phase.
    
    Requirements: 19.1
    
    Args:
        event: EventBridge phase completion event
        
    Returns:
        Next phase trigger result
    """
    detail = event["detail"]
    workflow_id = detail["workflow_id"]
    completed_phase = detail["phase_name"]
    phase_details = detail.get("details", {})
    
    logger.info(
        "Handling phase completion",
        extra={
            "workflow_id": workflow_id,
            "completed_phase": completed_phase
        }
    )
    
    # Determine next phase and trigger appropriate Lambda
    if completed_phase == "Discovery":
        return trigger_synthesis_phase(workflow_id, phase_details)
    elif completed_phase == "Synthesis":
        return trigger_aggression_phase(workflow_id, phase_details)
    elif completed_phase == "Aggression":
        return trigger_validation_phase(workflow_id, phase_details)
    elif completed_phase == "Validation":
        return trigger_trust_phase(workflow_id, phase_details)
    elif completed_phase == "Trust":
        return handle_workflow_completion(workflow_id, phase_details)
    else:
        logger.error(
            "Unknown phase completed",
            extra={"workflow_id": workflow_id, "phase": completed_phase}
        )
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Unknown phase: {completed_phase}"})
        }


def trigger_ingestion_engine(
    workflow_id: str,
    bucket_name: str,
    object_key: str
) -> Dict[str, Any]:
    """
    Trigger Ingestion Engine Lambda for Discovery phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        bucket_name: S3 bucket containing artifact
        object_key: S3 object key for artifact
        
    Returns:
        Ingestion Engine invocation result
    """
    ingestion_lambda_name = os.environ.get(
        'INGESTION_ENGINE_FUNCTION_NAME',
        'rosetta-zero-ingestion-engine'
    )
    
    payload = {
        "workflow_id": workflow_id,
        "s3_bucket": bucket_name,
        "s3_key": object_key
    }
    
    def invoke_lambda():
        response = get_lambda_client().invoke(
            FunctionName=ingestion_lambda_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return {
            "request_id": response['ResponseMetadata']['RequestId'],
            "status_code": response['StatusCode']
        }
    
    return retry_strategy.execute_with_retry(
        invoke_lambda,
        operation_name='trigger_ingestion_engine'
    )


def trigger_synthesis_phase(
    workflow_id: str,
    discovery_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Trigger Bedrock Architect Lambda for Synthesis phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        discovery_details: Details from Discovery phase (Logic Map location)
        
    Returns:
        Bedrock Architect invocation result
    """
    logger.info(
        "Triggering Synthesis phase",
        extra={"workflow_id": workflow_id}
    )
    
    # Start Synthesis phase
    get_workflow_tracker().start_phase(workflow_id, WorkflowPhase.SYNTHESIS)
    
    architect_lambda_name = os.environ.get(
        'BEDROCK_ARCHITECT_FUNCTION_NAME',
        'rosetta-zero-bedrock-architect'
    )
    
    payload = {
        "workflow_id": workflow_id,
        "logic_map_location": discovery_details.get("logic_map_location")
    }
    
    def invoke_lambda():
        response = get_lambda_client().invoke(
            FunctionName=architect_lambda_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return {
            "request_id": response['ResponseMetadata']['RequestId'],
            "status_code": response['StatusCode']
        }
    
    result = retry_strategy.execute_with_retry(
        invoke_lambda,
        operation_name='trigger_synthesis_phase'
    )
    
    logger.info(
        "Synthesis phase triggered",
        extra={
            "workflow_id": workflow_id,
            "request_id": result.get("request_id")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "phase": "Synthesis",
            "status": "triggered",
            "request_id": result.get("request_id")
        })
    }


def trigger_aggression_phase(
    workflow_id: str,
    synthesis_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Trigger Hostile Auditor Lambda for Aggression phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        synthesis_details: Details from Synthesis phase (modern implementation location)
        
    Returns:
        Hostile Auditor invocation result
    """
    logger.info(
        "Triggering Aggression phase",
        extra={"workflow_id": workflow_id}
    )
    
    # Start Aggression phase
    get_workflow_tracker().start_phase(workflow_id, WorkflowPhase.AGGRESSION)
    
    auditor_lambda_name = os.environ.get(
        'HOSTILE_AUDITOR_FUNCTION_NAME',
        'rosetta-zero-hostile-auditor'
    )
    
    payload = {
        "workflow_id": workflow_id,
        "logic_map_location": synthesis_details.get("logic_map_location"),
        "modern_implementation_location": synthesis_details.get("modern_implementation_location")
    }
    
    def invoke_lambda():
        response = get_lambda_client().invoke(
            FunctionName=auditor_lambda_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return {
            "request_id": response['ResponseMetadata']['RequestId'],
            "status_code": response['StatusCode']
        }
    
    result = retry_strategy.execute_with_retry(
        invoke_lambda,
        operation_name='trigger_aggression_phase'
    )
    
    logger.info(
        "Aggression phase triggered",
        extra={
            "workflow_id": workflow_id,
            "request_id": result.get("request_id")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "phase": "Aggression",
            "status": "triggered",
            "request_id": result.get("request_id")
        })
    }


def trigger_validation_phase(
    workflow_id: str,
    aggression_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Trigger Verification Environment (Step Functions) for Validation phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        aggression_details: Details from Aggression phase (test vectors location)
        
    Returns:
        Step Functions execution result
    """
    logger.info(
        "Triggering Validation phase",
        extra={"workflow_id": workflow_id}
    )
    
    # Start Validation phase
    get_workflow_tracker().start_phase(workflow_id, WorkflowPhase.VALIDATION)
    
    # Trigger Step Functions state machine for parallel test execution
    sfn_client = boto3.client('stepfunctions')
    state_machine_arn = os.environ.get(
        'VERIFICATION_STATE_MACHINE_ARN',
        f'arn:aws:states:{os.environ.get("AWS_REGION")}:{os.environ.get("AWS_ACCOUNT_ID")}:stateMachine:rosetta-zero-verification'
    )
    
    execution_input = {
        "workflow_id": workflow_id,
        "test_vectors_location": aggression_details.get("test_vectors_location"),
        "legacy_artifact_location": aggression_details.get("legacy_artifact_location"),
        "modern_implementation_location": aggression_details.get("modern_implementation_location")
    }
    
    def start_execution():
        response = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"{workflow_id}-validation",
            input=json.dumps(execution_input)
        )
        return {
            "execution_arn": response['executionArn'],
            "start_date": response['startDate'].isoformat()
        }
    
    result = retry_strategy.execute_with_retry(
        start_execution,
        operation_name='trigger_validation_phase'
    )
    
    logger.info(
        "Validation phase triggered",
        extra={
            "workflow_id": workflow_id,
            "execution_arn": result.get("execution_arn")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "phase": "Validation",
            "status": "triggered",
            "execution_arn": result.get("execution_arn")
        })
    }


def trigger_trust_phase(
    workflow_id: str,
    validation_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Trigger Certificate Generator Lambda for Trust phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        validation_details: Details from Validation phase (all tests passed)
        
    Returns:
        Certificate Generator invocation result
    """
    logger.info(
        "Triggering Trust phase",
        extra={"workflow_id": workflow_id}
    )
    
    # Start Trust phase
    get_workflow_tracker().start_phase(workflow_id, WorkflowPhase.TRUST)
    
    cert_lambda_name = os.environ.get(
        'CERTIFICATE_GENERATOR_FUNCTION_NAME',
        'rosetta-zero-certificate-generator'
    )
    
    payload = {
        "workflow_id": workflow_id,
        "test_results_summary": validation_details.get("test_results_summary"),
        "total_tests": validation_details.get("total_tests"),
        "coverage_report": validation_details.get("coverage_report")
    }
    
    def invoke_lambda():
        response = get_lambda_client().invoke(
            FunctionName=cert_lambda_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        return {
            "request_id": response['ResponseMetadata']['RequestId'],
            "status_code": response['StatusCode']
        }
    
    result = retry_strategy.execute_with_retry(
        invoke_lambda,
        operation_name='trigger_trust_phase'
    )
    
    logger.info(
        "Trust phase triggered",
        extra={
            "workflow_id": workflow_id,
            "request_id": result.get("request_id")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "phase": "Trust",
            "status": "triggered",
            "request_id": result.get("request_id")
        })
    }


def handle_workflow_completion(
    workflow_id: str,
    trust_details: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Handle workflow completion after Trust phase.
    
    Requirements: 19.1
    
    Args:
        workflow_id: Workflow identifier
        trust_details: Details from Trust phase (certificate location)
        
    Returns:
        Workflow completion result
    """
    logger.info(
        "Workflow completed successfully",
        extra={
            "workflow_id": workflow_id,
            "certificate_location": trust_details.get("certificate_location")
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "workflow_id": workflow_id,
            "status": "completed",
            "certificate_location": trust_details.get("certificate_location"),
            "completion_timestamp": datetime.utcnow().isoformat()
        })
    }