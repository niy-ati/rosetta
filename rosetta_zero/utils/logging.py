"""AWS Lambda PowerTools logging infrastructure."""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from aws_lambda_powertools import Logger, Tracer, Metrics
    from aws_lambda_powertools.metrics import MetricUnit
    POWERTOOLS_AVAILABLE = True
except ImportError:
    # Fallback for local development without PowerTools
    POWERTOOLS_AVAILABLE = False
    import logging
    Logger = logging.getLogger
    Tracer = None
    Metrics = None
    MetricUnit = None


# Initialize PowerTools components
if POWERTOOLS_AVAILABLE:
    logger = Logger(service="rosetta-zero")
    tracer = Tracer(service="rosetta-zero")
    metrics = Metrics(namespace="RosettaZero", service="rosetta-zero")
else:
    logger = logging.getLogger("rosetta-zero")
    tracer = None
    metrics = None


def configure_logging(
    service_name: str = "rosetta-zero",
    log_level: str = "INFO",
    retention_days: int = 2555
):
    """
    Configure logging for Rosetta Zero components.
    
    Args:
        service_name: Name of the service/component
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        retention_days: CloudWatch Logs retention period (default: 2555 = 7 years)
    """
    if POWERTOOLS_AVAILABLE:
        logger.setLevel(log_level)
        logger.info(
            "Logging configured",
            extra={
                'service': service_name,
                'log_level': log_level,
                'retention_days': retention_days,
            }
        )
    else:
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def log_ingestion_decision(
    artifact_id: str,
    decision: str,
    details: Dict[str, Any]
):
    """Log Ingestion Engine decision."""
    logger.info(
        "Ingestion decision",
        extra={
            'component': 'ingestion_engine',
            'artifact_id': artifact_id,
            'decision': decision,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_architect_decision(
    logic_map_id: str,
    decision: str,
    details: Dict[str, Any]
):
    """Log Bedrock Architect decision."""
    logger.info(
        "Architect decision",
        extra={
            'component': 'bedrock_architect',
            'logic_map_id': logic_map_id,
            'decision': decision,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_auditor_decision(
    logic_map_id: str,
    decision: str,
    details: Dict[str, Any]
):
    """Log Hostile Auditor decision."""
    logger.info(
        "Auditor decision",
        extra={
            'component': 'hostile_auditor',
            'logic_map_id': logic_map_id,
            'decision': decision,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_verification_decision(
    test_vector_id: str,
    decision: str,
    details: Dict[str, Any]
):
    """Log Verification Environment decision."""
    logger.info(
        "Verification decision",
        extra={
            'component': 'verification_environment',
            'test_vector_id': test_vector_id,
            'decision': decision,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_retry_attempt(
    operation: str,
    attempt: int,
    max_retries: int,
    error: Optional[str] = None
):
    """Log retry attempt."""
    logger.warning(
        "Retry attempt",
        extra={
            'operation': operation,
            'attempt': attempt,
            'max_retries': max_retries,
            'error': error,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_error(
    component: str,
    error_type: str,
    error_message: str,
    context: Dict[str, Any]
):
    """Log error with context."""
    logger.error(
        "Error occurred",
        extra={
            'component': component,
            'error_type': error_type,
            'error_message': error_message,
            'context': context,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_pii_detection(
    artifact_id: str,
    pii_types: list,
    redaction_count: int
):
    """Log PII detection event."""
    logger.warning(
        "PII detected and redacted",
        extra={
            'component': 'ingestion_engine',
            'artifact_id': artifact_id,
            'pii_types': pii_types,
            'redaction_count': redaction_count,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_test_failure(
    test_vector_id: str,
    discrepancy_report_id: str,
    details: Dict[str, Any]
):
    """Log test failure before any correction attempts."""
    logger.error(
        "Test failure detected",
        extra={
            'component': 'verification_environment',
            'test_vector_id': test_vector_id,
            'discrepancy_report_id': discrepancy_report_id,
            'details': details,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_certificate_generated(
    certificate_id: str,
    total_tests: int,
    coverage_percent: float
):
    """Log certificate generation."""
    logger.info(
        "Equivalence certificate generated",
        extra={
            'component': 'certificate_generator',
            'certificate_id': certificate_id,
            'total_tests': total_tests,
            'coverage_percent': coverage_percent,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def log_aws_500_error(
    service: str,
    operation: str,
    error_code: str,
    error_message: str,
    context: Dict[str, Any]
):
    """Log AWS 500-level error for operator notification."""
    logger.critical(
        "AWS 500-level error - operator intervention required",
        extra={
            'service': service,
            'operation': operation,
            'error_code': error_code,
            'error_message': error_message,
            'context': context,
            'timestamp': datetime.utcnow().isoformat(),
        }
    )


def publish_metric(
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: Optional[Dict[str, str]] = None
):
    """
    Publish metric to CloudWatch.
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Metric unit (Count, Seconds, Milliseconds, etc.)
        dimensions: Optional dimensions for the metric
    """
    if not POWERTOOLS_AVAILABLE or not metrics:
        logger.debug(f"Metric: {metric_name}={value} {unit}")
        return
    
    if dimensions:
        for key, val in dimensions.items():
            metrics.add_dimension(name=key, value=val)
    
    # Map unit string to MetricUnit enum
    unit_map = {
        "Count": MetricUnit.Count,
        "Seconds": MetricUnit.Seconds,
        "Milliseconds": MetricUnit.Milliseconds,
        "Bytes": MetricUnit.Bytes,
        "Percent": MetricUnit.Percent,
    }
    
    metric_unit = unit_map.get(unit, MetricUnit.Count)
    metrics.add_metric(name=metric_name, unit=metric_unit, value=value)


def log_execution_metrics(
    component: str,
    operation: str,
    duration_ms: int,
    success: bool,
    details: Optional[Dict[str, Any]] = None
):
    """Log execution metrics for monitoring."""
    logger.info(
        "Execution metrics",
        extra={
            'component': component,
            'operation': operation,
            'duration_ms': duration_ms,
            'success': success,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
        }
    )
    
    # Publish metrics
    publish_metric(
        f"{component}.{operation}.duration",
        duration_ms,
        "Milliseconds",
        {"component": component, "operation": operation}
    )
    
    publish_metric(
        f"{component}.{operation}.{'success' if success else 'failure'}",
        1,
        "Count",
        {"component": component, "operation": operation}
    )


def create_structured_log_entry(
    level: str,
    message: str,
    component: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Create structured log entry.
    
    Args:
        level: Log level (INFO, WARNING, ERROR, etc.)
        message: Log message
        component: Component name
        **kwargs: Additional fields
        
    Returns:
        Structured log entry as dictionary
    """
    entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        'component': component,
        'service': 'rosetta-zero',
    }
    entry.update(kwargs)
    return entry


def log_structured(entry: Dict[str, Any]):
    """Log structured entry."""
    level = entry.get('level', 'INFO')
    message = entry.get('message', '')
    
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message, extra=entry)



# Immutable Audit Logging Functions (Requirements 18.1, 18.2, 18.3, 18.4, 18.7)

def log_immutable_decision(
    component: str,
    decision_type: str,
    decision: str,
    context: Dict[str, Any],
    artifact_id: Optional[str] = None
):
    """
    Log immutable decision to CloudWatch for audit trail.
    
    Requirements: 18.1, 18.2, 18.3, 18.4
    
    This function logs all component decisions to CloudWatch with structured
    JSON format for immutable audit trails. Logs are retained for 7 years
    and encrypted with KMS.
    
    Args:
        component: Component name (ingestion_engine, bedrock_architect, 
                   hostile_auditor, verification_environment)
        decision_type: Type of decision (e.g., "logic_map_extraction", 
                       "code_synthesis", "test_generation", "output_comparison")
        decision: The decision made
        context: Additional context for the decision
        artifact_id: Optional artifact/workflow identifier
    """
    log_entry = {
        'audit_log': True,
        'immutable': True,
        'component': component,
        'decision_type': decision_type,
        'decision': decision,
        'context': context,
        'artifact_id': artifact_id,
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"[AUDIT] {component} decision: {decision_type}",
        extra=log_entry
    )


def log_ingestion_engine_decision(
    artifact_id: str,
    decision_type: str,
    decision: str,
    details: Dict[str, Any]
):
    """
    Log Ingestion Engine decision for audit trail.
    
    Requirement: 18.1
    
    Args:
        artifact_id: Legacy artifact identifier
        decision_type: Type of decision (e.g., "pii_detection", "logic_map_extraction")
        decision: The decision made
        details: Decision details
    """
    log_immutable_decision(
        component='ingestion_engine',
        decision_type=decision_type,
        decision=decision,
        context=details,
        artifact_id=artifact_id
    )


def log_bedrock_architect_decision(
    logic_map_id: str,
    decision_type: str,
    decision: str,
    details: Dict[str, Any]
):
    """
    Log Bedrock Architect decision for audit trail.
    
    Requirement: 18.2
    
    Args:
        logic_map_id: Logic Map identifier
        decision_type: Type of decision (e.g., "code_synthesis", "precision_preservation")
        decision: The decision made
        details: Decision details
    """
    log_immutable_decision(
        component='bedrock_architect',
        decision_type=decision_type,
        decision=decision,
        context=details,
        artifact_id=logic_map_id
    )


def log_hostile_auditor_decision(
    logic_map_id: str,
    decision_type: str,
    decision: str,
    details: Dict[str, Any]
):
    """
    Log Hostile Auditor decision for audit trail.
    
    Requirement: 18.3
    
    Args:
        logic_map_id: Logic Map identifier
        decision_type: Type of decision (e.g., "test_vector_generation", "coverage_analysis")
        decision: The decision made
        details: Decision details
    """
    log_immutable_decision(
        component='hostile_auditor',
        decision_type=decision_type,
        decision=decision,
        context=details,
        artifact_id=logic_map_id
    )


def log_verification_environment_decision(
    test_vector_id: str,
    decision_type: str,
    decision: str,
    details: Dict[str, Any]
):
    """
    Log Verification Environment decision for audit trail.
    
    Requirement: 18.4
    
    Args:
        test_vector_id: Test vector identifier
        decision_type: Type of decision (e.g., "output_comparison", "discrepancy_detection")
        decision: The decision made
        details: Decision details
    """
    log_immutable_decision(
        component='verification_environment',
        decision_type=decision_type,
        decision=decision,
        context=details,
        artifact_id=test_vector_id
    )


def log_test_failure_immutable(
    test_vector_id: str,
    legacy_result_hash: str,
    modern_result_hash: str,
    discrepancy_report_id: str,
    differences: Dict[str, Any]
):
    """
    Log test failure before any correction attempts.
    
    Requirement: 18.7
    
    This function MUST be called immediately when a test failure is detected,
    before any attempts to correct or retry the test. This ensures an immutable
    audit trail of all failures.
    
    Args:
        test_vector_id: Test vector identifier
        legacy_result_hash: SHA-256 hash of legacy execution result
        modern_result_hash: SHA-256 hash of modern execution result
        discrepancy_report_id: Discrepancy report identifier
        differences: Detailed differences between outputs
    """
    log_entry = {
        'audit_log': True,
        'immutable': True,
        'event_type': 'test_failure',
        'component': 'verification_environment',
        'test_vector_id': test_vector_id,
        'legacy_result_hash': legacy_result_hash,
        'modern_result_hash': modern_result_hash,
        'discrepancy_report_id': discrepancy_report_id,
        'differences': differences,
        'logged_before_correction': True,
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    logger.error(
        f"[AUDIT] Test failure detected - logged before correction attempts",
        extra=log_entry
    )


def log_workflow_phase_transition(
    workflow_id: str,
    from_phase: str,
    to_phase: str,
    status: str,
    details: Dict[str, Any]
):
    """
    Log workflow phase transition for audit trail.
    
    Args:
        workflow_id: Workflow identifier
        from_phase: Previous phase name
        to_phase: Next phase name
        status: Transition status (SUCCESS, FAILED)
        details: Transition details
    """
    log_entry = {
        'audit_log': True,
        'immutable': True,
        'event_type': 'workflow_phase_transition',
        'workflow_id': workflow_id,
        'from_phase': from_phase,
        'to_phase': to_phase,
        'status': status,
        'details': details,
        'timestamp': datetime.utcnow().isoformat(),
    }
    
    logger.info(
        f"[AUDIT] Workflow phase transition: {from_phase} -> {to_phase}",
        extra=log_entry
    )


def log_certificate_generation_decision(
    certificate_id: str,
    total_tests: int,
    passed_tests: int,
    coverage_percent: float,
    test_results_hash: str,
    decision: str
):
    """
    Log certificate generation decision for audit trail.
    
    Args:
        certificate_id: Certificate identifier
        total_tests: Total number of tests executed
        passed_tests: Number of tests that passed
        coverage_percent: Branch coverage percentage
        test_results_hash: SHA-256 hash of all test results
        decision: Decision made (e.g., "certificate_generated", "certificate_denied")
    """
    log_immutable_decision(
        component='certificate_generator',
        decision_type='certificate_generation',
        decision=decision,
        context={
            'certificate_id': certificate_id,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'coverage_percent': coverage_percent,
            'test_results_hash': test_results_hash,
        },
        artifact_id=certificate_id
    )
