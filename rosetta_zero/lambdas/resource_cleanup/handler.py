"""
Resource Cleanup Lambda Handler.

Handles automatic resource cleanup after workflow phase completion.

Requirements:
- 26.1: Terminate temporary Fargate tasks after test execution
- 26.2: Delete temporary S3 objects older than 30 days
- 26.3: Tag all AWS resources with workflow identifiers
- 26.4: Publish resource usage metrics to CloudWatch
"""

import json
import os
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from rosetta_zero.utils.logging import logger, log_error
from rosetta_zero.utils.resource_cleanup import ResourceCleanupManager
from rosetta_zero.utils.monitoring import PerformanceMetricsPublisher

# Initialize utilities
tracer = Tracer()

# Lazy-load metrics publisher and cleanup manager
_metrics_publisher = None
_cleanup_manager = None


def get_metrics_publisher() -> PerformanceMetricsPublisher:
    """Get or create metrics publisher."""
    global _metrics_publisher
    if _metrics_publisher is None:
        _metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
    return _metrics_publisher


def get_cleanup_manager() -> ResourceCleanupManager:
    """Get or create resource cleanup manager."""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = ResourceCleanupManager(
            metrics_publisher=get_metrics_publisher()
        )
    return _cleanup_manager


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def cleanup_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main handler for resource cleanup operations.
    
    Handles different types of cleanup events:
    1. Phase completion events - cleanup resources after workflow phase
    2. Scheduled events - periodic cleanup of temporary objects
    3. Manual cleanup requests - on-demand cleanup
    
    Args:
        event: Lambda event containing cleanup instructions
        context: Lambda context
        
    Returns:
        Cleanup result
    """
    logger.info("Resource cleanup invoked", extra={"event": event})
    
    try:
        # Determine event type
        if "detail-type" in event and event["detail-type"] == "Workflow Phase Completed":
            # Phase completion event - cleanup resources for completed phase
            return handle_phase_completion_cleanup(event)
        elif "source" in event and event["source"] == "aws.events":
            # Scheduled event - periodic cleanup
            return handle_scheduled_cleanup(event)
        elif "cleanup_type" in event:
            # Manual cleanup request
            return handle_manual_cleanup(event)
        else:
            logger.error("Unknown event type", extra={"event": event})
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Unknown event type"})
            }
    
    except Exception as e:
        log_error(
            component='resource_cleanup',
            error_type=type(e).__name__,
            error_message=str(e),
            context={'event': event}
        )
        raise


def handle_phase_completion_cleanup(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle resource cleanup after workflow phase completion.
    
    Requirement: 26.1 - Terminate temporary compute resources
    
    Args:
        event: EventBridge phase completion event
        
    Returns:
        Cleanup result
    """
    detail = event["detail"]
    workflow_id = detail["workflow_id"]
    completed_phase = detail["phase_name"]
    phase_details = detail.get("details", {})
    
    logger.info(
        "Handling phase completion cleanup",
        extra={
            "workflow_id": workflow_id,
            "completed_phase": completed_phase
        }
    )
    
    cleanup_manager = get_cleanup_manager()
    results = {
        "workflow_id": workflow_id,
        "phase": completed_phase,
        "cleanup_operations": []
    }
    
    # Cleanup based on phase
    if completed_phase == "Validation":
        # Terminate Fargate tasks after test execution
        task_arns = phase_details.get("fargate_task_arns", [])
        cluster_name = os.environ.get('ECS_CLUSTER_NAME', 'rosetta-zero-cluster')
        
        for task_arn in task_arns:
            try:
                result = cleanup_manager.terminate_fargate_task(
                    cluster_name=cluster_name,
                    task_arn=task_arn,
                    workflow_id=workflow_id,
                    reason=f"Validation phase completed for workflow {workflow_id}"
                )
                results["cleanup_operations"].append({
                    "operation": "terminate_fargate_task",
                    "success": True,
                    "task_arn": task_arn
                })
            except Exception as e:
                logger.error(
                    "Failed to terminate Fargate task",
                    extra={
                        "workflow_id": workflow_id,
                        "task_arn": task_arn,
                        "error": str(e)
                    }
                )
                results["cleanup_operations"].append({
                    "operation": "terminate_fargate_task",
                    "success": False,
                    "task_arn": task_arn,
                    "error": str(e)
                })
        
        # Tag resources with workflow identifier
        resource_arns = phase_details.get("resource_arns", [])
        for resource_arn in resource_arns:
            try:
                result = cleanup_manager.tag_aws_resource(
                    resource_arn=resource_arn,
                    workflow_id=workflow_id,
                    additional_tags={
                        "Phase": completed_phase,
                        "CompletedAt": phase_details.get("completion_timestamp", "")
                    }
                )
                results["cleanup_operations"].append({
                    "operation": "tag_resource",
                    "success": True,
                    "resource_arn": resource_arn
                })
            except Exception as e:
                logger.error(
                    "Failed to tag resource",
                    extra={
                        "workflow_id": workflow_id,
                        "resource_arn": resource_arn,
                        "error": str(e)
                    }
                )
                results["cleanup_operations"].append({
                    "operation": "tag_resource",
                    "success": False,
                    "resource_arn": resource_arn,
                    "error": str(e)
                })
    
    # Publish resource usage metrics for all phases
    try:
        metrics = {
            'phase_completed': 1,
            'cleanup_operations': len(results["cleanup_operations"]),
            'cleanup_successes': sum(1 for op in results["cleanup_operations"] if op.get("success")),
            'cleanup_failures': sum(1 for op in results["cleanup_operations"] if not op.get("success"))
        }
        cleanup_manager.publish_resource_usage_metrics(workflow_id, metrics)
        results["metrics_published"] = True
    except Exception as e:
        logger.error(
            "Failed to publish resource usage metrics",
            extra={
                "workflow_id": workflow_id,
                "error": str(e)
            }
        )
        results["metrics_published"] = False
    
    logger.info(
        "Phase completion cleanup finished",
        extra={
            "workflow_id": workflow_id,
            "operations": len(results["cleanup_operations"])
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps(results)
    }


def handle_scheduled_cleanup(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle scheduled periodic cleanup of temporary objects.
    
    Requirement: 26.2 - Delete temporary storage objects older than 30 days
    
    Args:
        event: EventBridge scheduled event
        
    Returns:
        Cleanup result
    """
    logger.info("Handling scheduled cleanup")
    
    cleanup_manager = get_cleanup_manager()
    results = {
        "cleanup_type": "scheduled",
        "buckets_cleaned": []
    }
    
    # Get list of buckets to clean from environment
    buckets_to_clean = os.environ.get(
        'TEMP_BUCKETS',
        'rosetta-zero-test-vectors,rosetta-zero-discrepancy-reports'
    ).split(',')
    
    # Clean temporary objects from each bucket
    for bucket_name in buckets_to_clean:
        bucket_name = bucket_name.strip()
        try:
            result = cleanup_manager.cleanup_temporary_s3_objects(
                bucket_name=bucket_name,
                prefix="temp/",
                age_days=30
            )
            results["buckets_cleaned"].append({
                "bucket": bucket_name,
                "success": True,
                "deleted_count": result["deleted_count"],
                "total_size_bytes": result["total_size_bytes"]
            })
        except Exception as e:
            logger.error(
                "Failed to clean bucket",
                extra={
                    "bucket": bucket_name,
                    "error": str(e)
                }
            )
            results["buckets_cleaned"].append({
                "bucket": bucket_name,
                "success": False,
                "error": str(e)
            })
    
    # Publish cleanup metrics
    try:
        total_deleted = sum(
            b.get("deleted_count", 0)
            for b in results["buckets_cleaned"]
            if b.get("success")
        )
        total_size_mb = sum(
            b.get("total_size_bytes", 0)
            for b in results["buckets_cleaned"]
            if b.get("success")
        ) / (1024 * 1024)
        
        metrics = {
            'scheduled_cleanup_runs': 1,
            'buckets_cleaned': len([b for b in results["buckets_cleaned"] if b.get("success")]),
            'objects_deleted': total_deleted,
            'storage_freed_mb': total_size_mb
        }
        cleanup_manager.publish_resource_usage_metrics("scheduled-cleanup", metrics)
        results["metrics_published"] = True
    except Exception as e:
        logger.error(
            "Failed to publish cleanup metrics",
            extra={"error": str(e)}
        )
        results["metrics_published"] = False
    
    logger.info(
        "Scheduled cleanup finished",
        extra={
            "buckets_cleaned": len(results["buckets_cleaned"])
        }
    )
    
    return {
        "statusCode": 200,
        "body": json.dumps(results)
    }


def handle_manual_cleanup(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle manual cleanup request.
    
    Args:
        event: Manual cleanup event with specific instructions
        
    Returns:
        Cleanup result
    """
    cleanup_type = event.get("cleanup_type")
    workflow_id = event.get("workflow_id")
    
    logger.info(
        "Handling manual cleanup",
        extra={
            "cleanup_type": cleanup_type,
            "workflow_id": workflow_id
        }
    )
    
    cleanup_manager = get_cleanup_manager()
    
    if cleanup_type == "terminate_tasks":
        # Terminate specific Fargate tasks
        cluster_name = event.get("cluster_name", os.environ.get('ECS_CLUSTER_NAME', 'rosetta-zero-cluster'))
        task_arns = event.get("task_arns", [])
        
        results = []
        for task_arn in task_arns:
            try:
                result = cleanup_manager.terminate_fargate_task(
                    cluster_name=cluster_name,
                    task_arn=task_arn,
                    workflow_id=workflow_id or "manual-cleanup",
                    reason="Manual cleanup request"
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to terminate task",
                    extra={"task_arn": task_arn, "error": str(e)}
                )
                results.append({
                    "success": False,
                    "task_arn": task_arn,
                    "error": str(e)
                })
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "cleanup_type": cleanup_type,
                "results": results
            })
        }
    
    elif cleanup_type == "cleanup_s3":
        # Clean specific S3 bucket
        bucket_name = event.get("bucket_name")
        prefix = event.get("prefix", "temp/")
        age_days = event.get("age_days", 30)
        
        try:
            result = cleanup_manager.cleanup_temporary_s3_objects(
                bucket_name=bucket_name,
                prefix=prefix,
                age_days=age_days,
                workflow_id=workflow_id
            )
            return {
                "statusCode": 200,
                "body": json.dumps(result)
            }
        except Exception as e:
            logger.error(
                "Failed to clean S3 bucket",
                extra={"bucket": bucket_name, "error": str(e)}
            )
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": str(e),
                    "bucket": bucket_name
                })
            }
    
    elif cleanup_type == "tag_resources":
        # Tag specific resources
        resource_arns = event.get("resource_arns", [])
        additional_tags = event.get("additional_tags", {})
        
        results = []
        for resource_arn in resource_arns:
            try:
                result = cleanup_manager.tag_aws_resource(
                    resource_arn=resource_arn,
                    workflow_id=workflow_id or "manual-cleanup",
                    additional_tags=additional_tags
                )
                results.append(result)
            except Exception as e:
                logger.error(
                    "Failed to tag resource",
                    extra={"resource_arn": resource_arn, "error": str(e)}
                )
                results.append({
                    "success": False,
                    "resource_arn": resource_arn,
                    "error": str(e)
                })
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "cleanup_type": cleanup_type,
                "results": results
            })
        }
    
    else:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Unknown cleanup type: {cleanup_type}"
            })
        }
