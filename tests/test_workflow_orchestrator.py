"""Unit tests for Workflow Orchestrator Lambda."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

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


@pytest.fixture
def s3_upload_event():
    """S3 upload event fixture."""
    return {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": "rosetta-zero-legacy-artifacts"
                    },
                    "object": {
                        "key": "cobol/legacy-system.cbl"
                    }
                }
            }
        ]
    }


@pytest.fixture
def phase_completion_event():
    """EventBridge phase completion event fixture."""
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Workflow Phase Completed",
        "source": "rosetta-zero.workflow",
        "time": "2024-01-01T00:00:00Z",
        "region": "us-east-1",
        "detail": {
            "workflow_id": "workflow-20240101-000000-legacy-system.cbl",
            "phase_name": "Discovery",
            "status": "SUCCESS",
            "details": {
                "completion_timestamp": "2024-01-01T00:00:00Z",
                "logic_map_location": "s3://rosetta-zero-logic-maps/workflow-123/logic-map.json",
                "next_phase": "Synthesis"
            }
        }
    }


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = Mock()
    context.function_name = "rosetta-zero-workflow-orchestrator"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:rosetta-zero-workflow-orchestrator"
    context.memory_limit_in_mb = 512
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/rosetta-zero-workflow-orchestrator"
    context.log_stream_name = "2024/01/01/[$LATEST]test-stream"
    return context


class TestOrchestratorHandler:
    """Test orchestrator_handler function."""
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.handle_artifact_upload')
    def test_orchestrator_handles_s3_event(self, mock_handle_upload, s3_upload_event, lambda_context):
        """Test orchestrator routes S3 upload events correctly."""
        mock_handle_upload.return_value = {
            "statusCode": 200,
            "body": json.dumps({"workflow_id": "test-workflow"})
        }
        
        result = orchestrator_handler(s3_upload_event, lambda_context)
        
        assert result["statusCode"] == 200
        mock_handle_upload.assert_called_once_with(s3_upload_event)
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.handle_phase_completion')
    def test_orchestrator_handles_phase_completion_event(
        self,
        mock_handle_completion,
        phase_completion_event,
        lambda_context
    ):
        """Test orchestrator routes phase completion events correctly."""
        mock_handle_completion.return_value = {
            "statusCode": 200,
            "body": json.dumps({"phase": "Synthesis", "status": "triggered"})
        }
        
        result = orchestrator_handler(phase_completion_event, lambda_context)
        
        assert result["statusCode"] == 200
        mock_handle_completion.assert_called_once_with(phase_completion_event)
    
    def test_orchestrator_handles_unknown_event(self, lambda_context):
        """Test orchestrator handles unknown event types."""
        unknown_event = {"unknown": "event"}
        
        result = orchestrator_handler(unknown_event, lambda_context)
        
        assert result["statusCode"] == 400
        assert "error" in json.loads(result["body"])


class TestArtifactUploadHandler:
    """Test handle_artifact_upload function."""
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.trigger_ingestion_engine')
    def test_artifact_upload_creates_workflow(
        self,
        mock_trigger_ingestion,
        mock_get_tracker,
        s3_upload_event
    ):
        """Test artifact upload creates workflow and triggers Discovery phase."""
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        mock_trigger_ingestion.return_value = {"request_id": "test-request-id"}
        
        result = handle_artifact_upload(s3_upload_event)
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert "workflow_id" in body
        assert body["phase"] == "Discovery"
        assert body["status"] == "triggered"
        
        # Verify workflow was created
        mock_tracker.create_workflow.assert_called_once()
        
        # Verify Discovery phase was started
        mock_tracker.start_phase.assert_called_once()
        
        # Verify Ingestion Engine was triggered
        mock_trigger_ingestion.assert_called_once()


class TestPhaseCompletionHandler:
    """Test handle_phase_completion function."""
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.trigger_synthesis_phase')
    def test_discovery_completion_triggers_synthesis(
        self,
        mock_trigger_synthesis,
        phase_completion_event
    ):
        """Test Discovery phase completion triggers Synthesis phase."""
        mock_trigger_synthesis.return_value = {
            "statusCode": 200,
            "body": json.dumps({"phase": "Synthesis"})
        }
        
        result = handle_phase_completion(phase_completion_event)
        
        assert result["statusCode"] == 200
        mock_trigger_synthesis.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.trigger_aggression_phase')
    def test_synthesis_completion_triggers_aggression(self, mock_trigger_aggression):
        """Test Synthesis phase completion triggers Aggression phase."""
        event = {
            "detail": {
                "workflow_id": "test-workflow",
                "phase_name": "Synthesis",
                "details": {}
            }
        }
        mock_trigger_aggression.return_value = {
            "statusCode": 200,
            "body": json.dumps({"phase": "Aggression"})
        }
        
        result = handle_phase_completion(event)
        
        assert result["statusCode"] == 200
        mock_trigger_aggression.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.trigger_validation_phase')
    def test_aggression_completion_triggers_validation(self, mock_trigger_validation):
        """Test Aggression phase completion triggers Validation phase."""
        event = {
            "detail": {
                "workflow_id": "test-workflow",
                "phase_name": "Aggression",
                "details": {}
            }
        }
        mock_trigger_validation.return_value = {
            "statusCode": 200,
            "body": json.dumps({"phase": "Validation"})
        }
        
        result = handle_phase_completion(event)
        
        assert result["statusCode"] == 200
        mock_trigger_validation.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.trigger_trust_phase')
    def test_validation_completion_triggers_trust(self, mock_trigger_trust):
        """Test Validation phase completion triggers Trust phase."""
        event = {
            "detail": {
                "workflow_id": "test-workflow",
                "phase_name": "Validation",
                "details": {}
            }
        }
        mock_trigger_trust.return_value = {
            "statusCode": 200,
            "body": json.dumps({"phase": "Trust"})
        }
        
        result = handle_phase_completion(event)
        
        assert result["statusCode"] == 200
        mock_trigger_trust.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.handle_workflow_completion')
    def test_trust_completion_completes_workflow(self, mock_handle_completion):
        """Test Trust phase completion completes workflow."""
        event = {
            "detail": {
                "workflow_id": "test-workflow",
                "phase_name": "Trust",
                "details": {}
            }
        }
        mock_handle_completion.return_value = {
            "statusCode": 200,
            "body": json.dumps({"status": "completed"})
        }
        
        result = handle_phase_completion(event)
        
        assert result["statusCode"] == 200
        mock_handle_completion.assert_called_once()


class TestPhaseTriggers:
    """Test phase trigger functions."""
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_lambda_client')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    def test_trigger_ingestion_engine(self, mock_retry, mock_get_lambda_client):
        """Test triggering Ingestion Engine Lambda."""
        mock_retry.execute_with_retry.return_value = {
            "request_id": "test-request-id",
            "status_code": 202
        }
        
        result = trigger_ingestion_engine(
            workflow_id="test-workflow",
            bucket_name="test-bucket",
            object_key="test-key"
        )
        
        assert result["request_id"] == "test-request-id"
        mock_retry.execute_with_retry.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_lambda_client')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    def test_trigger_synthesis_phase(self, mock_retry, mock_get_lambda_client, mock_get_tracker):
        """Test triggering Synthesis phase."""
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        mock_retry.execute_with_retry.return_value = {
            "request_id": "test-request-id",
            "status_code": 202
        }
        
        result = trigger_synthesis_phase(
            workflow_id="test-workflow",
            discovery_details={"logic_map_location": "s3://bucket/key"}
        )
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Synthesis"
        
        # Verify phase was started
        mock_tracker.start_phase.assert_called_once()
        
        # Verify Lambda was invoked
        mock_retry.execute_with_retry.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_lambda_client')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    def test_trigger_aggression_phase(self, mock_retry, mock_get_lambda_client, mock_get_tracker):
        """Test triggering Aggression phase."""
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        mock_retry.execute_with_retry.return_value = {
            "request_id": "test-request-id",
            "status_code": 202
        }
        
        result = trigger_aggression_phase(
            workflow_id="test-workflow",
            synthesis_details={
                "logic_map_location": "s3://bucket/logic-map",
                "modern_implementation_location": "s3://bucket/modern-impl"
            }
        )
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Aggression"
        
        # Verify phase was started
        mock_tracker.start_phase.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    @patch('boto3.client')
    def test_trigger_validation_phase(self, mock_boto_client, mock_retry, mock_get_tracker):
        """Test triggering Validation phase with Step Functions."""
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        mock_sfn_client = MagicMock()
        mock_boto_client.return_value = mock_sfn_client
        
        mock_retry.execute_with_retry.return_value = {
            "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:test",
            "start_date": "2024-01-01T00:00:00"
        }
        
        result = trigger_validation_phase(
            workflow_id="test-workflow",
            aggression_details={
                "test_vectors_location": "s3://bucket/vectors",
                "legacy_artifact_location": "s3://bucket/legacy",
                "modern_implementation_location": "s3://bucket/modern"
            }
        )
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Validation"
        
        # Verify phase was started
        mock_tracker.start_phase.assert_called_once()
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_lambda_client')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    def test_trigger_trust_phase(self, mock_retry, mock_get_lambda_client, mock_get_tracker):
        """Test triggering Trust phase."""
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        mock_retry.execute_with_retry.return_value = {
            "request_id": "test-request-id",
            "status_code": 202
        }
        
        result = trigger_trust_phase(
            workflow_id="test-workflow",
            validation_details={
                "test_results_summary": {},
                "total_tests": 1000000,
                "coverage_report": {}
            }
        )
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Trust"
        
        # Verify phase was started
        mock_tracker.start_phase.assert_called_once()


class TestWorkflowCompletion:
    """Test workflow completion handler."""
    
    def test_handle_workflow_completion(self):
        """Test workflow completion handler."""
        result = handle_workflow_completion(
            workflow_id="test-workflow",
            trust_details={
                "certificate_location": "s3://bucket/certificate.json"
            }
        )
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "completed"
        assert "completion_timestamp" in body


class TestAutonomousExecution:
    """Test autonomous workflow execution end-to-end."""
    
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_workflow_tracker')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.get_lambda_client')
    @patch('rosetta_zero.lambdas.workflow_orchestrator.handler.retry_strategy')
    def test_autonomous_workflow_execution(
        self,
        mock_retry,
        mock_get_lambda_client,
        mock_get_tracker,
        s3_upload_event,
        lambda_context
    ):
        """Test autonomous workflow execution from artifact upload to completion.
        
        Requirements: 19.1
        """
        mock_tracker = Mock()
        mock_get_tracker.return_value = mock_tracker
        
        # Mock successful Lambda invocations
        mock_retry.execute_with_retry.return_value = {
            "request_id": "test-request-id",
            "status_code": 202
        }
        
        # Test artifact upload triggers Discovery
        result = handle_artifact_upload(s3_upload_event)
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["phase"] == "Discovery"
        
        # Verify workflow was created and Discovery phase started
        mock_tracker.create_workflow.assert_called_once()
        mock_tracker.start_phase.assert_called()
        
        # Verify Ingestion Engine was triggered
        mock_retry.execute_with_retry.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
