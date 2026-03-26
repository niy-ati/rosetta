"""Lambda handler for Bedrock Architect.

Requirements: 6.1, 6.2
"""

import json
import os
from typing import Dict, Any

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

from .synthesis import BedrockArchitect

# Initialize PowerTools
logger = Logger(service="bedrock-architect")
tracer = Tracer(service="bedrock-architect")
metrics = Metrics(namespace="RosettaZero", service="bedrock-architect")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for synthesizing modern implementations from Logic Maps.
    
    Event structure:
    {
        "logic_map_s3_bucket": "rosetta-zero-logic-maps-...",
        "logic_map_s3_key": "logic-maps/artifact-id/version/logic-map.json"
    }
    
    Returns:
        {
            "statusCode": 200,
            "body": {
                "artifact_id": "...",
                "modern_implementation_s3_key": "modern-implementations/.../lambda.py",
                "cdk_infrastructure_s3_key": "cdk-infrastructure/.../stack.py",
                "synthesis_timestamp": "2024-01-01T00:00:00Z"
            }
        }
    """
    try:
        # Extract parameters from event
        logic_map_bucket = event["logic_map_s3_bucket"]
        logic_map_key = event["logic_map_s3_key"]
        
        logger.info(
            "Starting Lambda synthesis",
            extra={
                "logic_map_bucket": logic_map_bucket,
                "logic_map_key": logic_map_key,
            },
        )
        
        # Initialize Bedrock Architect
        architect = BedrockArchitect(
            region=os.environ.get("AWS_REGION", "us-east-1"),
            modern_implementations_bucket=os.environ.get("MODERN_IMPLEMENTATIONS_BUCKET"),
            cdk_infrastructure_bucket=os.environ.get("CDK_INFRASTRUCTURE_BUCKET"),
            kms_key_id=os.environ.get("KMS_KEY_ID"),
            bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
            cobol_kb_id=os.environ.get("COBOL_KB_ID"),
            fortran_kb_id=os.environ.get("FORTRAN_KB_ID"),
            mainframe_kb_id=os.environ.get("MAINFRAME_KB_ID"),
        )
        
        # Synthesize Lambda function
        result = architect.synthesize_lambda(
            logic_map_bucket=logic_map_bucket,
            logic_map_key=logic_map_key,
        )
        
        logger.info(
            "Lambda synthesis completed successfully",
            extra={
                "artifact_id": result.artifact_id,
                "modern_implementation_s3_key": result.modern_implementation_s3_key,
            },
        )
        
        # Publish success metric
        metrics.add_metric(name="SynthesisSuccess", unit="Count", value=1)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "artifact_id": result.artifact_id,
                "modern_implementation_s3_key": result.modern_implementation_s3_key,
                "cdk_infrastructure_s3_key": result.cdk_infrastructure_s3_key,
                "synthesis_timestamp": result.synthesis_timestamp.isoformat(),
            }),
        }
        
    except KeyError as e:
        logger.error(f"Missing required parameter: {e}")
        metrics.add_metric(name="SynthesisError", unit="Count", value=1)
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Missing required parameter: {e}"}),
        }
        
    except Exception as e:
        logger.exception("Synthesis failed with unexpected error")
        metrics.add_metric(name="SynthesisError", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
