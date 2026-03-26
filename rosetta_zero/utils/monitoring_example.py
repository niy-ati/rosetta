"""Example usage of Rosetta Zero monitoring infrastructure.

This module demonstrates how to use the monitoring, logging, and event
infrastructure in Lambda functions.
"""

import os
import time
from typing import Dict, Any
from datetime import datetime

from rosetta_zero.utils.logging import (
    logger,
    log_ingestion_engine_decision,
    log_bedrock_architect_decision,
    log_hostile_auditor_decision,
    log_verification_environment_decision,
    log_test_failure_immutable,
    log_workflow_phase_transition,
    log_certificate_generation_decision,
)

from rosetta_zero.utils.monitoring import (
    CloudWatchLogsManager,
    EventBridgeManager,
    SNSNotificationManager,
    PerformanceMetricsPublisher,
)


def example_ingestion_engine_workflow():
    """Example: Ingestion Engine workflow with monitoring."""
    
    # Initialize managers
    events_manager = EventBridgeManager()
    metrics_publisher = PerformanceMetricsPublisher()
    
    artifact_id = "artifact-123"
    start_time = time.time()
    
    try:
        # Log decision: Starting artifact ingestion
        log_ingestion_engine_decision(
            artifact_id=artifact_id,
            decision_type="artifact_ingestion_start",
            decision="starting_ingestion",
            details={
                "artifact_type": "COBOL",
                "file_size_bytes": 1024000,
            }
        )
        
        # Simulate processing
        time.sleep(0.1)
        
        # Log decision: PII detection
        log_ingestion_engine_decision(
            artifact_id=artifact_id,
            decision_type="pii_detection",
            decision="pii_detected_and_redacted",
            details={
                "pii_types": ["email", "ssn"],
                "redaction_count": 5,
            }
        )
        
        # Log decision: Logic Map extraction
        log_ingestion_engine_decision(
            artifact_id=artifact_id,
            decision_type="logic_map_extraction",
            decision="logic_map_extracted",
            details={
                "entry_points": 5,
                "data_structures": 12,
                "control_flow_branches": 45,
                "side_effects": 3,
            }
        )
        
        # Publish metrics
        duration_ms = int((time.time() - start_time) * 1000)
        metrics_publisher.publish_api_latency(
            service="bedrock",
            operation="InvokeModel",
            latency_ms=duration_ms
        )
        
        # Publish phase completion event
        events_manager.publish_phase_completion_event(
            workflow_id="workflow-123",
            phase_name="Discovery",
            status="SUCCESS",
            details={
                "artifact_id": artifact_id,
                "duration_ms": duration_ms,
            }
        )
        
        logger.info(f"Ingestion Engine workflow completed for {artifact_id}")
        
    except Exception as e:
        logger.error(f"Ingestion Engine workflow failed: {str(e)}")
        raise


def example_verification_workflow():
    """Example: Verification Environment workflow with monitoring."""
    
    # Initialize managers
    events_manager = EventBridgeManager()
    sns_manager = SNSNotificationManager()
    metrics_publisher = PerformanceMetricsPublisher()
    
    test_vector_id = "test-456"
    start_time = time.time()
    
    try:
        # Log decision: Starting test execution
        log_verification_environment_decision(
            test_vector_id=test_vector_id,
            decision_type="test_execution_start",
            decision="executing_parallel_tests",
            details={
                "legacy_container": "legacy-executor:latest",
                "modern_lambda": "rosetta-zero-modern-impl",
            }
        )
        
        # Simulate test execution
        time.sleep(0.2)
        
        # Simulate test failure detection
        legacy_result_hash = "abc123def456..."
        modern_result_hash = "xyz789uvw012..."
        
        if legacy_result_hash != modern_result_hash:
            # CRITICAL: Log failure BEFORE any correction attempts
            discrepancy_report_id = f"discrepancy-{test_vector_id}"
            
            log_test_failure_immutable(
                test_vector_id=test_vector_id,
                legacy_result_hash=legacy_result_hash,
                modern_result_hash=modern_result_hash,
                discrepancy_report_id=discrepancy_report_id,
                differences={
                    "return_value_match": False,
                    "stdout_match": True,
                    "stderr_match": True,
                    "side_effects_match": True,
                }
            )
            
            # Log decision: Discrepancy detected
            log_verification_environment_decision(
                test_vector_id=test_vector_id,
                decision_type="output_comparison",
                decision="discrepancy_detected",
                details={
                    "discrepancy_report_id": discrepancy_report_id,
                    "differences": ["return_value"],
                }
            )
            
            # Publish discrepancy event
            events_manager.publish_discrepancy_event(
                test_vector_id=test_vector_id,
                discrepancy_report_id=discrepancy_report_id,
                s3_location=f"s3://bucket/discrepancy-reports/{discrepancy_report_id}.json"
            )
            
            # Publish operator alert
            sns_manager.publish_operator_alert(
                subject="Behavioral Discrepancy Detected",
                message=f"Test vector {test_vector_id} produced different outputs",
                severity="HIGH",
                context={
                    "test_vector_id": test_vector_id,
                    "discrepancy_report_id": discrepancy_report_id,
                }
            )
            
            logger.error(f"Test failure detected for {test_vector_id}")
        
        # Publish metrics
        duration_ms = int((time.time() - start_time) * 1000)
        metrics_publisher.publish_test_execution_duration(
            test_id=test_vector_id,
            duration_ms=duration_ms,
            implementation_type="legacy"
        )
        
    except Exception as e:
        logger.error(f"Verification workflow failed: {str(e)}")
        raise


def example_certificate_generation_workflow():
    """Example: Certificate Generator workflow with monitoring."""
    
    # Initialize managers
    events_manager = EventBridgeManager()
    sns_manager = SNSNotificationManager()
    
    certificate_id = "cert-789"
    
    try:
        # Log decision: Certificate generation
        log_certificate_generation_decision(
            certificate_id=certificate_id,
            total_tests=1000000,
            passed_tests=1000000,
            coverage_percent=98.5,
            test_results_hash="sha256:abc123...",
            decision="certificate_generated"
        )
        
        # Publish certificate generation event
        events_manager.publish_certificate_event(
            certificate_id=certificate_id,
            s3_location=f"s3://bucket/certificates/{certificate_id}.json",
            total_tests=1000000,
            coverage_percent=98.5
        )
        
        # Publish operator notification
        sns_manager.publish_operator_alert(
            subject="Equivalence Certificate Generated",
            message=f"Certificate {certificate_id} has been generated and signed",
            severity="MEDIUM",
            context={
                "certificate_id": certificate_id,
                "total_tests": 1000000,
                "coverage_percent": 98.5,
            }
        )
        
        logger.info(f"Certificate generation completed for {certificate_id}")
        
    except Exception as e:
        logger.error(f"Certificate generation failed: {str(e)}")
        raise


def example_aws_500_error_handling():
    """Example: AWS 500-level error handling with monitoring."""
    
    # Initialize managers
    events_manager = EventBridgeManager()
    sns_manager = SNSNotificationManager()
    
    try:
        # Simulate AWS service call that returns 500 error
        service = "bedrock"
        operation = "InvokeModel"
        error_code = "InternalServerError"
        error_message = "Service temporarily unavailable"
        
        # Publish error event
        events_manager.publish_error_event(
            service=service,
            error_code=error_code,
            error_message=error_message,
            context={
                "operation": operation,
                "retry_count": 3,
                "max_retries": 3,
            }
        )
        
        # Publish critical operator alert
        sns_manager.publish_aws_500_error_alert(
            service=service,
            operation=operation,
            error_code=error_code,
            error_message=error_message,
            context={
                "retry_count": 3,
                "max_retries": 3,
                "action_required": "System execution paused - operator intervention required",
            }
        )
        
        logger.critical(
            f"AWS 500-level error in {service}.{operation} - operator intervention required"
        )
        
    except Exception as e:
        logger.error(f"Error handling failed: {str(e)}")
        raise


def example_workflow_phase_transition():
    """Example: Workflow phase transition with monitoring."""
    
    workflow_id = "workflow-123"
    
    # Log phase transitions
    log_workflow_phase_transition(
        workflow_id=workflow_id,
        from_phase="Discovery",
        to_phase="Synthesis",
        status="SUCCESS",
        details={
            "artifacts_processed": 1,
            "logic_maps_generated": 1,
        }
    )
    
    log_workflow_phase_transition(
        workflow_id=workflow_id,
        from_phase="Synthesis",
        to_phase="Aggression",
        status="SUCCESS",
        details={
            "modern_implementations_generated": 1,
            "cdk_code_generated": True,
        }
    )
    
    logger.info(f"Workflow {workflow_id} progressing through phases")


if __name__ == "__main__":
    """Run examples (for local testing only)."""
    
    print("Running Rosetta Zero monitoring examples...")
    
    print("\n1. Ingestion Engine Workflow")
    example_ingestion_engine_workflow()
    
    print("\n2. Verification Workflow")
    example_verification_workflow()
    
    print("\n3. Certificate Generation Workflow")
    example_certificate_generation_workflow()
    
    print("\n4. AWS 500-Level Error Handling")
    example_aws_500_error_handling()
    
    print("\n5. Workflow Phase Transition")
    example_workflow_phase_transition()
    
    print("\nAll examples completed!")
