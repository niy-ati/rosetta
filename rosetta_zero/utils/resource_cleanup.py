"""
Resource Cleanup Utilities.

Implements automatic resource cleanup to minimize cloud infrastructure costs.

Requirements:
- 26.1: Terminate temporary compute resources after workflow phase completion
- 26.2: Delete temporary storage objects older than 30 days
- 26.3: Tag all AWS resources with workflow identifiers for cost tracking
- 26.4: Publish resource usage metrics to CloudWatch
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

from rosetta_zero.utils.logging import logger, log_error
from rosetta_zero.utils.monitoring import PerformanceMetricsPublisher


class ResourceCleanupManager:
    """
    Manages automatic resource cleanup for cost optimization.
    
    Handles:
    - Fargate task termination after test execution
    - S3 temporary object deletion based on lifecycle policies
    - Resource tagging for cost tracking
    - Resource usage metrics publishing
    """
    
    def __init__(
        self,
        ecs_client=None,
        s3_client=None,
        cloudwatch_client=None,
        metrics_publisher: Optional[PerformanceMetricsPublisher] = None
    ):
        """
        Initialize resource cleanup manager.
        
        Args:
            ecs_client: Boto3 ECS client (optional, will create if not provided)
            s3_client: Boto3 S3 client (optional, will create if not provided)
            cloudwatch_client: Boto3 CloudWatch client (optional, will create if not provided)
            metrics_publisher: Performance metrics publisher (optional)
        """
        self._ecs_client = ecs_client
        self._s3_client = s3_client
        self._cloudwatch_client = cloudwatch_client
        self._metrics_publisher = metrics_publisher
    
    @property
    def ecs_client(self):
        """Lazy-load ECS client."""
        if self._ecs_client is None:
            self._ecs_client = boto3.client('ecs')
        return self._ecs_client
    
    @property
    def s3_client(self):
        """Lazy-load S3 client."""
        if self._s3_client is None:
            self._s3_client = boto3.client('s3')
        return self._s3_client
    
    @property
    def cloudwatch_client(self):
        """Lazy-load CloudWatch client."""
        if self._cloudwatch_client is None:
            self._cloudwatch_client = boto3.client('cloudwatch')
        return self._cloudwatch_client
    
    @property
    def metrics_publisher(self):
        """Lazy-load metrics publisher."""
        if self._metrics_publisher is None:
            self._metrics_publisher = PerformanceMetricsPublisher(
                namespace='RosettaZero'
            )
        return self._metrics_publisher
    
    def terminate_fargate_task(
        self,
        cluster_name: str,
        task_arn: str,
        workflow_id: str,
        reason: str = "Test execution completed"
    ) -> Dict[str, Any]:
        """
        Terminate a Fargate task after test execution.
        
        Requirement: 26.1 - Terminate temporary compute resources
        
        Args:
            cluster_name: ECS cluster name
            task_arn: ARN of the task to terminate
            workflow_id: Workflow identifier for logging
            reason: Reason for termination
            
        Returns:
            Termination result with task details
        """
        logger.info(
            "Terminating Fargate task",
            extra={
                "workflow_id": workflow_id,
                "cluster": cluster_name,
                "task_arn": task_arn,
                "reason": reason
            }
        )
        
        try:
            # Stop the task
            response = self.ecs_client.stop_task(
                cluster=cluster_name,
                task=task_arn,
                reason=reason
            )
            
            task = response['task']
            
            # Publish resource cleanup metric
            self.metrics_publisher.publish_resource_utilization(
                resource_type='FargateTask',
                utilization_percent=0.0,  # Task terminated
                component='verification-environment'
            )
            
            logger.info(
                "Fargate task terminated successfully",
                extra={
                    "workflow_id": workflow_id,
                    "task_arn": task_arn,
                    "stopped_at": task.get('stoppedAt', 'N/A'),
                    "stopped_reason": task.get('stoppedReason', reason)
                }
            )
            
            return {
                "success": True,
                "task_arn": task_arn,
                "stopped_at": task.get('stoppedAt'),
                "stopped_reason": task.get('stoppedReason', reason)
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # Task already stopped is not an error
            if error_code == 'InvalidParameterException':
                logger.info(
                    "Fargate task already stopped",
                    extra={
                        "workflow_id": workflow_id,
                        "task_arn": task_arn
                    }
                )
                return {
                    "success": True,
                    "task_arn": task_arn,
                    "already_stopped": True
                }
            
            log_error(
                component='resource_cleanup',
                error_type=error_code,
                error_message=str(e),
                context={
                    "workflow_id": workflow_id,
                    "task_arn": task_arn,
                    "cluster": cluster_name
                }
            )
            raise
    
    def cleanup_temporary_s3_objects(
        self,
        bucket_name: str,
        prefix: str = "temp/",
        age_days: int = 30,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete temporary S3 objects older than specified age.
        
        Requirement: 26.2 - Delete temporary storage objects older than 30 days
        
        Args:
            bucket_name: S3 bucket name
            prefix: Prefix for temporary objects (default: "temp/")
            age_days: Age threshold in days (default: 30)
            workflow_id: Optional workflow identifier for logging
            
        Returns:
            Cleanup result with count of deleted objects
        """
        logger.info(
            "Cleaning up temporary S3 objects",
            extra={
                "workflow_id": workflow_id,
                "bucket": bucket_name,
                "prefix": prefix,
                "age_days": age_days
            }
        )
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=age_days)
            
            # List objects with prefix
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            
            deleted_count = 0
            total_size_bytes = 0
            objects_to_delete = []
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    # Check if object is older than cutoff date
                    if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                        objects_to_delete.append({'Key': obj['Key']})
                        total_size_bytes += obj['Size']
                        
                        # Delete in batches of 1000 (S3 limit)
                        if len(objects_to_delete) >= 1000:
                            self._delete_s3_objects_batch(
                                bucket_name,
                                objects_to_delete
                            )
                            deleted_count += len(objects_to_delete)
                            objects_to_delete = []
            
            # Delete remaining objects
            if objects_to_delete:
                self._delete_s3_objects_batch(bucket_name, objects_to_delete)
                deleted_count += len(objects_to_delete)
            
            # Publish storage cleanup metric
            self.metrics_publisher.publish_resource_utilization(
                resource_type='S3Storage',
                utilization_percent=0.0,  # Objects deleted
                component='resource-cleanup'
            )
            
            logger.info(
                "Temporary S3 objects cleaned up",
                extra={
                    "workflow_id": workflow_id,
                    "bucket": bucket_name,
                    "deleted_count": deleted_count,
                    "total_size_mb": total_size_bytes / (1024 * 1024),
                    "age_days": age_days
                }
            )
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "total_size_bytes": total_size_bytes,
                "bucket": bucket_name,
                "prefix": prefix
            }
            
        except ClientError as e:
            log_error(
                component='resource_cleanup',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={
                    "workflow_id": workflow_id,
                    "bucket": bucket_name,
                    "prefix": prefix
                }
            )
            raise
    
    def _delete_s3_objects_batch(
        self,
        bucket_name: str,
        objects: List[Dict[str, str]]
    ) -> None:
        """
        Delete a batch of S3 objects.
        
        Args:
            bucket_name: S3 bucket name
            objects: List of objects to delete (format: [{'Key': 'key1'}, ...])
        """
        if not objects:
            return
        
        self.s3_client.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': objects}
        )
    
    def tag_aws_resource(
        self,
        resource_arn: str,
        workflow_id: str,
        additional_tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Tag AWS resource with workflow identifier for cost tracking.
        
        Requirement: 26.3 - Tag all AWS resources with workflow identifiers
        
        Args:
            resource_arn: ARN of the resource to tag
            workflow_id: Workflow identifier
            additional_tags: Optional additional tags to apply
            
        Returns:
            Tagging result
        """
        logger.info(
            "Tagging AWS resource",
            extra={
                "workflow_id": workflow_id,
                "resource_arn": resource_arn
            }
        )
        
        try:
            # Prepare tags
            tags = [
                {'Key': 'WorkflowId', 'Value': workflow_id},
                {'Key': 'ManagedBy', 'Value': 'RosettaZero'},
                {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()}
            ]
            
            # Add additional tags if provided
            if additional_tags:
                for key, value in additional_tags.items():
                    tags.append({'Key': key, 'Value': value})
            
            # Determine service from ARN and apply tags
            if ':ecs:' in resource_arn and ':task/' in resource_arn:
                # ECS task tagging
                self.ecs_client.tag_resource(
                    resourceArn=resource_arn,
                    tags=tags
                )
            elif ':s3:::' in resource_arn:
                # S3 bucket tagging
                bucket_name = resource_arn.split(':::')[1]
                self.s3_client.put_bucket_tagging(
                    Bucket=bucket_name,
                    Tagging={'TagSet': tags}
                )
            else:
                # Generic resource tagging using Resource Groups Tagging API
                tagging_client = boto3.client('resourcegroupstaggingapi')
                tagging_client.tag_resources(
                    ResourceARNList=[resource_arn],
                    Tags={tag['Key']: tag['Value'] for tag in tags}
                )
            
            logger.info(
                "AWS resource tagged successfully",
                extra={
                    "workflow_id": workflow_id,
                    "resource_arn": resource_arn,
                    "tags_count": len(tags)
                }
            )
            
            return {
                "success": True,
                "resource_arn": resource_arn,
                "tags_applied": len(tags)
            }
            
        except ClientError as e:
            log_error(
                component='resource_cleanup',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={
                    "workflow_id": workflow_id,
                    "resource_arn": resource_arn
                }
            )
            raise
    
    def publish_resource_usage_metrics(
        self,
        workflow_id: str,
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Publish resource usage metrics to CloudWatch.
        
        Requirement: 26.4 - Publish resource usage metrics to CloudWatch
        
        Args:
            workflow_id: Workflow identifier
            metrics: Dictionary of metric names to values
                     Example: {
                         'fargate_tasks_active': 5,
                         's3_storage_gb': 120.5,
                         'lambda_invocations': 1000000,
                         'dynamodb_read_units': 50000
                     }
            
        Returns:
            Metrics publishing result
        """
        logger.info(
            "Publishing resource usage metrics",
            extra={
                "workflow_id": workflow_id,
                "metrics_count": len(metrics)
            }
        )
        
        try:
            metric_data = []
            
            for metric_name, value in metrics.items():
                metric_data.append({
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': self._get_metric_unit(metric_name),
                    'Timestamp': datetime.utcnow(),
                    'Dimensions': [
                        {'Name': 'WorkflowId', 'Value': workflow_id},
                        {'Name': 'Component', 'Value': 'ResourceCleanup'}
                    ]
                })
            
            # Publish metrics in batches of 20 (CloudWatch limit)
            for i in range(0, len(metric_data), 20):
                batch = metric_data[i:i+20]
                self.cloudwatch_client.put_metric_data(
                    Namespace='RosettaZero/ResourceUsage',
                    MetricData=batch
                )
            
            logger.info(
                "Resource usage metrics published",
                extra={
                    "workflow_id": workflow_id,
                    "metrics_published": len(metrics)
                }
            )
            
            return {
                "success": True,
                "metrics_published": len(metrics),
                "workflow_id": workflow_id
            }
            
        except ClientError as e:
            log_error(
                component='resource_cleanup',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={
                    "workflow_id": workflow_id,
                    "metrics_count": len(metrics)
                }
            )
            raise
    
    def _get_metric_unit(self, metric_name: str) -> str:
        """
        Determine appropriate CloudWatch unit for metric.
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            CloudWatch unit string
        """
        metric_name_lower = metric_name.lower()
        
        if 'gb' in metric_name_lower or 'gigabyte' in metric_name_lower:
            return 'Gigabytes'
        elif 'mb' in metric_name_lower or 'megabyte' in metric_name_lower:
            return 'Megabytes'
        elif 'percent' in metric_name_lower or 'utilization' in metric_name_lower:
            return 'Percent'
        elif 'count' in metric_name_lower or 'tasks' in metric_name_lower or 'invocations' in metric_name_lower:
            return 'Count'
        elif 'seconds' in metric_name_lower or 'duration' in metric_name_lower:
            return 'Seconds'
        else:
            return 'None'
    
    def cleanup_workflow_resources(
        self,
        workflow_id: str,
        cluster_name: str,
        task_arns: List[str],
        temp_buckets: List[str]
    ) -> Dict[str, Any]:
        """
        Comprehensive cleanup of all resources for a workflow.
        
        Combines all cleanup operations for a complete workflow phase.
        
        Args:
            workflow_id: Workflow identifier
            cluster_name: ECS cluster name
            task_arns: List of Fargate task ARNs to terminate
            temp_buckets: List of S3 buckets to clean temporary objects from
            
        Returns:
            Comprehensive cleanup result
        """
        logger.info(
            "Starting comprehensive workflow resource cleanup",
            extra={
                "workflow_id": workflow_id,
                "tasks_to_terminate": len(task_arns),
                "buckets_to_clean": len(temp_buckets)
            }
        )
        
        results = {
            "workflow_id": workflow_id,
            "terminated_tasks": [],
            "cleaned_buckets": [],
            "errors": []
        }
        
        # Terminate Fargate tasks
        for task_arn in task_arns:
            try:
                result = self.terminate_fargate_task(
                    cluster_name=cluster_name,
                    task_arn=task_arn,
                    workflow_id=workflow_id
                )
                results["terminated_tasks"].append(result)
            except Exception as e:
                results["errors"].append({
                    "operation": "terminate_task",
                    "task_arn": task_arn,
                    "error": str(e)
                })
        
        # Clean temporary S3 objects
        for bucket_name in temp_buckets:
            try:
                result = self.cleanup_temporary_s3_objects(
                    bucket_name=bucket_name,
                    workflow_id=workflow_id
                )
                results["cleaned_buckets"].append(result)
            except Exception as e:
                results["errors"].append({
                    "operation": "cleanup_s3",
                    "bucket": bucket_name,
                    "error": str(e)
                })
        
        # Publish resource usage metrics
        try:
            metrics = {
                'fargate_tasks_terminated': len(results["terminated_tasks"]),
                's3_buckets_cleaned': len(results["cleaned_buckets"]),
                'cleanup_errors': len(results["errors"])
            }
            self.publish_resource_usage_metrics(workflow_id, metrics)
        except Exception as e:
            results["errors"].append({
                "operation": "publish_metrics",
                "error": str(e)
            })
        
        logger.info(
            "Workflow resource cleanup completed",
            extra={
                "workflow_id": workflow_id,
                "terminated_tasks": len(results["terminated_tasks"]),
                "cleaned_buckets": len(results["cleaned_buckets"]),
                "errors": len(results["errors"])
            }
        )
        
        return results
