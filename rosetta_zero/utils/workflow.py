"""Workflow orchestration and phase tracking for Rosetta Zero."""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import boto3
from botocore.exceptions import ClientError

from rosetta_zero.utils.logging import logger, log_error
from rosetta_zero.utils.monitoring import EventBridgeManager


class WorkflowPhase(Enum):
    """Workflow phases in Rosetta Zero."""
    DISCOVERY = "Discovery"
    SYNTHESIS = "Synthesis"
    AGGRESSION = "Aggression"
    VALIDATION = "Validation"
    TRUST = "Trust"


class PhaseStatus(Enum):
    """Phase completion status."""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowPhaseTracker:
    """
    Tracks workflow phase status in DynamoDB.
    
    Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.7
    """
    
    def __init__(
        self,
        table_name: Optional[str] = None,
        event_manager: Optional[EventBridgeManager] = None
    ):
        """
        Initialize Workflow Phase Tracker.
        
        Args:
            table_name: DynamoDB table name (default: from environment)
            event_manager: EventBridge manager for publishing events
        """
        self.dynamodb = boto3.resource('dynamodb')
        self.table_name = table_name or os.environ.get(
            'WORKFLOW_PHASES_TABLE',
            'rosetta-zero-workflow-phases'
        )
        self.table = self.dynamodb.Table(self.table_name)
        self.event_manager = event_manager or EventBridgeManager()
    
    def create_workflow(
        self,
        workflow_id: str,
        artifact_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new workflow and initialize all phases.
        
        Args:
            workflow_id: Unique workflow identifier
            artifact_id: Legacy artifact identifier
            metadata: Additional workflow metadata
            
        Returns:
            Workflow creation result
        """
        timestamp = datetime.utcnow().isoformat()
        
        try:
            # Initialize all phases as NOT_STARTED
            for phase in WorkflowPhase:
                self.table.put_item(
                    Item={
                        'workflow_id': workflow_id,
                        'phase_name': phase.value,
                        'status': PhaseStatus.NOT_STARTED.value,
                        'artifact_id': artifact_id,
                        'created_at': timestamp,
                        'updated_at': timestamp,
                        'metadata': metadata or {}
                    }
                )
            
            logger.info(
                "Created workflow with all phases initialized",
                extra={
                    'workflow_id': workflow_id,
                    'artifact_id': artifact_id,
                    'timestamp': timestamp
                }
            )
            
            return {
                'workflow_id': workflow_id,
                'artifact_id': artifact_id,
                'phases_initialized': len(WorkflowPhase),
                'timestamp': timestamp
            }
            
        except ClientError as e:
            log_error(
                component='workflow_phase_tracker',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'workflow_id': workflow_id}
            )
            raise
    
    def start_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase
    ) -> Dict[str, Any]:
        """
        Mark a phase as started.
        
        Requirement: 24.3
        
        Args:
            workflow_id: Workflow identifier
            phase: Phase to start
            
        Returns:
            Phase start result
        """
        timestamp = datetime.utcnow().isoformat()
        
        try:
            response = self.table.update_item(
                Key={
                    'workflow_id': workflow_id,
                    'phase_name': phase.value
                },
                UpdateExpression='SET #status = :status, start_time = :start_time, updated_at = :updated_at',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': PhaseStatus.IN_PROGRESS.value,
                    ':start_time': timestamp,
                    ':updated_at': timestamp
                },
                ReturnValues='ALL_NEW'
            )
            
            logger.info(
                "Phase started",
                extra={
                    'workflow_id': workflow_id,
                    'phase': phase.value,
                    'status': PhaseStatus.IN_PROGRESS.value,
                    'timestamp': timestamp
                }
            )
            
            return {
                'workflow_id': workflow_id,
                'phase': phase.value,
                'status': PhaseStatus.IN_PROGRESS.value,
                'start_time': timestamp
            }
            
        except ClientError as e:
            log_error(
                component='workflow_phase_tracker',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'workflow_id': workflow_id, 'phase': phase.value}
            )
            raise
    
    def complete_phase(
        self,
        workflow_id: str,
        phase: WorkflowPhase,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Mark a phase as completed and publish completion event to EventBridge.
        
        Requirements: 24.6
        
        Args:
            workflow_id: Workflow identifier
            phase: Phase to complete
            details: Phase completion details (e.g., artifact locations, metrics)
            
        Returns:
            Phase completion result including event publication details
        """
        timestamp = datetime.utcnow().isoformat()
        
        try:
            # Update phase status in DynamoDB
            response = self.table.update_item(
                Key={
                    'workflow_id': workflow_id,
                    'phase_name': phase.value
                },
                UpdateExpression='SET #status = :status, end_time = :end_time, updated_at = :updated_at, completion_details = :details',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': PhaseStatus.COMPLETED.value,
                    ':end_time': timestamp,
                    ':updated_at': timestamp,
                    ':details': details or {}
                },
                ReturnValues='ALL_NEW'
            )
            
            logger.info(
                "Phase completed",
                extra={
                    'workflow_id': workflow_id,
                    'phase': phase.value,
                    'status': PhaseStatus.COMPLETED.value,
                    'timestamp': timestamp
                }
            )
            
            # Publish phase completion event to EventBridge
            event_result = self.event_manager.publish_phase_completion_event(
                workflow_id=workflow_id,
                phase_name=phase.value,
                status='SUCCESS',
                details={
                    'completion_timestamp': timestamp,
                    'phase_details': details or {},
                    'next_phase': self._get_next_phase(phase)
                }
            )
            
            logger.info(
                "Published phase completion event to EventBridge",
                extra={
                    'workflow_id': workflow_id,
                    'phase': phase.value,
                    'event_id': event_result.get('event_id'),
                    'timestamp': timestamp
                }
            )
            
            return {
                'workflow_id': workflow_id,
                'phase': phase.value,
                'status': PhaseStatus.COMPLETED.value,
                'end_time': timestamp,
                'event_published': True,
                'event_id': event_result.get('event_id'),
                'next_phase': self._get_next_phase(phase)
            }
            
        except ClientError as e:
            log_error(
                component='workflow_phase_tracker',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'workflow_id': workflow_id, 'phase': phase.value}
            )
            raise
    
    def _get_next_phase(self, current_phase: WorkflowPhase) -> Optional[str]:
        """
        Get the next phase in the workflow sequence.
        
        Args:
            current_phase: Current workflow phase
            
        Returns:
            Next phase name or None if this is the last phase
        """
        phase_order = [
            WorkflowPhase.DISCOVERY,
            WorkflowPhase.SYNTHESIS,
            WorkflowPhase.AGGRESSION,
            WorkflowPhase.VALIDATION,
            WorkflowPhase.TRUST
        ]
        
        try:
            current_index = phase_order.index(current_phase)
            if current_index < len(phase_order) - 1:
                return phase_order[current_index + 1].value
            return None
        except ValueError:
            return None
