"""Lambda handler for Ingestion Engine.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import json
import os
from typing import Dict, Any

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

from .ingestion import IngestionEngine

# Initialize PowerTools
logger = Logger(service="ingestion-engine")
tracer = Tracer(service="ingestion-engine")
metrics = Metrics(namespace="RosettaZero", service="ingestion-engine")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for ingesting legacy artifacts.
    
    Event structure:
    {
        "s3_bucket": "rosetta-zero-legacy-artifacts-...",
        "s3_key": "artifacts/cobol/payroll.cbl",
        "artifact_type": "COBOL"  # or "FORTRAN" or "MAINFRAME_BINARY"
    }
    
    Returns:
        {
            "statusCode": 200,
            "body": {
                "artifact_id": "...",
                "artifact_hash": "sha256:...",
                "ingestion_timestamp": "2024-01-01T00:00:00Z",
                "logic_map_s3_key": "logic-maps/.../logic-map.json",
                "ears_document_s3_key": "ears-requirements/.../ears.md"
            }
        }
    """
    try:
        # Extract parameters from event
        s3_bucket = event["s3_bucket"]
        s3_key = event["s3_key"]
        artifact_type = event["artifact_type"]
        
        logger.info(
            "Starting artifact ingestion",
            extra={
                "s3_bucket": s3_bucket,
                "s3_key": s3_key,
                "artifact_type": artifact_type,
            },
        )
        
        # Initialize Ingestion Engine
        engine = IngestionEngine(
            region=os.environ.get("AWS_REGION", "us-east-1"),
            logic_maps_bucket=os.environ.get("LOGIC_MAPS_BUCKET"),
            ears_bucket=os.environ.get("EARS_BUCKET"),
            kms_key_id=os.environ.get("KMS_KEY_ID"),
        )
        
        # Ingest artifact
        result = engine.ingest_artifact(
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            artifact_type=artifact_type,
        )
        
        logger.info(
            "Artifact ingestion completed successfully",
            extra={
                "artifact_id": result.artifact_id,
                "artifact_hash": result.artifact_hash,
            },
        )
        
        # Publish success metric
        metrics.add_metric(name="IngestionSuccess", unit="Count", value=1)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "artifact_id": result.artifact_id,
                "artifact_hash": result.artifact_hash,
                "ingestion_timestamp": result.ingestion_timestamp.isoformat(),
                "logic_map_s3_key": result.logic_map_s3_key,
                "ears_document_s3_key": result.ears_document_s3_key,
            }),
        }
        
    except KeyError as e:
        logger.error(f"Missing required parameter: {e}")
        metrics.add_metric(name="IngestionError", unit="Count", value=1)
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Missing required parameter: {e}"}),
        }
        
    except Exception as e:
        logger.exception("Ingestion failed with unexpected error")
        metrics.add_metric(name="IngestionError", unit="Count", value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
