"""Unit tests for workflow phase completion event publishing."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from botocore.exceptions import ClientError

from rosetta_zero.utils.workflow import (
    WorkflowPhaseTracker,
    WorkflowPhase,
    PhaseStatus
)
from rosetta_zero.utils.monitoring import EventBridgeManager


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table."""
    table = Mock()
    table.update_item = Mock(return_value={
        'Attributes': {
            'workflow_id': 'test-workflow-123',
            'phase_name': 'Discovery',
            'status': 'COMPLETED',
            'end_time': '2024-01-15T10:30:00.000000',
            'updated_at': '2024-01-15T10:30:00.000000'
        }
    })
    return table


@pytest.fixture
def mock_event_manager():
    """Mock EventBridge manager."""
    manager = Mock(spec=EventBridgeManager)
    manager.publish_phase_completion_event = Mock(return_value={
        'event_id': 'event-123',
        'source': 'rosetta-zero.workflow',
        'detail_type': 'Workflow Phase Completed',
        'timestamp': '2024-01-15T10:30:00.000000'
    })
    return manager


@pytest.fixture
def workflow_tracker(mock_dynamodb_table, mock_event_manager):
    """Create WorkflowPhaseTracker with mocked dependencies."""
    with patch('rosetta_zero.utils.workflow.boto3') as mock_boto3:
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_dynamodb_table
        mock_boto3.resource.return_value = mock_dynamodb
        
        tracker = WorkflowPhaseTracker(
            table_name='test-workflow-phases',
            event_manager=mock_event_manager
        )
        tracker.table = mock_dynamodb_table
        
        return tracker


class TestWorkflowPhaseCompletion:
    """Test workflow phase completion event publishing."""
    
    def test_complete_phase_updates_dynamodb(self, workflow_tracker, mock_dynamodb_table):
        """Test that complete_phase updates DynamoDB with correct status."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.DISCOVERY
        details = {
            'logic_map_location': 's3://bucket/logic-maps/test.json',
            'artifacts_processed': 1
        }
        
        # Act
        result = workflow_tracker.complete_phase(
            workflow_id=workflow_id,
            phase=phase,
            details=details
        )
        
        # Assert
        mock_dynamodb_table.update_item.assert_called_once()
        call_args = mock_dynamodb_table.update_item.call_args
        
        assert call_args[1]['Key'] == {
            'workflow_id': workflow_id,
            'phase_name': phase.value
        }
        assert ':status' in call_args[1]['ExpressionAttributeValues']
        assert call_args[1]['ExpressionAttributeValues'][':status'] == PhaseStatus.COMPLETED.value
        assert call_args[1]['ExpressionAttributeValues'][':details'] == details
    
    def test_complete_phase_publishes_event(self, workflow_tracker, mock_event_manager):
        """Test that complete_phase publishes event to EventBridge."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.SYNTHESIS
        details = {
            'lambda_code_location': 's3://bucket/modern-implementations/test.py',
            'functions_generated': 5
        }
        
        # Act
        result = workflow_tracker.complete_phase(
            workflow_id=workflow_id,
            phase=phase,
            details=details
        )
        
        # Assert
        mock_event_manager.publish_phase_completion_event.assert_called_once()
        call_args = mock_event_manager.publish_phase_completion_event.call_args
        
        assert call_args[1]['workflow_id'] == workflow_id
        assert call_args[1]['phase_name'] == phase.value
        assert call_args[1]['status'] == 'SUCCESS'
        assert 'completion_timestamp' in call_args[1]['details']
        assert call_args[1]['details']['phase_details'] == details
        assert call_args[1]['details']['next_phase'] == WorkflowPhase.AGGRESSION.value
    
    def test_complete_phase_returns_correct_result(self, workflow_tracker):
        """Test that complete_phase returns correct result structure."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.AGGRESSION
        details = {
            'test_vectors_generated': 1000000,
            'coverage_percent': 96.5
        }
        
        # Act
        result = workflow_tracker.complete_phase(
            workflow_id=workflow_id,
            phase=phase,
            details=details
        )
        
        # Assert
        assert result['workflow_id'] == workflow_id
        assert result['phase'] == phase.value
        assert result['status'] == PhaseStatus.COMPLETED.value
        assert 'end_time' in result
        assert result['event_published'] is True
        assert result['event_id'] == 'event-123'
        assert result['next_phase'] == WorkflowPhase.VALIDATION.value
    
    def test_complete_phase_with_no_details(self, workflow_tracker, mock_dynamodb_table):
        """Test that complete_phase works without optional details."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.VALIDATION
        
        # Act
        result = workflow_tracker.complete_phase(
            workflow_id=workflow_id,
            phase=phase
        )
        
        # Assert
        call_args = mock_dynamodb_table.update_item.call_args
        assert call_args[1]['ExpressionAttributeValues'][':details'] == {}
        assert result['event_published'] is True
    
    def test_complete_last_phase_has_no_next_phase(self, workflow_tracker):
        """Test that completing the Trust phase has no next phase."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.TRUST
        details = {
            'certificate_id': 'cert-123',
            'certificate_location': 's3://bucket/certificates/cert-123.json'
        }
        
        # Act
        result = workflow_tracker.complete_phase(
            workflow_id=workflow_id,
            phase=phase,
            details=details
        )
        
        # Assert
        assert result['next_phase'] is None
    
    def test_complete_phase_handles_dynamodb_error(self, workflow_tracker, mock_dynamodb_table):
        """Test that complete_phase handles DynamoDB errors correctly."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.DISCOVERY
        
        mock_dynamodb_table.update_item.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Table not found'}},
            'UpdateItem'
        )
        
        # Act & Assert
        with pytest.raises(ClientError):
            workflow_tracker.complete_phase(
                workflow_id=workflow_id,
                phase=phase
            )
    
    def test_get_next_phase_returns_correct_sequence(self, workflow_tracker):
        """Test that _get_next_phase returns correct phase sequence."""
        # Test each phase transition
        assert workflow_tracker._get_next_phase(WorkflowPhase.DISCOVERY) == WorkflowPhase.SYNTHESIS.value
        assert workflow_tracker._get_next_phase(WorkflowPhase.SYNTHESIS) == WorkflowPhase.AGGRESSION.value
        assert workflow_tracker._get_next_phase(WorkflowPhase.AGGRESSION) == WorkflowPhase.VALIDATION.value
        assert workflow_tracker._get_next_phase(WorkflowPhase.VALIDATION) == WorkflowPhase.TRUST.value
        assert workflow_tracker._get_next_phase(WorkflowPhase.TRUST) is None
    
    def test_complete_phase_includes_timestamp(self, workflow_tracker, mock_event_manager):
        """Test that complete_phase includes completion timestamp in event."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phase = WorkflowPhase.DISCOVERY
        
        # Act
        with patch('rosetta_zero.utils.workflow.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = '2024-01-15T10:30:00.000000'
            
            result = workflow_tracker.complete_phase(
                workflow_id=workflow_id,
                phase=phase
            )
        
        # Assert
        call_args = mock_event_manager.publish_phase_completion_event.call_args
        assert call_args[1]['details']['completion_timestamp'] == '2024-01-15T10:30:00.000000'
    
    def test_complete_all_phases_in_sequence(self, workflow_tracker):
        """Test completing all phases in correct sequence."""
        # Arrange
        workflow_id = 'test-workflow-123'
        phases = [
            WorkflowPhase.DISCOVERY,
            WorkflowPhase.SYNTHESIS,
            WorkflowPhase.AGGRESSION,
            WorkflowPhase.VALIDATION,
            WorkflowPhase.TRUST
        ]
        
        # Act & Assert
        for i, phase in enumerate(phases):
            result = workflow_tracker.complete_phase(
                workflow_id=workflow_id,
                phase=phase,
                details={'phase_index': i}
            )
            
            assert result['phase'] == phase.value
            assert result['status'] == PhaseStatus.COMPLETED.value
            assert result['event_published'] is True
            
            # Check next phase
            if i < len(phases) - 1:
                assert result['next_phase'] == phases[i + 1].value
            else:
                assert result['next_phase'] is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
