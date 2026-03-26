"""
Unit tests for Resource Cleanup functionality.

Tests Requirements:
- 26.1: Terminate temporary Fargate tasks after test execution
- 26.2: Delete temporary S3 objects older than 30 days
- 26.3: Tag all AWS resources with workflow identifiers
- 26.4: Publish resource usage metrics to CloudWatch
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
import pytest
from botocore.exceptions import ClientError

from rosetta_zero.utils.resource_cleanup import ResourceCleanupManager


class TestResourceCleanupManager:
    """Test suite for ResourceCleanupManager."""
    
    def test_terminate_fargate_task_success(self):
        """
        Test successful Fargate task termination.
        
        Requirement: 26.1 - Terminate temporary compute resources
        """
        # Mock AWS clients
        mock_ecs_client = Mock()
        mock_metrics_publisher = Mock()
        
        # Mock ECS stop_task response
        mock_ecs_client.stop_task.return_value = {
            'task': {
                'taskArn': 'arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123',
                'stoppedAt': datetime.utcnow(),
                'stoppedReason': 'Test execution completed'
            }
        }
        
        # Create cleanup manager
        cleanup_manager = ResourceCleanupManager(
            ecs_client=mock_ecs_client,
            metrics_publisher=mock_metrics_publisher
        )
        
        # Terminate task
        result = cleanup_manager.terminate_fargate_task(
            cluster_name='test-cluster',
            task_arn='arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123',
            workflow_id='test-workflow-123',
            reason='Test execution completed'
        )
        
        # Verify ECS stop_task was called
        mock_ecs_client.stop_task.assert_called_once_with(
            cluster='test-cluster',
            task='arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123',
            reason='Test execution completed'
        )
        
        # Verify metrics were published
        mock_metrics_publisher.publish_resource_utilization.assert_called_once()
        
        # Verify result
        assert result['success'] is True
        assert result['task_arn'] == 'arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123'
    
    def test_terminate_fargate_task_already_stopped(self):
        """
        Test terminating a task that's already stopped.
        
        Requirement: 26.1
        """
        mock_ecs_client = Mock()
        mock_metrics_publisher = Mock()
        
        # Mock InvalidParameterException (task already stopped)
        mock_ecs_client.stop_task.side_effect = ClientError(
            {'Error': {'Code': 'InvalidParameterException', 'Message': 'Task already stopped'}},
            'StopTask'
        )
        
        cleanup_manager = ResourceCleanupManager(
            ecs_client=mock_ecs_client,
            metrics_publisher=mock_metrics_publisher
        )
        
        # Terminate task
        result = cleanup_manager.terminate_fargate_task(
            cluster_name='test-cluster',
            task_arn='arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123',
            workflow_id='test-workflow-123'
        )
        
        # Verify result indicates task was already stopped
        assert result['success'] is True
        assert result.get('already_stopped') is True
    
    def test_cleanup_temporary_s3_objects(self):
        """
        Test cleanup of temporary S3 objects older than 30 days.
        
        Requirement: 26.2 - Delete temporary storage objects older than 30 days
        """
        mock_s3_client = Mock()
        mock_metrics_publisher = Mock()
        
        # Mock S3 list_objects_v2 response with old and new objects
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_object_date = cutoff_date - timedelta(days=5)
        new_object_date = cutoff_date + timedelta(days=5)
        
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {
                        'Key': 'temp/old-object-1.json',
                        'LastModified': old_object_date,
                        'Size': 1024
                    },
                    {
                        'Key': 'temp/old-object-2.json',
                        'LastModified': old_object_date,
                        'Size': 2048
                    },
                    {
                        'Key': 'temp/new-object.json',
                        'LastModified': new_object_date,
                        'Size': 512
                    }
                ]
            }
        ]
        
        cleanup_manager = ResourceCleanupManager(
            s3_client=mock_s3_client,
            metrics_publisher=mock_metrics_publisher
        )
        
        # Cleanup temporary objects
        result = cleanup_manager.cleanup_temporary_s3_objects(
            bucket_name='test-bucket',
            prefix='temp/',
            age_days=30,
            workflow_id='test-workflow-123'
        )
        
        # Verify S3 delete_objects was called with old objects only
        mock_s3_client.delete_objects.assert_called_once()
        delete_call = mock_s3_client.delete_objects.call_args
        deleted_keys = [obj['Key'] for obj in delete_call[1]['Delete']['Objects']]
        
        assert 'temp/old-object-1.json' in deleted_keys
        assert 'temp/old-object-2.json' in deleted_keys
        assert 'temp/new-object.json' not in deleted_keys
        
        # Verify result
        assert result['success'] is True
        assert result['deleted_count'] == 2
        assert result['total_size_bytes'] == 3072  # 1024 + 2048
        
        # Verify metrics were published
        mock_metrics_publisher.publish_resource_utilization.assert_called_once()
    
    def test_cleanup_s3_objects_empty_bucket(self):
        """
        Test cleanup when bucket has no objects.
        
        Requirement: 26.2
        """
        mock_s3_client = Mock()
        mock_metrics_publisher = Mock()
        
        # Mock empty S3 response
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No Contents key
        
        cleanup_manager = ResourceCleanupManager(
            s3_client=mock_s3_client,
            metrics_publisher=mock_metrics_publisher
        )
        
        # Cleanup temporary objects
        result = cleanup_manager.cleanup_temporary_s3_objects(
            bucket_name='test-bucket',
            prefix='temp/',
            age_days=30
        )
        
        # Verify no delete operations
        mock_s3_client.delete_objects.assert_not_called()
        
        # Verify result
        assert result['success'] is True
        assert result['deleted_count'] == 0
        assert result['total_size_bytes'] == 0
    
    def test_tag_aws_resource_ecs_task(self):
        """
        Test tagging ECS task with workflow identifier.
        
        Requirement: 26.3 - Tag all AWS resources with workflow identifiers
        """
        mock_ecs_client = Mock()
        
        cleanup_manager = ResourceCleanupManager(
            ecs_client=mock_ecs_client
        )
        
        # Tag ECS task
        task_arn = 'arn:aws:ecs:us-east-1:123456789012:task/cluster/abc123'
        result = cleanup_manager.tag_aws_resource(
            resource_arn=task_arn,
            workflow_id='test-workflow-123',
            additional_tags={'Phase': 'Validation'}
        )
        
        # Verify ECS tag_resource was called
        mock_ecs_client.tag_resource.assert_called_once()
        call_args = mock_ecs_client.tag_resource.call_args
        
        assert call_args[1]['resourceArn'] == task_arn
        tags = call_args[1]['tags']
        
        # Verify required tags
        tag_dict = {tag['Key']: tag['Value'] for tag in tags}
        assert tag_dict['WorkflowId'] == 'test-workflow-123'
        assert tag_dict['ManagedBy'] == 'RosettaZero'
        assert tag_dict['Phase'] == 'Validation'
        assert 'CreatedAt' in tag_dict
        
        # Verify result
        assert result['success'] is True
        assert result['resource_arn'] == task_arn
    
    def test_tag_aws_resource_s3_bucket(self):
        """
        Test tagging S3 bucket with workflow identifier.
        
        Requirement: 26.3
        """
        mock_s3_client = Mock()
        
        cleanup_manager = ResourceCleanupManager(
            s3_client=mock_s3_client
        )
        
        # Tag S3 bucket
        bucket_arn = 'arn:aws:s3:::test-bucket'
        result = cleanup_manager.tag_aws_resource(
            resource_arn=bucket_arn,
            workflow_id='test-workflow-123'
        )
        
        # Verify S3 put_bucket_tagging was called
        mock_s3_client.put_bucket_tagging.assert_called_once()
        call_args = mock_s3_client.put_bucket_tagging.call_args
        
        assert call_args[1]['Bucket'] == 'test-bucket'
        tags = call_args[1]['Tagging']['TagSet']
        
        # Verify required tags
        tag_dict = {tag['Key']: tag['Value'] for tag in tags}
        assert tag_dict['WorkflowId'] == 'test-workflow-123'
        assert tag_dict['ManagedBy'] == 'RosettaZero'
        
        # Verify result
        assert result['success'] is True
    
    def test_publish_resource_usage_metrics(self):
        """
        Test publishing resource usage metrics to CloudWatch.
        
        Requirement: 26.4 - Publish resource usage metrics to CloudWatch
        """
        mock_cloudwatch_client = Mock()
        
        cleanup_manager = ResourceCleanupManager(
            cloudwatch_client=mock_cloudwatch_client
        )
        
        # Publish metrics
        metrics = {
            'fargate_tasks_active': 5,
            's3_storage_gb': 120.5,
            'lambda_invocations': 1000000,
            'dynamodb_read_units': 50000
        }
        
        result = cleanup_manager.publish_resource_usage_metrics(
            workflow_id='test-workflow-123',
            metrics=metrics
        )
        
        # Verify CloudWatch put_metric_data was called
        mock_cloudwatch_client.put_metric_data.assert_called_once()
        call_args = mock_cloudwatch_client.put_metric_data.call_args
        
        assert call_args[1]['Namespace'] == 'RosettaZero/ResourceUsage'
        metric_data = call_args[1]['MetricData']
        
        # Verify all metrics were published
        assert len(metric_data) == 4
        
        # Verify metric structure
        for metric in metric_data:
            assert 'MetricName' in metric
            assert 'Value' in metric
            assert 'Unit' in metric
            assert 'Timestamp' in metric
            assert 'Dimensions' in metric
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            assert dimensions['WorkflowId'] == 'test-workflow-123'
            assert dimensions['Component'] == 'ResourceCleanup'
        
        # Verify result
        assert result['success'] is True
        assert result['metrics_published'] == 4
    
    def test_publish_metrics_batching(self):
        """
        Test that metrics are batched when exceeding CloudWatch limit.
        
        Requirement: 26.4
        """
        mock_cloudwatch_client = Mock()
        
        cleanup_manager = ResourceCleanupManager(
            cloudwatch_client=mock_cloudwatch_client
        )
        
        # Create 25 metrics (exceeds 20 metric batch limit)
        metrics = {f'metric_{i}': float(i) for i in range(25)}
        
        result = cleanup_manager.publish_resource_usage_metrics(
            workflow_id='test-workflow-123',
            metrics=metrics
        )
        
        # Verify CloudWatch put_metric_data was called twice (batches of 20 and 5)
        assert mock_cloudwatch_client.put_metric_data.call_count == 2
        
        # Verify first batch has 20 metrics
        first_call = mock_cloudwatch_client.put_metric_data.call_args_list[0]
        assert len(first_call[1]['MetricData']) == 20
        
        # Verify second batch has 5 metrics
        second_call = mock_cloudwatch_client.put_metric_data.call_args_list[1]
        assert len(second_call[1]['MetricData']) == 5
    
    def test_cleanup_workflow_resources_comprehensive(self):
        """
        Test comprehensive cleanup of all workflow resources.
        
        Requirements: 26.1, 26.2, 26.3, 26.4
        """
        mock_ecs_client = Mock()
        mock_s3_client = Mock()
        mock_cloudwatch_client = Mock()
        mock_metrics_publisher = Mock()
        
        # Mock successful ECS stop_task
        mock_ecs_client.stop_task.return_value = {
            'task': {
                'taskArn': 'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1',
                'stoppedAt': datetime.utcnow()
            }
        }
        
        # Mock S3 cleanup
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # Empty bucket
        
        cleanup_manager = ResourceCleanupManager(
            ecs_client=mock_ecs_client,
            s3_client=mock_s3_client,
            cloudwatch_client=mock_cloudwatch_client,
            metrics_publisher=mock_metrics_publisher
        )
        
        # Comprehensive cleanup
        result = cleanup_manager.cleanup_workflow_resources(
            workflow_id='test-workflow-123',
            cluster_name='test-cluster',
            task_arns=[
                'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1',
                'arn:aws:ecs:us-east-1:123456789012:task/cluster/task2'
            ],
            temp_buckets=['bucket1', 'bucket2']
        )
        
        # Verify tasks were terminated
        assert len(result['terminated_tasks']) == 2
        assert mock_ecs_client.stop_task.call_count == 2
        
        # Verify buckets were cleaned
        assert len(result['cleaned_buckets']) == 2
        
        # Verify metrics were published
        mock_metrics_publisher.publish_resource_utilization.assert_called()
        
        # Verify no errors
        assert len(result['errors']) == 0
    
    def test_get_metric_unit(self):
        """
        Test metric unit determination.
        
        Requirement: 26.4
        """
        cleanup_manager = ResourceCleanupManager()
        
        # Test various metric names
        assert cleanup_manager._get_metric_unit('storage_gb') == 'Gigabytes'
        assert cleanup_manager._get_metric_unit('memory_mb') == 'Megabytes'
        assert cleanup_manager._get_metric_unit('cpu_utilization') == 'Percent'
        assert cleanup_manager._get_metric_unit('task_count') == 'Count'
        assert cleanup_manager._get_metric_unit('execution_seconds') == 'Seconds'
        assert cleanup_manager._get_metric_unit('unknown_metric') == 'None'


class TestResourceCleanupLambdaHandler:
    """Test suite for Resource Cleanup Lambda handler."""
    
    @patch('rosetta_zero.lambdas.resource_cleanup.handler.get_cleanup_manager')
    def test_handle_phase_completion_cleanup(self, mock_get_manager):
        """
        Test handling phase completion cleanup event.
        
        Requirement: 26.1
        """
        from rosetta_zero.lambdas.resource_cleanup.handler import handle_phase_completion_cleanup
        
        # Mock cleanup manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        mock_manager.terminate_fargate_task.return_value = {
            'success': True,
            'task_arn': 'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1'
        }
        
        mock_manager.tag_aws_resource.return_value = {
            'success': True,
            'resource_arn': 'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1'
        }
        
        mock_manager.publish_resource_usage_metrics.return_value = {
            'success': True
        }
        
        # Create phase completion event
        event = {
            'detail-type': 'Workflow Phase Completed',
            'detail': {
                'workflow_id': 'test-workflow-123',
                'phase_name': 'Validation',
                'details': {
                    'fargate_task_arns': [
                        'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1'
                    ],
                    'resource_arns': [
                        'arn:aws:ecs:us-east-1:123456789012:task/cluster/task1'
                    ],
                    'completion_timestamp': datetime.utcnow().isoformat()
                }
            }
        }
        
        # Handle cleanup
        with patch.dict('os.environ', {'ECS_CLUSTER_NAME': 'test-cluster'}):
            result = handle_phase_completion_cleanup(event)
        
        # Verify cleanup operations
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body['workflow_id'] == 'test-workflow-123'
        assert body['phase'] == 'Validation'
        assert len(body['cleanup_operations']) == 2  # terminate + tag
        assert body['metrics_published'] is True
        
        # Verify manager methods were called
        mock_manager.terminate_fargate_task.assert_called_once()
        mock_manager.tag_aws_resource.assert_called_once()
        mock_manager.publish_resource_usage_metrics.assert_called_once()
    
    @patch('rosetta_zero.lambdas.resource_cleanup.handler.get_cleanup_manager')
    def test_handle_scheduled_cleanup(self, mock_get_manager):
        """
        Test handling scheduled cleanup event.
        
        Requirement: 26.2
        """
        from rosetta_zero.lambdas.resource_cleanup.handler import handle_scheduled_cleanup
        
        # Mock cleanup manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        mock_manager.cleanup_temporary_s3_objects.return_value = {
            'success': True,
            'deleted_count': 10,
            'total_size_bytes': 10240
        }
        
        mock_manager.publish_resource_usage_metrics.return_value = {
            'success': True
        }
        
        # Create scheduled event
        event = {
            'source': 'aws.events',
            'detail-type': 'Scheduled Event'
        }
        
        # Handle cleanup
        with patch.dict('os.environ', {'TEMP_BUCKETS': 'bucket1,bucket2'}):
            result = handle_scheduled_cleanup(event)
        
        # Verify cleanup operations
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body['cleanup_type'] == 'scheduled'
        assert len(body['buckets_cleaned']) == 2
        assert body['metrics_published'] is True
        
        # Verify manager methods were called
        assert mock_manager.cleanup_temporary_s3_objects.call_count == 2
        mock_manager.publish_resource_usage_metrics.assert_called_once()
