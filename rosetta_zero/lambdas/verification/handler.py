"""
Verification Environment Lambda Handler.

Main handler for verification Lambda functions.
"""

import json
import os
from typing import Dict, Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from rosetta_zero.models import TestVector, ExecutionResult, ComparisonResult
from rosetta_zero.utils import logger, tracer

from .legacy_executor import execute_legacy_binary
from .modern_executor import execute_modern_lambda
from .comparator import compare_outputs
from .discrepancy_reporter import handle_behavioral_discrepancy
from .test_result_storage import store_test_result


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def comparator_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Comparator Lambda handler.
    
    Compares legacy and modern execution results and stores test result.
    
    Args:
        event: Event containing legacy_result and modern_result
        context: Lambda context
        
    Returns:
        Comparison result with match status
    """
    logger.info("Comparator Lambda invoked")
    
    # Parse inputs
    legacy_result_data = event['legacy_result']
    modern_result_data = event['modern_result']
    test_vector_data = event['test_vector']
    
    # Deserialize
    test_vector = TestVector.from_dict(test_vector_data)
    legacy_result = ExecutionResult.from_dict(legacy_result_data)
    modern_result = ExecutionResult.from_dict(modern_result_data)
    
    # Compare outputs
    comparison = compare_outputs(legacy_result, modern_result)
    
    # Store test result
    discrepancy_report_id = None
    
    if not comparison.match:
        # Generate discrepancy report
        from .discrepancy_reporter import generate_discrepancy_report
        report = generate_discrepancy_report(
            test_vector,
            legacy_result,
            modern_result,
            comparison
        )
        discrepancy_report_id = report.report_id
    
    # Store in DynamoDB
    store_test_result(
        test_vector,
        legacy_result,
        modern_result,
        comparison,
        discrepancy_report_id
    )
    
    # Return comparison result
    return {
        'test_vector_id': test_vector.vector_id,
        'match': comparison.match,
        'return_value_match': comparison.return_value_match,
        'stdout_match': comparison.stdout_match,
        'stderr_match': comparison.stderr_match,
        'side_effects_match': comparison.side_effects_match,
        'result_hash': comparison.result_hash,
        'discrepancy_report_id': discrepancy_report_id
    }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def orchestrator_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Orchestrator Lambda handler.
    
    Orchestrates parallel test execution for a batch of test vectors.
    
    Args:
        event: Event containing test_vectors array
        context: Lambda context
        
    Returns:
        Execution summary
    """
    logger.info("Orchestrator Lambda invoked")
    
    test_vectors_data = event.get('test_vectors', [])
    
    logger.info(f"Processing {len(test_vectors_data)} test vectors")
    
    # This handler would typically invoke Step Functions for each test vector
    # For now, return a summary
    
    return {
        'test_vector_count': len(test_vectors_data),
        'status': 'INITIATED'
    }
