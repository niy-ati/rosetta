"""
Integration tests for monitoring infrastructure.

Tests CloudWatch Logs ingestion, EventBridge event publishing,
SNS notifications, and metrics publishing.

Requirements: 18.1-18.7, 29.1-29.5
"""

import json
import os
import uuid
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any

import pytest
from botocore.exceptions import ClientError

# Set AWS region before importing monitoring modules
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['KMS_KEY_ID'] = 'arn:aws:kms:us-east-1:123456789012:key/test-key'
os.environ['SNS_TOPIC_ARN'] = 'arn:aws:sns:us-east-1:123456789012:test-topic'

from rosetta_zero.utils.monitoring import (
    CloudWatchLogsManager,
    EventBridgeManager,
    SNSNotificationManager,
    PerformanceMetricsPublisher,
)
from rosetta_zero.utils.logging import (
    log_ingestion_engine_decision,
    log_bedrock_architect_decision,
    log_hostile_auditor_decision,
    log_verification_environment_decision,
    log_test_failure_immutable,
    log_aws_500_error,
)


# Test fixtures

@pytest.fixture
def mock_logs_client():
    """Create mock CloudWatch Logs client."""
    with patch('boto3.client') as mock_client:
        logs_client = Mock()
        mock_client.return_value = logs_client
        yield logs_client


@pytest.fixture
def mock_events_client():
    """Create mock EventBridge client."""
    with patch('boto3.client') as mock_client:
        events_client = Mock()
        mock_client.return_value = events_client
        yield events_client


@pytest.fixture
def mock_sns_client():
    """Create mock SNS client."""
    with patch('boto3.client') as mock_client:
        sns_client = Mock()
        mock_client.return_value = sns_client
        yield sns_client


@pytest.fixture
def mock_cloudwatch_client():
    """Create mock CloudWatch client."""
    with patch('boto3.client') as mock_client:
        cloudwatch_client = Mock()
        mock_client.return_value = cloudwatch_client
        yield cloudwatch_client


# Integration Tests

class TestCloudWatchLogsIngestion:
    """
    Test CloudWatch Logs ingestion with encryption and retention.
    
    Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6
    """
    
    def test_configure_log_group_with_encryption_and_retention(self):
        """
        Test log group configuration with KMS encryption and 7-year retention.
        
        Requirement 18.5: Configure CloudWatch Logs with 7-year retention
        Requirement 18.6: Enable CloudWatch Logs encryption using AWS KMS
        """
        with patch('boto3.client') as mock_boto_client:
            logs_client = Mock()
            mock_boto_client.return_value = logs_client
            
            # Mock successful log group creation
            logs_client.create_log_group.return_value = {}
            logs_client.put_retention_policy.return_value = {}
            logs_client.associate_kms_key.return_value = {}
            
            # Create CloudWatch Logs Manager
            logs_manager = CloudWatchLogsManager(
                kms_key_id='arn:aws:kms:us-east-1:123456789012:key/test-key',
                retention_days=2555  # 7 years
            )
            
            # Configure log group
            result = logs_manager.configure_log_group(
                log_group_name='/aws/lambda/rosetta-zero-test'
            )
            
            # Verify log group was created
            logs_client.create_log_group.assert_called_once_with(
                logGroupName='/aws/lambda/rosetta-zero-test'
            )
            
            # Verify retention policy was set (Requirement 18.5)
            logs_client.put_retention_policy.assert_called_once_with(
                logGroupName='/aws/lambda/rosetta-zero-test',
                retentionInDays=2555
            )
            
            # Verify KMS encryption was enabled (Requirement 18.6)
            logs_client.associate_kms_key.assert_called_once_with(
                logGroupName='/aws/lambda/rosetta-zero-test',
                kmsKeyId='arn:aws:kms:us-east-1:123456789012:key/test-key'
            )
            
            # Verify result
            assert result['log_group_name'] == '/aws/lambda/rosetta-zero-test'
            assert result['retention_days'] == 2555
            assert result['kms_encrypted'] is True
            assert result['kms_key_id'] == 'arn:aws:kms:us-east-1:123456789012:key/test-key'
    
    def test_configure_log_group_already_exists(self):
        """
        Test log group configuration when log group already exists.
        
        Requirement 18.5: Configure CloudWatch Logs with retention
        """
        with patch('boto3.client') as mock_boto_client:
            logs_client = Mock()
            mock_boto_client.return_value = logs_client
            
            # Mock log group already exists
            logs_client.create_log_group.side_effect = ClientError(
                {'Error': {'Code': 'ResourceAlreadyExistsException'}},
                'CreateLogGroup'
            )
            logs_client.put_retention_policy.return_value = {}
            logs_client.associate_kms_key.return_value = {}
            
            # Create CloudWatch Logs Manager
            logs_manager = CloudWatchLogsManager(
                kms_key_id='arn:aws:kms:us-east-1:123456789012:key/test-key',
                retention_days=2555
            )
            
            # Configure log group (should not raise exception)
            result = logs_manager.configure_log_group(
                log_group_name='/aws/lambda/rosetta-zero-existing'
            )
            
            # Verify retention and encryption were still configured
            logs_client.put_retention_policy.assert_called_once()
            logs_client.associate_kms_key.assert_called_once()
            
            assert result['log_group_name'] == '/aws/lambda/rosetta-zero-existing'
    
    def test_structured_json_logging_format(self):
        """
        Test structured JSON logging format configuration.
        
        Requirement 18.4: Structured JSON logging format
        """
        with patch('boto3.client') as mock_boto_client:
            logs_client = Mock()
            mock_boto_client.return_value = logs_client
            
            logs_manager = CloudWatchLogsManager()
            
            # Configure structured logging
            result = logs_manager.configure_structured_logging(
                log_group_name='/aws/lambda/rosetta-zero-test',
                log_format='json'
            )
            
            # Verify configuration
            assert result['log_group_name'] == '/aws/lambda/rosetta-zero-test'
            assert result['log_format'] == 'json'
            assert result['structured'] is True
    
    def test_immutable_audit_logging_ingestion_engine(self):
        """
        Test immutable audit logging for Ingestion Engine decisions.
        
        Requirement 18.1: Log all Ingestion Engine decisions to CloudWatch
        """
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            # Log Ingestion Engine decision
            log_ingestion_engine_decision(
                artifact_id='artifact-123',
                decision_type='logic_map_extraction',
                decision='extracted_logic_map',
                details={
                    'entry_points': 5,
                    'data_structures': 12,
                    'side_effects': 3
                }
            )
            
            # Verify log was created
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Verify log contains audit trail markers
            log_extra = call_args[1]['extra']
            assert log_extra['audit_log'] is True
            assert log_extra['immutable'] is True
            assert log_extra['component'] == 'ingestion_engine'
            assert log_extra['decision_type'] == 'logic_map_extraction'
            assert log_extra['artifact_id'] == 'artifact-123'
    
    def test_immutable_audit_logging_bedrock_architect(self):
        """
        Test immutable audit logging for Bedrock Architect decisions.
        
        Requirement 18.2: Log all Bedrock Architect decisions to CloudWatch
        """
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            # Log Bedrock Architect decision
            log_bedrock_architect_decision(
                logic_map_id='logic-map-456',
                decision_type='code_synthesis',
                decision='generated_lambda_function',
                details={
                    'language': 'python',
                    'lines_of_code': 250,
                    'side_effects_preserved': 3
                }
            )
            
            # Verify log was created
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Verify log contains audit trail markers
            log_extra = call_args[1]['extra']
            assert log_extra['audit_log'] is True
            assert log_extra['immutable'] is True
            assert log_extra['component'] == 'bedrock_architect'
            assert log_extra['decision_type'] == 'code_synthesis'
            assert log_extra['artifact_id'] == 'logic-map-456'
    
    def test_immutable_audit_logging_hostile_auditor(self):
        """
        Test immutable audit logging for Hostile Auditor decisions.
        
        Requirement 18.3: Log all Hostile Auditor decisions to CloudWatch
        """
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            # Log Hostile Auditor decision
            log_hostile_auditor_decision(
                logic_map_id='logic-map-789',
                decision_type='test_vector_generation',
                decision='generated_1000000_test_vectors',
                details={
                    'total_vectors': 1000000,
                    'boundary_tests': 50000,
                    'coverage_percent': 98.5
                }
            )
            
            # Verify log was created
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Verify log contains audit trail markers
            log_extra = call_args[1]['extra']
            assert log_extra['audit_log'] is True
            assert log_extra['immutable'] is True
            assert log_extra['component'] == 'hostile_auditor'
            assert log_extra['decision_type'] == 'test_vector_generation'
            assert log_extra['artifact_id'] == 'logic-map-789'
    
    def test_immutable_audit_logging_verification_environment(self):
        """
        Test immutable audit logging for Verification Environment decisions.
        
        Requirement 18.4: Log all Verification Environment decisions to CloudWatch
        """
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            # Log Verification Environment decision
            log_verification_environment_decision(
                test_vector_id='test-vector-101',
                decision_type='output_comparison',
                decision='outputs_match',
                details={
                    'return_value_match': True,
                    'stdout_match': True,
                    'stderr_match': True,
                    'side_effects_match': True
                }
            )
            
            # Verify log was created
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            # Verify log contains audit trail markers
            log_extra = call_args[1]['extra']
            assert log_extra['audit_log'] is True
            assert log_extra['immutable'] is True
            assert log_extra['component'] == 'verification_environment'
            assert log_extra['decision_type'] == 'output_comparison'
            assert log_extra['artifact_id'] == 'test-vector-101'
    
    def test_log_test_failure_before_correction(self):
        """
        Test logging test failure before any correction attempts.
        
        Requirement 18.7: Log test failures before any correction attempts
        """
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            # Log test failure
            log_test_failure_immutable(
                test_vector_id='test-vector-202',
                legacy_result_hash='abc123def456',
                modern_result_hash='ghi789jkl012',
                discrepancy_report_id='discrepancy-303',
                differences={
                    'return_value_match': False,
                    'stdout_match': True,
                    'stderr_match': True,
                    'side_effects_match': False
                }
            )
            
            # Verify error log was created
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            
            # Verify log contains audit trail markers
            log_extra = call_args[1]['extra']
            assert log_extra['audit_log'] is True
            assert log_extra['immutable'] is True
            assert log_extra['event_type'] == 'test_failure'
            assert log_extra['component'] == 'verification_environment'
            assert log_extra['test_vector_id'] == 'test-vector-202'
            assert log_extra['logged_before_correction'] is True
            assert log_extra['discrepancy_report_id'] == 'discrepancy-303'


class TestEventBridgeEventPublishing:
    """
    Test EventBridge event publishing for various system events.
    
    Requirements: 17.9, 19.3, 24.6, 25.5
    """
    
    def test_publish_certificate_generation_event(self):
        """
        Test publishing certificate generation event to EventBridge.
        
        Requirement 17.9: Publish certificate generation event to EventBridge
        """
        with patch('boto3.client') as mock_boto_client:
            events_client = Mock()
            mock_boto_client.return_value = events_client
            
            # Mock successful event publication
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-123'}]
            }
            
            # Create EventBridge Manager
            events_manager = EventBridgeManager(event_bus_name='default')
            
            # Publish certificate event
            result = events_manager.publish_certificate_event(
                certificate_id='cert-456',
                s3_location='s3://bucket/certificates/cert-456.json',
                total_tests=1000000,
                coverage_percent=98.5
            )
            
            # Verify event was published
            events_client.put_events.assert_called_once()
            call_args = events_client.put_events.call_args[1]
            
            # Verify event structure
            entries = call_args['Entries']
            assert len(entries) == 1
            entry = entries[0]
            assert entry['Source'] == 'rosetta-zero.certificate-generator'
            assert entry['DetailType'] == 'Certificate Generated'
            assert entry['EventBusName'] == 'default'
            
            # Verify event detail
            detail = json.loads(entry['Detail'])
            assert detail['certificate_id'] == 'cert-456'
            assert detail['s3_location'] == 's3://bucket/certificates/cert-456.json'
            assert detail['total_tests'] == 1000000
            assert detail['coverage_percent'] == 98.5
            
            # Verify result
            assert result['event_id'] == 'event-123'
            assert result['source'] == 'rosetta-zero.certificate-generator'
            assert result['detail_type'] == 'Certificate Generated'
    
    def test_publish_aws_500_error_event(self):
        """
        Test publishing AWS 500-level error event to EventBridge.
        
        Requirement 19.3: Publish AWS 500-level error events
        """
        with patch('boto3.client') as mock_boto_client:
            events_client = Mock()
            mock_boto_client.return_value = events_client
            
            # Mock successful event publication
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-789'}]
            }
            
            # Create EventBridge Manager
            events_manager = EventBridgeManager(event_bus_name='default')
            
            # Publish AWS 500 error event
            result = events_manager.publish_error_event(
                service='bedrock',
                error_code='InternalServerError',
                error_message='Service temporarily unavailable',
                context={'operation': 'InvokeModel', 'retry_count': 3}
            )
            
            # Verify event was published
            events_client.put_events.assert_called_once()
            call_args = events_client.put_events.call_args[1]
            
            # Verify event structure
            entries = call_args['Entries']
            assert len(entries) == 1
            entry = entries[0]
            assert entry['Source'] == 'rosetta-zero.bedrock'
            assert entry['DetailType'] == 'AWS 500-Level Error'
            
            # Verify event detail
            detail = json.loads(entry['Detail'])
            assert detail['service'] == 'bedrock'
            assert detail['error_code'] == 'InternalServerError'
            assert detail['error_message'] == 'Service temporarily unavailable'
            assert detail['context']['operation'] == 'InvokeModel'
            assert detail['context']['retry_count'] == 3
    
    def test_publish_behavioral_discrepancy_event(self):
        """
        Test publishing behavioral discrepancy event to EventBridge.
        
        Requirement 24.6: Publish workflow events to EventBridge
        """
        with patch('boto3.client') as mock_boto_client:
            events_client = Mock()
            mock_boto_client.return_value = events_client
            
            # Mock successful event publication
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-abc'}]
            }
            
            # Create EventBridge Manager
            events_manager = EventBridgeManager(event_bus_name='default')
            
            # Publish discrepancy event
            result = events_manager.publish_discrepancy_event(
                test_vector_id='test-vector-999',
                discrepancy_report_id='discrepancy-888',
                s3_location='s3://bucket/discrepancies/discrepancy-888.json'
            )
            
            # Verify event was published
            events_client.put_events.assert_called_once()
            call_args = events_client.put_events.call_args[1]
            
            # Verify event structure
            entries = call_args['Entries']
            assert len(entries) == 1
            entry = entries[0]
            assert entry['Source'] == 'rosetta-zero.verification-environment'
            assert entry['DetailType'] == 'Behavioral Discrepancy Detected'
            
            # Verify event detail
            detail = json.loads(entry['Detail'])
            assert detail['test_vector_id'] == 'test-vector-999'
            assert detail['discrepancy_report_id'] == 'discrepancy-888'
            assert detail['s3_location'] == 's3://bucket/discrepancies/discrepancy-888.json'
    
    def test_publish_workflow_phase_completion_event(self):
        """
        Test publishing workflow phase completion event to EventBridge.
        
        Requirement 24.6: Publish phase completion events to EventBridge
        """
        with patch('boto3.client') as mock_boto_client:
            events_client = Mock()
            mock_boto_client.return_value = events_client
            
            # Mock successful event publication
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-def'}]
            }
            
            # Create EventBridge Manager
            events_manager = EventBridgeManager(event_bus_name='default')
            
            # Publish phase completion event
            result = events_manager.publish_phase_completion_event(
                workflow_id='workflow-777',
                phase_name='Discovery',
                status='SUCCESS',
                details={
                    'artifacts_processed': 1,
                    'logic_maps_generated': 1,
                    'duration_seconds': 120
                }
            )
            
            # Verify event was published
            events_client.put_events.assert_called_once()
            call_args = events_client.put_events.call_args[1]
            
            # Verify event structure
            entries = call_args['Entries']
            assert len(entries) == 1
            entry = entries[0]
            assert entry['Source'] == 'rosetta-zero.workflow'
            assert entry['DetailType'] == 'Workflow Phase Completed'
            
            # Verify event detail
            detail = json.loads(entry['Detail'])
            assert detail['workflow_id'] == 'workflow-777'
            assert detail['phase_name'] == 'Discovery'
            assert detail['status'] == 'SUCCESS'
            assert detail['details']['artifacts_processed'] == 1
    
    def test_event_publishing_error_handling(self):
        """
        Test error handling when EventBridge event publishing fails.
        """
        with patch('boto3.client') as mock_boto_client:
            events_client = Mock()
            mock_boto_client.return_value = events_client
            
            # Mock EventBridge error
            events_client.put_events.side_effect = ClientError(
                {'Error': {'Code': 'InternalException'}},
                'PutEvents'
            )
            
            # Create EventBridge Manager
            events_manager = EventBridgeManager(event_bus_name='default')
            
            # Attempt to publish event (should raise exception)
            with pytest.raises(ClientError):
                events_manager.publish_certificate_event(
                    certificate_id='cert-error',
                    s3_location='s3://bucket/cert-error.json',
                    total_tests=1000,
                    coverage_percent=95.0
                )


class TestSNSNotifications:
    """
    Test SNS notifications for operator alerts.
    
    Requirements: 19.3, 19.4
    """
    
    def test_publish_operator_alert(self):
        """
        Test publishing operator alert to SNS topic.
        
        Requirement 19.3: Notify operators via SNS for AWS 500-level errors
        Requirement 19.4: Pause execution until operator intervention
        """
        with patch('boto3.client') as mock_boto_client:
            sns_client = Mock()
            mock_boto_client.return_value = sns_client
            
            # Mock successful SNS publication
            sns_client.publish.return_value = {
                'MessageId': 'msg-123'
            }
            
            # Create SNS Notification Manager
            sns_manager = SNSNotificationManager(
                topic_arn='arn:aws:sns:us-east-1:123456789012:operator-alerts'
            )
            
            # Publish operator alert
            result = sns_manager.publish_operator_alert(
                subject='Test Failure Detected',
                message='Behavioral discrepancy found in test vector test-456',
                severity='HIGH',
                context={'test_vector_id': 'test-456'}
            )
            
            # Verify SNS publish was called
            sns_client.publish.assert_called_once()
            call_args = sns_client.publish.call_args[1]
            
            # Verify SNS message structure
            assert call_args['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:operator-alerts'
            assert call_args['Subject'] == '[HIGH] Rosetta Zero Alert: Test Failure Detected'
            
            # Verify message content
            message = json.loads(call_args['Message'])
            assert message['subject'] == 'Test Failure Detected'
            assert message['message'] == 'Behavioral discrepancy found in test vector test-456'
            assert message['severity'] == 'HIGH'
            assert message['context']['test_vector_id'] == 'test-456'
            
            # Verify result
            assert result['message_id'] == 'msg-123'
            assert result['subject'] == 'Test Failure Detected'
            assert result['severity'] == 'HIGH'
    
    def test_publish_aws_500_error_alert(self):
        """
        Test publishing AWS 500-level error alert to SNS.
        
        Requirement 19.3: Notify operators via SNS for AWS 500-level errors
        Requirement 19.4: Pause execution until operator intervention
        """
        with patch('boto3.client') as mock_boto_client:
            sns_client = Mock()
            mock_boto_client.return_value = sns_client
            
            # Mock successful SNS publication
            sns_client.publish.return_value = {
                'MessageId': 'msg-456'
            }
            
            # Create SNS Notification Manager
            sns_manager = SNSNotificationManager(
                topic_arn='arn:aws:sns:us-east-1:123456789012:operator-alerts'
            )
            
            # Publish AWS 500 error alert
            result = sns_manager.publish_aws_500_error_alert(
                service='bedrock',
                operation='InvokeModel',
                error_code='InternalServerError',
                error_message='Service temporarily unavailable',
                context={'retry_count': 3, 'workflow_id': 'workflow-123'}
            )
            
            # Verify SNS publish was called
            sns_client.publish.assert_called_once()
            call_args = sns_client.publish.call_args[1]
            
            # Verify SNS message structure
            assert call_args['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:operator-alerts'
            assert call_args['Subject'] == '[CRITICAL] Rosetta Zero Alert: AWS 500-Level Error in bedrock'
            
            # Verify message content
            message = json.loads(call_args['Message'])
            assert message['severity'] == 'CRITICAL'
            assert message['context']['service'] == 'bedrock'
            assert message['context']['operation'] == 'InvokeModel'
            assert message['context']['error_code'] == 'InternalServerError'
            assert message['context']['retry_count'] == 3
    
    def test_sns_notification_without_topic_arn(self):
        """
        Test SNS notification when topic ARN is not configured.
        """
        # Temporarily remove SNS_TOPIC_ARN from environment
        original_topic_arn = os.environ.get('SNS_TOPIC_ARN')
        if 'SNS_TOPIC_ARN' in os.environ:
            del os.environ['SNS_TOPIC_ARN']
        
        try:
            with patch('boto3.client') as mock_boto_client:
                sns_client = Mock()
                mock_boto_client.return_value = sns_client
                
                # Create SNS Notification Manager without topic ARN
                sns_manager = SNSNotificationManager(topic_arn=None)
                
                # Attempt to publish alert (should skip and return early)
                result = sns_manager.publish_operator_alert(
                    subject='Test Alert',
                    message='Test message',
                    severity='LOW'
                )
                
                # Verify result indicates skipped
                assert result['skipped'] is True
                
                # Verify SNS publish was not called (early return)
                sns_client.publish.assert_not_called()
        finally:
            # Restore original environment variable
            if original_topic_arn:
                os.environ['SNS_TOPIC_ARN'] = original_topic_arn
    
    def test_sns_notification_error_handling(self):
        """
        Test error handling when SNS notification fails.
        """
        with patch('boto3.client') as mock_boto_client:
            sns_client = Mock()
            mock_boto_client.return_value = sns_client
            
            # Mock SNS error
            sns_client.publish.side_effect = ClientError(
                {'Error': {'Code': 'InternalError'}},
                'Publish'
            )
            
            # Create SNS Notification Manager
            sns_manager = SNSNotificationManager(
                topic_arn='arn:aws:sns:us-east-1:123456789012:operator-alerts'
            )
            
            # Attempt to publish alert (should raise exception)
            with pytest.raises(ClientError):
                sns_manager.publish_operator_alert(
                    subject='Test Alert',
                    message='Test message',
                    severity='HIGH'
                )


class TestMetricsPublishing:
    """
    Test performance metrics publishing to CloudWatch.
    
    Requirements: 29.1, 29.2, 29.3, 29.4
    """
    
    def test_publish_test_execution_duration_metric(self):
        """
        Test publishing test execution duration metric.
        
        Requirement 29.1: Publish test execution duration metrics to CloudWatch
        """
        with patch('boto3.client') as mock_boto_client:
            cloudwatch_client = Mock()
            mock_boto_client.return_value = cloudwatch_client
            
            # Mock successful metric publication
            cloudwatch_client.put_metric_data.return_value = {}
            
            # Create Performance Metrics Publisher
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            
            # Publish test execution duration metric
            metrics_publisher.publish_test_execution_duration(
                test_id='test-123',
                duration_ms=1500,
                implementation_type='legacy'
            )
            
            # Verify metric was published
            cloudwatch_client.put_metric_data.assert_called_once()
            call_args = cloudwatch_client.put_metric_data.call_args[1]
            
            # Verify metric structure
            assert call_args['Namespace'] == 'RosettaZero'
            metric_data = call_args['MetricData']
            assert len(metric_data) == 1
            
            metric = metric_data[0]
            assert metric['MetricName'] == 'TestExecutionDuration'
            assert metric['Value'] == 1500
            assert metric['Unit'] == 'Milliseconds'
            assert len(metric['Dimensions']) == 1
            assert metric['Dimensions'][0]['Name'] == 'ImplementationType'
            assert metric['Dimensions'][0]['Value'] == 'legacy'
    
    def test_publish_test_throughput_metric(self):
        """
        Test publishing test throughput metric.
        
        Requirement 29.2: Publish test throughput metrics to CloudWatch
        """
        with patch('boto3.client') as mock_boto_client:
            cloudwatch_client = Mock()
            mock_boto_client.return_value = cloudwatch_client
            
            # Mock successful metric publication
            cloudwatch_client.put_metric_data.return_value = {}
            
            # Create Performance Metrics Publisher
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            
            # Publish test throughput metric
            metrics_publisher.publish_test_throughput(
                tests_per_second=100.5,
                component='verification-environment'
            )
            
            # Verify metric was published
            cloudwatch_client.put_metric_data.assert_called_once()
            call_args = cloudwatch_client.put_metric_data.call_args[1]
            
            # Verify metric structure
            metric_data = call_args['MetricData']
            assert len(metric_data) == 1
            
            metric = metric_data[0]
            assert metric['MetricName'] == 'TestThroughput'
            assert metric['Value'] == 100.5
            assert metric['Unit'] == 'Count/Second'
            assert metric['Dimensions'][0]['Name'] == 'Component'
            assert metric['Dimensions'][0]['Value'] == 'verification-environment'
    
    def test_publish_api_latency_metric(self):
        """
        Test publishing AWS service API latency metric.
        
        Requirement 29.3: Publish AWS service API latency metrics to CloudWatch
        """
        with patch('boto3.client') as mock_boto_client:
            cloudwatch_client = Mock()
            mock_boto_client.return_value = cloudwatch_client
            
            # Mock successful metric publication
            cloudwatch_client.put_metric_data.return_value = {}
            
            # Create Performance Metrics Publisher
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            
            # Publish API latency metric
            metrics_publisher.publish_api_latency(
                service='bedrock',
                operation='InvokeModel',
                latency_ms=2500
            )
            
            # Verify metric was published
            cloudwatch_client.put_metric_data.assert_called_once()
            call_args = cloudwatch_client.put_metric_data.call_args[1]
            
            # Verify metric structure
            metric_data = call_args['MetricData']
            assert len(metric_data) == 1
            
            metric = metric_data[0]
            assert metric['MetricName'] == 'APILatency'
            assert metric['Value'] == 2500
            assert metric['Unit'] == 'Milliseconds'
            assert len(metric['Dimensions']) == 2
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            assert dimensions['Service'] == 'bedrock'
            assert dimensions['Operation'] == 'InvokeModel'
    
    def test_publish_resource_utilization_metric(self):
        """
        Test publishing resource utilization metric.
        
        Requirement 29.4: Publish resource utilization metrics to CloudWatch
        """
        with patch('boto3.client') as mock_boto_client:
            cloudwatch_client = Mock()
            mock_boto_client.return_value = cloudwatch_client
            
            # Mock successful metric publication
            cloudwatch_client.put_metric_data.return_value = {}
            
            # Create Performance Metrics Publisher
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            
            # Publish resource utilization metric
            metrics_publisher.publish_resource_utilization(
                resource_type='CPU',
                utilization_percent=75.5,
                component='hostile-auditor'
            )
            
            # Verify metric was published
            cloudwatch_client.put_metric_data.assert_called_once()
            call_args = cloudwatch_client.put_metric_data.call_args[1]
            
            # Verify metric structure
            metric_data = call_args['MetricData']
            assert len(metric_data) == 1
            
            metric = metric_data[0]
            assert metric['MetricName'] == 'ResourceUtilization'
            assert metric['Value'] == 75.5
            assert metric['Unit'] == 'Percent'
            assert len(metric['Dimensions']) == 2
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            assert dimensions['ResourceType'] == 'CPU'
            assert dimensions['Component'] == 'hostile-auditor'
    
    def test_metrics_publishing_error_handling(self):
        """
        Test error handling when metrics publishing fails.
        
        Metrics publishing failures should not break the workflow.
        """
        with patch('boto3.client') as mock_boto_client:
            cloudwatch_client = Mock()
            mock_boto_client.return_value = cloudwatch_client
            
            # Mock CloudWatch error
            cloudwatch_client.put_metric_data.side_effect = ClientError(
                {'Error': {'Code': 'InternalServiceError'}},
                'PutMetricData'
            )
            
            # Create Performance Metrics Publisher
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            
            # Publish metric (should not raise exception)
            metrics_publisher.publish_test_execution_duration(
                test_id='test-error',
                duration_ms=1000,
                implementation_type='modern'
            )
            
            # Verify metric publication was attempted
            cloudwatch_client.put_metric_data.assert_called_once()


class TestEndToEndMonitoringWorkflow:
    """
    Test end-to-end monitoring workflow integration.
    
    Tests the complete monitoring flow from decision logging to
    event publishing to operator notifications.
    """
    
    def test_complete_monitoring_workflow_success(self):
        """
        Test complete monitoring workflow for successful test execution.
        
        Simulates: Decision logging -> Metrics publishing -> Event publishing
        """
        with patch('boto3.client') as mock_boto_client, \
             patch('rosetta_zero.utils.logging.logger') as mock_logger:
            
            # Mock AWS clients
            logs_client = Mock()
            events_client = Mock()
            cloudwatch_client = Mock()
            
            def get_client(service_name, **kwargs):
                if service_name == 'logs':
                    return logs_client
                elif service_name == 'events':
                    return events_client
                elif service_name == 'cloudwatch':
                    return cloudwatch_client
                return Mock()
            
            mock_boto_client.side_effect = get_client
            
            # Mock successful responses
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-123'}]
            }
            cloudwatch_client.put_metric_data.return_value = {}
            
            # Step 1: Log verification decision
            log_verification_environment_decision(
                test_vector_id='test-complete-123',
                decision_type='output_comparison',
                decision='outputs_match',
                details={'match': True}
            )
            
            # Verify decision was logged
            mock_logger.info.assert_called()
            
            # Step 2: Publish performance metrics
            metrics_publisher = PerformanceMetricsPublisher(namespace='RosettaZero')
            metrics_publisher.publish_test_execution_duration(
                test_id='test-complete-123',
                duration_ms=1200,
                implementation_type='legacy'
            )
            
            # Verify metrics were published
            cloudwatch_client.put_metric_data.assert_called()
            
            # Step 3: Publish phase completion event
            events_manager = EventBridgeManager(event_bus_name='default')
            events_manager.publish_phase_completion_event(
                workflow_id='workflow-complete-123',
                phase_name='Validation',
                status='SUCCESS',
                details={'tests_passed': 1000000}
            )
            
            # Verify event was published
            events_client.put_events.assert_called()
    
    def test_complete_monitoring_workflow_failure(self):
        """
        Test complete monitoring workflow for test failure.
        
        Simulates: Failure logging -> Discrepancy event -> Operator alert
        """
        with patch('boto3.client') as mock_boto_client, \
             patch('rosetta_zero.utils.logging.logger') as mock_logger:
            
            # Mock AWS clients
            events_client = Mock()
            sns_client = Mock()
            
            def get_client(service_name, **kwargs):
                if service_name == 'events':
                    return events_client
                elif service_name == 'sns':
                    return sns_client
                return Mock()
            
            mock_boto_client.side_effect = get_client
            
            # Mock successful responses
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-failure-123'}]
            }
            sns_client.publish.return_value = {
                'MessageId': 'msg-failure-123'
            }
            
            # Step 1: Log test failure (BEFORE any correction attempts)
            log_test_failure_immutable(
                test_vector_id='test-failure-456',
                legacy_result_hash='legacy-hash-abc',
                modern_result_hash='modern-hash-def',
                discrepancy_report_id='discrepancy-789',
                differences={'return_value_match': False}
            )
            
            # Verify failure was logged
            mock_logger.error.assert_called()
            log_extra = mock_logger.error.call_args[1]['extra']
            assert log_extra['logged_before_correction'] is True
            
            # Step 2: Publish discrepancy event
            events_manager = EventBridgeManager(event_bus_name='default')
            events_manager.publish_discrepancy_event(
                test_vector_id='test-failure-456',
                discrepancy_report_id='discrepancy-789',
                s3_location='s3://bucket/discrepancies/discrepancy-789.json'
            )
            
            # Verify event was published
            events_client.put_events.assert_called()
            
            # Step 3: Send operator alert
            sns_manager = SNSNotificationManager(
                topic_arn='arn:aws:sns:us-east-1:123456789012:operator-alerts'
            )
            sns_manager.publish_operator_alert(
                subject='Test Failure Detected',
                message='Behavioral discrepancy in test-failure-456',
                severity='CRITICAL',
                context={'discrepancy_report_id': 'discrepancy-789'}
            )
            
            # Verify alert was sent
            sns_client.publish.assert_called()
    
    def test_aws_500_error_monitoring_workflow(self):
        """
        Test monitoring workflow for AWS 500-level errors.
        
        Simulates: Error logging -> Error event -> Critical operator alert
        """
        with patch('boto3.client') as mock_boto_client, \
             patch('rosetta_zero.utils.logging.logger') as mock_logger:
            
            # Mock AWS clients
            events_client = Mock()
            sns_client = Mock()
            
            def get_client(service_name, **kwargs):
                if service_name == 'events':
                    return events_client
                elif service_name == 'sns':
                    return sns_client
                return Mock()
            
            mock_boto_client.side_effect = get_client
            
            # Mock successful responses
            events_client.put_events.return_value = {
                'Entries': [{'EventId': 'event-500-error'}]
            }
            sns_client.publish.return_value = {
                'MessageId': 'msg-500-error'
            }
            
            # Step 1: Log AWS 500 error
            log_aws_500_error(
                service='bedrock',
                operation='InvokeModel',
                error_code='InternalServerError',
                error_message='Service temporarily unavailable',
                context={'retry_count': 3, 'workflow_id': 'workflow-500'}
            )
            
            # Verify error was logged
            mock_logger.critical.assert_called()
            
            # Step 2: Publish error event
            events_manager = EventBridgeManager(event_bus_name='default')
            events_manager.publish_error_event(
                service='bedrock',
                error_code='InternalServerError',
                error_message='Service temporarily unavailable',
                context={'operation': 'InvokeModel', 'retry_count': 3}
            )
            
            # Verify event was published
            events_client.put_events.assert_called()
            
            # Step 3: Send critical operator alert
            sns_manager = SNSNotificationManager(
                topic_arn='arn:aws:sns:us-east-1:123456789012:operator-alerts'
            )
            sns_manager.publish_aws_500_error_alert(
                service='bedrock',
                operation='InvokeModel',
                error_code='InternalServerError',
                error_message='Service temporarily unavailable',
                context={'retry_count': 3, 'workflow_id': 'workflow-500'}
            )
            
            # Verify critical alert was sent
            sns_client.publish.assert_called()
            call_args = sns_client.publish.call_args[1]
            assert '[CRITICAL]' in call_args['Subject']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
