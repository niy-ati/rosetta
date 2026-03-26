"""
Integration tests for workflow orchestration.

Tests end-to-end workflow execution, phase transitions, error recovery,
and operator notifications.

Requirements: 19.1-19.5, 24.1-24.7
"""

import json
import os
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from botocore.exceptions import ClientError

# Set AWS region before importing modules that create boto3 clients
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_REGION'] = 'us-east-1'

from rosetta_zero.lambdas.workflow_orchestrator.handler import (
    orchestrator_handler,
    handle_artifact_upload,
    handle_phase_completion,
    trigger_ingestion_engine,
    trigger_synthesis_phase,
    trigger_aggression_phase,
    trigger_validation_phase,
    trigger_trust_phase,
    handle_workflow_completion
)
from rosetta_zero.utils.workflow import WorkflowPhase, PhaseStatus


@pytest.fixture
def mock_aws_clients():
    """Mock all AWS clients used in workflow orchestration."""
    with patch('boto3.client') as mock_boto_client, \
         patch('boto3.resource') as mock_boto_resource:
        
        # Mock Lambda client
        mock_lambda = MagicMock()
        mock_lambda.invoke.return_value = {
            'StatusCode': 202,
            'ResponseMetadata': {'RequestId': 'test-request-id'}
        }
        
        # Mock Step Functions client
        mock_sfn = MagicMock()
        mock_sfn.start_execution.return_value = {
            'executionArn': 'arn:aws:states:us-east-1:123456789012:execution:test',
            'startDate': datetime.utcnow()
        }
        
        # Mock DynamoDB resource
        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        mock_table.update_item.return_value = {
            'Attributes': {
                'workflow_id': 'test-workflow',
                'phase_name': 'Discovery',
                'status': 'COMPLETED'
            }
        }
        mock_dynamodb.Table.return_value = mock_table
        
        # Mock EventBridge client
        mock_events = MagicMock()
        mock_events.put_events.return_value = {
            'Entries': [{'EventId': 'event-123'}]
        }
        
        # Configure boto3.client to return appropriate mocks
        def client_factory(service_name, **kwargs):
            if service_name == 'lambda':
                return mock_lambda
            elif service_name == 'stepfunctions':
                return mock_sfn
            elif service_name == 'events':
                return mock_events
            return MagicMock()
        
        mock_boto_client.side_effect = client_factory
        mock_boto_resource.return_value = mock_dynamodb
        
        yield {
            'lambda': mock_lambda,
            'stepfunctions': mock_sfn,
            'dynamodb': mock_dynamodb,
            'events': mock_events,
            'table': mock_table
        }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "rosetta-zero-workflow-orchestrator"
    context.aws_request_id = "test-request-id"
    return context


class TestEndToEndWorkflowExecution:
    """
    Test end-to-end workflow execution through all five phases.
    
    Requirements: 19.1, 24.1-24.7
    """
    
    def test_complete_workflow_execution_all_phases(self, mock_aws_clients, lambda_context):
        """
        Test complete workflow execution from artifact upload through all phases to completion.
        
        Validates:
        - Artifact upload triggers Discovery phase
        - Discovery completion triggers Synthesis phase
        - Synthesis completion triggers Aggression phase
        - Aggression completion triggers Validation phase
        - Validation completion triggers Trust phase
        - Trust completion completes workflow
        
        Requirements: 19.1, 24.1-24.7
        """
        # Phase 1: Artifact Upload -> Discovery
        s3_event = {
            "Records": [{
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": "rosetta-zero-legacy-artifacts"},
                    "object": {"key": "cobol/payroll-system.cbl"}
                }
            }]
        }
        
        result = orchestrator_handler(s3_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Discovery"
        assert body["status"] == "triggered"
        workflow_id = body["workflow_id"]
        
        # Verify Discovery phase was triggered
        mock_aws_clients['lambda'].invoke.assert_called()
        
        # Phase 2: Discovery Complete -> Synthesis
        discovery_event = {
            "version": "0",
            "detail-type": "Workflow Phase Completed",
            "source": "rosetta-zero.workflow",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Discovery",
                "status": "SUCCESS",
                "details": {
                    "logic_map_location": "s3://bucket/logic-maps/test.json",
                    "ears_location": "s3://bucket/ears/test.json"
                }
            }
        }
        
        result = orchestrator_handler(discovery_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Synthesis"
        assert body["status"] == "triggered"
        
        # Phase 3: Synthesis Complete -> Aggression
        synthesis_event = {
            "version": "0",
            "detail-type": "Workflow Phase Completed",
            "source": "rosetta-zero.workflow",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Synthesis",
                "status": "SUCCESS",
                "details": {
                    "logic_map_location": "s3://bucket/logic-maps/test.json",
                    "modern_implementation_location": "s3://bucket/modern/test.py"
                }
            }
        }
        
        result = orchestrator_handler(synthesis_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Aggression"
        assert body["status"] == "triggered"
        
        # Phase 4: Aggression Complete -> Validation
        aggression_event = {
            "version": "0",
            "detail-type": "Workflow Phase Completed",
            "source": "rosetta-zero.workflow",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Aggression",
                "status": "SUCCESS",
                "details": {
                    "test_vectors_location": "s3://bucket/vectors/batch-1.json",
                    "total_vectors": 1000000,
                    "coverage_percent": 96.5
                }
            }
        }
        
        result = orchestrator_handler(aggression_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Validation"
        assert body["status"] == "triggered"
        
        # Verify Step Functions was invoked for Validation
        mock_aws_clients['stepfunctions'].start_execution.assert_called()
        
        # Phase 5: Validation Complete -> Trust
        validation_event = {
            "version": "0",
            "detail-type": "Workflow Phase Completed",
            "source": "rosetta-zero.workflow",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Validation",
                "status": "SUCCESS",
                "details": {
                    "test_results_summary": {"passed": 1000000, "failed": 0},
                    "total_tests": 1000000,
                    "coverage_report": {"branch_coverage": 96.5}
                }
            }
        }
        
        result = orchestrator_handler(validation_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Trust"
        assert body["status"] == "triggered"
        
        # Phase 6: Trust Complete -> Workflow Complete
        trust_event = {
            "version": "0",
            "detail-type": "Workflow Phase Completed",
            "source": "rosetta-zero.workflow",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Trust",
                "status": "SUCCESS",
                "details": {
                    "certificate_id": "cert-123",
                    "certificate_location": "s3://bucket/certificates/cert-123.json"
                }
            }
        }
        
        result = orchestrator_handler(trust_event, lambda_context)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "completed"
        assert "completion_timestamp" in body
        assert body["certificate_location"] == "s3://bucket/certificates/cert-123.json"
    
    def test_workflow_phase_tracking_in_dynamodb(self, mock_aws_clients):
        """
        Test that workflow phases are tracked correctly in DynamoDB.
        
        Requirements: 24.1-24.7
        """
        workflow_id = "test-workflow-123"
        
        # Simulate artifact upload
        s3_event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "test.cbl"}
                }
            }]
        }
        
        with patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker') as mock_tracker:
            mock_tracker_instance = Mock()
            mock_tracker.return_value = mock_tracker_instance
            
            handle_artifact_upload(s3_event)
            
            # Verify workflow was created
            mock_tracker_instance.create_workflow.assert_called_once()
            
            # Verify Discovery phase was started
            mock_tracker_instance.start_phase.assert_called_with(
                workflow_id=mock_tracker_instance.create_workflow.call_args[1]['workflow_id'],
                phase=WorkflowPhase.DISCOVERY
            )


class TestPhaseTransitions:
    """
    Test phase transitions and event publishing.
    
    Requirements: 24.6
    """
    
    def test_phase_completion_publishes_eventbridge_event(self, mock_aws_clients):
        """
        Test that phase completion publishes event to EventBridge.
        
        Requirements: 24.6
        """
        from rosetta_zero.utils.workflow import WorkflowPhaseTracker
        
        tracker = WorkflowPhaseTracker()
        
        result = tracker.complete_phase(
            workflow_id="test-workflow",
            phase=WorkflowPhase.DISCOVERY,
            details={"logic_map_location": "s3://bucket/logic-map.json"}
        )
        
        # Verify event was published
        assert result['event_published'] is True
        assert result['event_id'] == 'event-123'
        assert result['next_phase'] == WorkflowPhase.SYNTHESIS.value
        
        # Verify EventBridge was called
        mock_aws_clients['events'].put_events.assert_called_once()
        call_args = mock_aws_clients['events'].put_events.call_args
        event_entry = call_args[1]['Entries'][0]
        
        assert event_entry['Source'] == 'rosetta-zero.workflow'
        assert event_entry['DetailType'] == 'Workflow Phase Completed'
        
        detail = json.loads(event_entry['Detail'])
        assert detail['workflow_id'] == 'test-workflow'
        assert detail['phase_name'] == 'Discovery'
        assert detail['status'] == 'SUCCESS'
        assert detail['details']['next_phase'] == 'Synthesis'
    
    def test_all_phase_transitions_in_sequence(self, mock_aws_clients):
        """
        Test all phase transitions occur in correct sequence.
        
        Requirements: 24.1-24.5
        """
        from rosetta_zero.utils.workflow import WorkflowPhaseTracker
        
        tracker = WorkflowPhaseTracker()
        workflow_id = "test-workflow"
        
        phases = [
            (WorkflowPhase.DISCOVERY, WorkflowPhase.SYNTHESIS),
            (WorkflowPhase.SYNTHESIS, WorkflowPhase.AGGRESSION),
            (WorkflowPhase.AGGRESSION, WorkflowPhase.VALIDATION),
            (WorkflowPhase.VALIDATION, WorkflowPhase.TRUST),
            (WorkflowPhase.TRUST, None)
        ]
        
        for current_phase, expected_next in phases:
            result = tracker.complete_phase(
                workflow_id=workflow_id,
                phase=current_phase,
                details={"test": "data"}
            )
            
            assert result['phase'] == current_phase.value
            assert result['status'] == PhaseStatus.COMPLETED.value
            
            if expected_next:
                assert result['next_phase'] == expected_next.value
            else:
                assert result['next_phase'] is None
    
    def test_phase_completion_includes_timestamp(self, mock_aws_clients):
        """
        Test that phase completion includes timestamp in event.
        
        Requirements: 24.6
        """
        from rosetta_zero.utils.workflow import WorkflowPhaseTracker
        
        tracker = WorkflowPhaseTracker()
        
        result = tracker.complete_phase(
            workflow_id="test-workflow",
            phase=WorkflowPhase.DISCOVERY
        )
        
        assert 'end_time' in result
        assert result['end_time'] is not None
        
        # Verify timestamp format (ISO 8601)
        datetime.fromisoformat(result['end_time'])


class TestErrorRecoveryAndRetry:
    """
    Test error recovery and retry mechanisms.
    
    Requirements: 19.2, 19.3, 19.4, 19.5, 25.1-25.5
    """
    
    def test_transient_error_retry_with_exponential_backoff(self, mock_aws_clients):
        """
        Test that transient errors are retried with exponential backoff.
        
        Requirements: 19.2, 25.1, 25.2, 25.3
        """
        # Simulate transient error followed by success
        mock_aws_clients['lambda'].invoke.side_effect = [
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'Invoke'
            ),
            ClientError(
                {'Error': {'Code': 'ServiceException', 'Message': 'Temporary failure'}},
                'Invoke'
            ),
            {
                'StatusCode': 202,
                'ResponseMetadata': {'RequestId': 'success-request-id'}
            }
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = trigger_ingestion_engine(
                workflow_id="test-workflow",
                bucket_name="test-bucket",
                object_key="test.cbl"
            )
        
        # Verify operation succeeded after retries
        assert result['request_id'] == 'success-request-id'
        assert result['status_code'] == 202
        
        # Verify retry attempts (3 calls total: 2 failures + 1 success)
        assert mock_aws_clients['lambda'].invoke.call_count == 3
    
    def test_aws_500_error_triggers_operator_notification(self, mock_aws_clients):
        """
        Test that AWS 500-level errors trigger operator notifications.
        
        Requirements: 19.3, 19.4
        """
        # Simulate AWS 500-level error
        mock_aws_clients['lambda'].invoke.side_effect = ClientError(
            {'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'}},
            'Invoke'
        )
        
        with patch('rosetta_zero.utils.error_recovery.SNSNotificationManager') as mock_sns:
            mock_sns_instance = Mock()
            mock_sns.return_value = mock_sns_instance
            
            with patch('time.sleep'):  # Mock sleep
                with pytest.raises(ClientError):
                    trigger_ingestion_engine(
                        workflow_id="test-workflow",
                        bucket_name="test-bucket",
                        object_key="test.cbl"
                    )
            
            # Verify operator was notified
            mock_sns_instance.publish_aws_500_error_alert.assert_called()
            call_args = mock_sns_instance.publish_aws_500_error_alert.call_args
            assert 'InternalServerError' in str(call_args)
    
    def test_retry_exhaustion_after_max_attempts(self, mock_aws_clients):
        """
        Test that retries are exhausted after max attempts.
        
        Requirements: 25.3, 25.4
        """
        # Simulate persistent transient error
        mock_aws_clients['lambda'].invoke.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'Invoke'
        )
        
        with patch('time.sleep'):  # Mock sleep
            with pytest.raises(ClientError) as exc_info:
                trigger_ingestion_engine(
                    workflow_id="test-workflow",
                    bucket_name="test-bucket",
                    object_key="test.cbl"
                )
        
        # Verify max retries were attempted (3 attempts)
        assert mock_aws_clients['lambda'].invoke.call_count == 3
        assert exc_info.value.response['Error']['Code'] == 'ThrottlingException'
    
    def test_automatic_resume_after_transient_failure_resolution(self, mock_aws_clients):
        """
        Test that workflow automatically resumes after transient failures are resolved.
        
        Requirements: 19.5
        """
        # Simulate transient failure then success
        mock_aws_clients['lambda'].invoke.side_effect = [
            ClientError(
                {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
                'Invoke'
            ),
            {
                'StatusCode': 202,
                'ResponseMetadata': {'RequestId': 'resumed-request-id'}
            }
        ]
        
        with patch('time.sleep'):
            result = trigger_ingestion_engine(
                workflow_id="test-workflow",
                bucket_name="test-bucket",
                object_key="test.cbl"
            )
        
        # Verify workflow resumed successfully
        assert result['request_id'] == 'resumed-request-id'
        assert result['status_code'] == 202
    
    def test_error_logged_before_retry(self, mock_aws_clients):
        """
        Test that errors are logged to CloudWatch before retry attempts.
        
        Requirements: 25.1
        """
        mock_aws_clients['lambda'].invoke.side_effect = [
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'Invoke'
            ),
            {
                'StatusCode': 202,
                'ResponseMetadata': {'RequestId': 'success-request-id'}
            }
        ]
        
        with patch('rosetta_zero.utils.logging.logger') as mock_logger:
            with patch('time.sleep'):
                result = trigger_ingestion_engine(
                    workflow_id="test-workflow",
                    bucket_name="test-bucket",
                    object_key="test.cbl"
                )
            
            # Verify error was logged
            mock_logger.warning.assert_called()
            log_calls = [str(call) for call in mock_logger.warning.call_args_list]
            assert any('ThrottlingException' in str(call) for call in log_calls)


class TestOperatorNotifications:
    """
    Test operator notification mechanisms.
    
    Requirements: 19.3, 19.4
    """
    
    def test_sns_notification_on_aws_500_error(self):
        """
        Test that SNS notifications are sent on AWS 500-level errors.
        
        Requirements: 19.3, 19.4
        """
        from rosetta_zero.utils.monitoring import SNSNotificationManager
        
        with patch('boto3.client') as mock_boto:
            mock_sns = MagicMock()
            mock_sns.publish.return_value = {'MessageId': 'msg-123'}
            mock_boto.return_value = mock_sns
            
            manager = SNSNotificationManager(topic_arn='arn:aws:sns:us-east-1:123456789012:test')
            
            result = manager.publish_aws_500_error_alert(
                service='lambda',
                operation='Invoke',
                error_code='InternalServerError',
                error_message='Internal server error occurred',
                context={'workflow_id': 'test-workflow'}
            )
            
            # Verify SNS was called
            mock_sns.publish.assert_called_once()
            call_args = mock_sns.publish.call_args
            
            assert call_args[1]['TopicArn'] == 'arn:aws:sns:us-east-1:123456789012:test'
            assert '[CRITICAL]' in call_args[1]['Subject']
            assert 'AWS 500-Level Error' in call_args[1]['Subject']
            
            message = json.loads(call_args[1]['Message'])
            assert message['severity'] == 'CRITICAL'
            assert message['context']['error_code'] == 'InternalServerError'
    
    def test_operator_alert_includes_context(self):
        """
        Test that operator alerts include full error context.
        
        Requirements: 19.3, 19.4
        """
        from rosetta_zero.utils.monitoring import SNSNotificationManager
        
        with patch('boto3.client') as mock_boto:
            mock_sns = MagicMock()
            mock_sns.publish.return_value = {'MessageId': 'msg-123'}
            mock_boto.return_value = mock_sns
            
            manager = SNSNotificationManager(topic_arn='arn:aws:sns:us-east-1:123456789012:test')
            
            context = {
                'workflow_id': 'workflow-123',
                'phase': 'Discovery',
                'artifact_id': 'payroll-system.cbl',
                'error_details': 'Bedrock API returned 500'
            }
            
            result = manager.publish_operator_alert(
                subject='Workflow Execution Paused',
                message='AWS service error requires operator intervention',
                severity='HIGH',
                context=context
            )
            
            # Verify context was included
            call_args = mock_sns.publish.call_args
            message = json.loads(call_args[1]['Message'])
            
            assert message['context']['workflow_id'] == 'workflow-123'
            assert message['context']['phase'] == 'Discovery'
            assert message['context']['artifact_id'] == 'payroll-system.cbl'
    
    def test_notification_skipped_when_topic_not_configured(self):
        """
        Test that notifications are skipped gracefully when SNS topic is not configured.
        
        Requirements: 19.3
        """
        from rosetta_zero.utils.monitoring import SNSNotificationManager
        
        manager = SNSNotificationManager(topic_arn=None)
        
        result = manager.publish_operator_alert(
            subject='Test Alert',
            message='Test message',
            severity='LOW'
        )
        
        # Verify notification was skipped
        assert result['skipped'] is True


class TestAutonomousOperation:
    """
    Test autonomous operation without human intervention.
    
    Requirements: 19.1
    """
    
    def test_workflow_executes_without_human_intervention(self, mock_aws_clients, lambda_context):
        """
        Test that workflow executes all phases autonomously without human intervention.
        
        Requirements: 19.1
        """
        # Simulate complete autonomous workflow
        s3_event = {
            "Records": [{
                "s3": {
                    "bucket": {"name": "rosetta-zero-legacy-artifacts"},
                    "object": {"key": "fortran/scientific-calc.f90"}
                }
            }]
        }
        
        # Phase 1: Artifact upload triggers Discovery automatically
        result = orchestrator_handler(s3_event, lambda_context)
        assert result["statusCode"] == 200
        workflow_id = json.loads(result["body"])["workflow_id"]
        
        # Verify no human intervention required - Lambda was invoked automatically
        mock_aws_clients['lambda'].invoke.assert_called()
        
        # Phase 2: Discovery completion triggers Synthesis automatically
        discovery_event = {
            "detail-type": "Workflow Phase Completed",
            "detail": {
                "workflow_id": workflow_id,
                "phase_name": "Discovery",
                "details": {"logic_map_location": "s3://bucket/logic-map.json"}
            }
        }
        
        result = orchestrator_handler(discovery_event, lambda_context)
        assert result["statusCode"] == 200
        assert json.loads(result["body"])["phase"] == "Synthesis"
        
        # Verify autonomous progression - no manual trigger required
        assert mock_aws_clients['lambda'].invoke.call_count >= 2
    
    def test_workflow_handles_multiple_artifacts_concurrently(self, mock_aws_clients, lambda_context):
        """
        Test that multiple workflows can execute concurrently without interference.
        
        Requirements: 19.1
        """
        # Upload multiple artifacts
        artifacts = [
            "cobol/payroll.cbl",
            "fortran/physics.f90",
            "cobol/inventory.cbl"
        ]
        
        workflow_ids = []
        
        for artifact in artifacts:
            s3_event = {
                "Records": [{
                    "s3": {
                        "bucket": {"name": "rosetta-zero-legacy-artifacts"},
                        "object": {"key": artifact}
                    }
                }]
            }
            
            result = orchestrator_handler(s3_event, lambda_context)
            assert result["statusCode"] == 200
            
            workflow_id = json.loads(result["body"])["workflow_id"]
            workflow_ids.append(workflow_id)
        
        # Verify each workflow has unique ID
        assert len(workflow_ids) == len(set(workflow_ids))
        
        # Verify all workflows were triggered
        assert mock_aws_clients['lambda'].invoke.call_count == len(artifacts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
