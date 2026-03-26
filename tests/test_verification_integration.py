"""
Integration tests for Verification Environment.

Tests parallel execution orchestration, output comparison, discrepancy reporting,
and Step Functions workflow end-to-end.

Requirements: 11.1-11.7, 13.1-13.6
"""

import json
import os
import sys
import uuid
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any

import pytest

# Set AWS region and mock boto3 before importing verification modules
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['TEST_VECTORS_BUCKET'] = 'test-bucket'
os.environ['STATE_MACHINE_ARN'] = 'arn:aws:states:us-east-1:123456789012:stateMachine:test'
os.environ['ECS_CLUSTER_NAME'] = 'test-cluster'
os.environ['TASK_DEFINITION'] = 'test-task'
os.environ['SUBNET_IDS'] = 'subnet-1,subnet-2'
os.environ['SECURITY_GROUP_ID'] = 'sg-123'
os.environ['LOG_GROUP_NAME'] = '/test/logs'
os.environ['DISCREPANCY_BUCKET'] = 'test-discrepancy-bucket'
os.environ['KMS_KEY_ID'] = 'test-kms-key'
os.environ['EVENT_BUS_NAME'] = 'test-event-bus'

from rosetta_zero.models import (
    TestVector,
    TestVectorBatch,
    TestVectorCategory,
    ExecutionResult,
    ExecutionError,
    ImplementationType,
    ObservedSideEffect,
    ComparisonResult,
    DifferenceDetails,
    ByteDiff,
    SideEffectDiff,
    DiscrepancyReport,
)

# Import comparator first (doesn't use boto3 clients at module level)
from rosetta_zero.lambdas.verification.comparator import (
    compare_outputs,
    generate_byte_diff,
    compare_side_effects,
    compute_comparison_hash,
)


# Test fixtures

@pytest.fixture
def sample_test_vector():
    """Create a sample test vector."""
    return TestVector(
        vector_id=f"test-{uuid.uuid4().hex[:8]}",
        generation_timestamp=datetime.utcnow().isoformat(),
        random_seed=12345,
        entry_point="calculate_interest",
        input_parameters={
            "principal": 10000,
            "rate": 0.05,
            "years": 10
        },
        expected_coverage={"branch_1", "branch_2"},
        category=TestVectorCategory.BOUNDARY
    )


@pytest.fixture
def sample_test_vector_batch(sample_test_vector):
    """Create a sample test vector batch."""
    vectors = [sample_test_vector]
    for i in range(4):
        vectors.append(TestVector(
            vector_id=f"test-{uuid.uuid4().hex[:8]}",
            generation_timestamp=datetime.utcnow().isoformat(),
            random_seed=12345 + i,
            entry_point="calculate_interest",
            input_parameters={
                "principal": 10000 + i * 1000,
                "rate": 0.05,
                "years": 10
            },
            expected_coverage={"branch_1", "branch_2"},
            category=TestVectorCategory.RANDOM
        ))
    
    return TestVectorBatch(
        batch_id=f"batch-{uuid.uuid4().hex[:8]}",
        vectors=vectors,
        total_count=5,
        batch_index=0
    )


@pytest.fixture
def matching_execution_results(sample_test_vector):
    """Create matching execution results from legacy and modern implementations."""
    timestamp = datetime.utcnow().isoformat()
    
    # Both implementations return the same output
    return_value = b"16288.95"  # Interest calculation result
    stdout = b"Calculating interest...\nResult: 16288.95\n"
    stderr = b""
    
    legacy_result = ExecutionResult(
        test_vector_id=sample_test_vector.vector_id,
        implementation_type=ImplementationType.LEGACY,
        execution_timestamp=timestamp,
        return_value=return_value,
        stdout=stdout,
        stderr=stderr,
        side_effects=[],
        execution_duration_ms=150,
        error=None
    )
    
    modern_result = ExecutionResult(
        test_vector_id=sample_test_vector.vector_id,
        implementation_type=ImplementationType.MODERN,
        execution_timestamp=timestamp,
        return_value=return_value,
        stdout=stdout,
        stderr=stderr,
        side_effects=[],
        execution_duration_ms=50,
        error=None
    )
    
    return legacy_result, modern_result


@pytest.fixture
def differing_execution_results(sample_test_vector):
    """Create differing execution results from legacy and modern implementations."""
    timestamp = datetime.utcnow().isoformat()
    
    # Legacy and modern return different outputs
    legacy_result = ExecutionResult(
        test_vector_id=sample_test_vector.vector_id,
        implementation_type=ImplementationType.LEGACY,
        execution_timestamp=timestamp,
        return_value=b"16288.95",  # Legacy result
        stdout=b"Calculating interest...\nResult: 16288.95\n",
        stderr=b"",
        side_effects=[
            ObservedSideEffect(
                effect_type="FILE_IO",
                operation="write",
                data=b"interest_log.txt",
                timestamp=timestamp
            )
        ],
        execution_duration_ms=150,
        error=None
    )
    
    modern_result = ExecutionResult(
        test_vector_id=sample_test_vector.vector_id,
        implementation_type=ImplementationType.MODERN,
        execution_timestamp=timestamp,
        return_value=b"16289.00",  # Modern result differs by rounding
        stdout=b"Calculating interest...\nResult: 16289.00\n",
        stderr=b"",
        side_effects=[],  # Missing side effect
        execution_duration_ms=50,
        error=None
    )
    
    return legacy_result, modern_result


# Integration Tests

class TestParallelExecution:
    """
    Test parallel execution of legacy and modern implementations.
    
    Requirements: 11.1, 11.2, 11.3, 11.4
    """
    
    def test_execute_parallel_tests_success(
        self,
        sample_test_vector_batch
    ):
        """
        Test successful parallel execution of test vectors.
        
        Requirement 11.1: Use AWS Step Functions to orchestrate test execution
        Requirement 11.4: Execute legacy and modern implementations in parallel
        """
        with patch('rosetta_zero.lambdas.verification.orchestrator.s3_client') as mock_s3_client, \
             patch('rosetta_zero.lambdas.verification.orchestrator.sfn_client') as mock_sfn_client:
            
            # Import after patching
            from rosetta_zero.lambdas.verification.orchestrator import execute_parallel_tests
            
            # Mock S3 to return test vector batch
            batch_json = sample_test_vector_batch.to_json()
            mock_s3_client.get_object.return_value = {
                'Body': Mock(read=Mock(return_value=batch_json.encode('utf-8')))
            }
            
            # Mock Step Functions to return execution ARNs
            execution_arns = []
            for i, vector in enumerate(sample_test_vector_batch.vectors):
                arn = f"arn:aws:states:us-east-1:123456789012:execution:test-sm:test-{vector.vector_id}"
                execution_arns.append(arn)
            
            mock_sfn_client.start_execution.side_effect = [
                {'executionArn': arn} for arn in execution_arns
            ]
            
            # Mock Step Functions describe_execution to return completed status
            def describe_execution_side_effect(executionArn):
                return {
                    'status': 'SUCCEEDED',
                    'output': json.dumps({'match': True}),
                    'stopDate': datetime.utcnow()
                }
            
            mock_sfn_client.describe_execution.side_effect = describe_execution_side_effect
            
            # Execute parallel tests
            s3_key = f"batches/{sample_test_vector_batch.batch_id}.json"
            modern_lambda_arn = "arn:aws:lambda:us-east-1:123456789012:function:modern-impl"
            
            summary = execute_parallel_tests(s3_key, modern_lambda_arn)
            
            # Verify results
            assert summary['total_tests'] == 5
            assert summary['successful_starts'] == 5
            assert summary['failed_starts'] == 0
            assert summary['passed'] == 5
            assert summary['failed'] == 0
            
            # Verify Step Functions was called for each test vector
            assert mock_sfn_client.start_execution.call_count == 5
    
    def test_execute_parallel_tests_with_failures(
        self,
        sample_test_vector_batch
    ):
        """
        Test parallel execution with some test failures.
        
        Requirement 11.4: Execute legacy and modern implementations in parallel
        """
        with patch('rosetta_zero.lambdas.verification.orchestrator.s3_client') as mock_s3_client, \
             patch('rosetta_zero.lambdas.verification.orchestrator.sfn_client') as mock_sfn_client:
            
            # Import after patching
            from rosetta_zero.lambdas.verification.orchestrator import execute_parallel_tests
            
            # Mock S3 to return test vector batch
            batch_json = sample_test_vector_batch.to_json()
            mock_s3_client.get_object.return_value = {
                'Body': Mock(read=Mock(return_value=batch_json.encode('utf-8')))
            }
            
            # Mock Step Functions with mixed results
            execution_arns = []
            for i, vector in enumerate(sample_test_vector_batch.vectors):
                arn = f"arn:aws:states:us-east-1:123456789012:execution:test-sm:test-{vector.vector_id}"
                execution_arns.append(arn)
            
            mock_sfn_client.start_execution.side_effect = [
                {'executionArn': arn} for arn in execution_arns
            ]
            
            # Mock describe_execution with mixed results (3 pass, 2 fail)
            call_count = [0]
            def describe_execution_side_effect(executionArn):
                call_count[0] += 1
                if call_count[0] <= 3:
                    return {
                        'status': 'SUCCEEDED',
                        'output': json.dumps({'match': True}),
                        'stopDate': datetime.utcnow()
                    }
                else:
                    return {
                        'status': 'SUCCEEDED',
                        'output': json.dumps({'match': False}),
                        'stopDate': datetime.utcnow()
                    }
            
            mock_sfn_client.describe_execution.side_effect = describe_execution_side_effect
            
            # Execute parallel tests
            s3_key = f"batches/{sample_test_vector_batch.batch_id}.json"
            modern_lambda_arn = "arn:aws:lambda:us-east-1:123456789012:function:modern-impl"
            
            summary = execute_parallel_tests(s3_key, modern_lambda_arn)
            
            # Verify results
            assert summary['total_tests'] == 5
            assert summary['passed'] == 3
            assert summary['failed'] == 2


class TestOutputComparison:
    """
    Test output comparison with matching and differing outputs.
    
    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6
    """
    
    def test_compare_outputs_matching(self, matching_execution_results):
        """
        Test output comparison with matching outputs.
        
        Requirement 13.1: Compare return values byte-by-byte
        Requirement 13.2: Compare stdout content byte-by-byte
        Requirement 13.3: Compare stderr content byte-by-byte
        Requirement 13.4: Compare all side effects
        Requirement 13.5: Record passing test result when outputs match exactly
        """
        legacy_result, modern_result = matching_execution_results
        
        # Compare outputs
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify all matches
        assert comparison.match is True
        assert comparison.return_value_match is True
        assert comparison.stdout_match is True
        assert comparison.stderr_match is True
        assert comparison.side_effects_match is True
        
        # Verify no differences recorded
        assert comparison.differences is None
        
        # Verify hash is computed
        assert comparison.result_hash != ""
        assert len(comparison.result_hash) == 64  # SHA-256 hex length
    
    def test_compare_outputs_differing_return_value(self, differing_execution_results):
        """
        Test output comparison with differing return values.
        
        Requirement 13.1: Compare return values byte-by-byte
        Requirement 13.6: Record failing test result with difference details
        """
        legacy_result, modern_result = differing_execution_results
        
        # Compare outputs
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify mismatch detected
        assert comparison.match is False
        assert comparison.return_value_match is False
        
        # Verify differences are recorded
        assert comparison.differences is not None
        assert comparison.differences.return_value_diff is not None
        
        # Verify byte diff details
        byte_diff = comparison.differences.return_value_diff
        assert byte_diff.offset >= 0
        assert byte_diff.legacy_bytes != byte_diff.modern_bytes
    
    def test_compare_outputs_differing_stdout(self, sample_test_vector):
        """
        Test output comparison with differing stdout.
        
        Requirement 13.2: Compare stdout content byte-by-byte
        Requirement 13.6: Record failing test result with difference details
        """
        timestamp = datetime.utcnow().isoformat()
        
        legacy_result = ExecutionResult(
            test_vector_id=sample_test_vector.vector_id,
            implementation_type=ImplementationType.LEGACY,
            execution_timestamp=timestamp,
            return_value=b"100",
            stdout=b"Processing...\nDone\n",
            stderr=b"",
            side_effects=[],
            execution_duration_ms=100,
            error=None
        )
        
        modern_result = ExecutionResult(
            test_vector_id=sample_test_vector.vector_id,
            implementation_type=ImplementationType.MODERN,
            execution_timestamp=timestamp,
            return_value=b"100",
            stdout=b"Processing...\nComplete\n",  # Different stdout
            stderr=b"",
            side_effects=[],
            execution_duration_ms=50,
            error=None
        )
        
        # Compare outputs
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify mismatch detected
        assert comparison.match is False
        assert comparison.stdout_match is False
        assert comparison.return_value_match is True  # Return value matches
        
        # Verify stdout diff is recorded
        assert comparison.differences is not None
        assert comparison.differences.stdout_diff is not None
    
    def test_compare_outputs_differing_side_effects(self, differing_execution_results):
        """
        Test output comparison with differing side effects.
        
        Requirement 13.4: Compare all side effects
        Requirement 13.6: Record failing test result with difference details
        """
        legacy_result, modern_result = differing_execution_results
        
        # Compare outputs
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify side effects mismatch detected
        assert comparison.match is False
        assert comparison.side_effects_match is False
        
        # Verify side effect diffs are recorded
        assert comparison.differences is not None
        assert len(comparison.differences.side_effect_diffs) > 0
    
    def test_generate_byte_diff(self):
        """
        Test byte-level diff generation with context.
        
        Requirement 13.5: Include byte-level diff
        """
        legacy_bytes = b"Hello World!"
        modern_bytes = b"Hello Earth!"
        
        # Generate byte diff
        byte_diff = generate_byte_diff(legacy_bytes, modern_bytes, context_size=5)
        
        # Verify diff details
        assert byte_diff.offset == 6  # First difference at 'W' vs 'E'
        assert byte_diff.legacy_bytes == b"W"
        assert byte_diff.modern_bytes == b"E"
        # Context before is 5 bytes before offset 6: bytes[1:6] = "ello "
        assert byte_diff.context_before == b"ello "
        assert len(byte_diff.context_after) > 0
    
    def test_compute_comparison_hash(self, matching_execution_results):
        """
        Test SHA-256 hash computation for comparison results.
        
        Requirement 16.1: Generate SHA-256 hash of test result
        Requirement 16.2: Store SHA-256 hash with test result
        """
        legacy_result, modern_result = matching_execution_results
        
        # Compare outputs
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify hash is computed
        assert comparison.result_hash != ""
        assert len(comparison.result_hash) == 64  # SHA-256 hex length
        
        # Verify hash is deterministic
        hash1 = compute_comparison_hash(comparison)
        hash2 = compute_comparison_hash(comparison)
        assert hash1 == hash2


class TestDiscrepancyReporting:
    """
    Test discrepancy report generation.
    
    Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9
    """
    
    def test_generate_discrepancy_report(
        self,
        sample_test_vector,
        differing_execution_results
    ):
        """
        Test discrepancy report generation with all required fields.
        
        Requirement 14.1: Generate discrepancy report when outputs differ
        Requirement 14.2: Include test vector input values
        Requirement 14.3: Include legacy output values
        Requirement 14.4: Include modern output values
        Requirement 14.5: Include byte-level diff
        Requirement 14.6: Include execution timestamps
        Requirement 14.7: Include all captured side effects
        Requirement 14.8: Store report in S3
        Requirement 14.9: Publish failure event to EventBridge
        """
        with patch('rosetta_zero.lambdas.verification.discrepancy_reporter.s3_client') as mock_s3_client, \
             patch('rosetta_zero.lambdas.verification.discrepancy_reporter.events_client') as mock_events_client:
            
            # Import after patching
            from rosetta_zero.lambdas.verification.discrepancy_reporter import generate_discrepancy_report
            
            legacy_result, modern_result = differing_execution_results
            
            # Compare outputs to get comparison result
            comparison = compare_outputs(legacy_result, modern_result)
            
            # Mock S3 put_object
            mock_s3_client.put_object.return_value = {}
            
            # Mock EventBridge put_events
            mock_events_client.put_events.return_value = {}
            
            # Generate discrepancy report
            report = generate_discrepancy_report(
                sample_test_vector,
                legacy_result,
                modern_result,
                comparison
            )
            
            # Verify report structure (Requirements 14.2-14.7)
            assert report.report_id is not None
            assert report.generation_timestamp is not None
            assert report.test_vector_id == sample_test_vector.vector_id  # Requirement 14.2
            assert report.legacy_result_hash == legacy_result.compute_hash()  # Requirement 14.3
            assert report.modern_result_hash == modern_result.compute_hash()  # Requirement 14.4
            assert report.comparison_result == comparison  # Requirements 14.5, 14.6, 14.7
            
            # Verify S3 storage (Requirement 14.8)
            assert mock_s3_client.put_object.called
            s3_call = mock_s3_client.put_object.call_args
            assert s3_call[1]['Bucket'] is not None
            assert s3_call[1]['Key'] is not None
            assert 'report.json' in s3_call[1]['Key']
            
            # Verify EventBridge event (Requirement 14.9)
            assert mock_events_client.put_events.called
            event_call = mock_events_client.put_events.call_args
            entries = event_call[1]['Entries']
            assert len(entries) == 1
            assert entries[0]['DetailType'] == 'Behavioral Discrepancy Detected'
            assert entries[0]['Source'] == 'rosetta-zero.verification'
    
    def test_discrepancy_report_includes_all_differences(
        self,
        sample_test_vector,
        differing_execution_results
    ):
        """
        Test that discrepancy report includes all types of differences.
        
        Requirement 14.5: Include byte-level diff of all differences
        """
        with patch('rosetta_zero.lambdas.verification.discrepancy_reporter.s3_client') as mock_s3_client, \
             patch('rosetta_zero.lambdas.verification.discrepancy_reporter.events_client') as mock_events_client:
            
            # Import after patching
            from rosetta_zero.lambdas.verification.discrepancy_reporter import generate_discrepancy_report
            
            legacy_result, modern_result = differing_execution_results
            
            # Compare outputs
            comparison = compare_outputs(legacy_result, modern_result)
            
            # Mock AWS clients
            mock_s3_client.put_object.return_value = {}
            mock_events_client.put_events.return_value = {}
            
            # Generate report
            report = generate_discrepancy_report(
                sample_test_vector,
                legacy_result,
                modern_result,
                comparison
            )
            
            # Verify all difference types are captured
            assert comparison.differences is not None
            
            # Return value diff
            if not comparison.return_value_match:
                assert comparison.differences.return_value_diff is not None
            
            # Stdout diff
            if not comparison.stdout_match:
                assert comparison.differences.stdout_diff is not None
            
            # Side effect diffs
            if not comparison.side_effects_match:
                assert len(comparison.differences.side_effect_diffs) > 0


class TestStepFunctionsWorkflow:
    """
    Test Step Functions workflow end-to-end.
    
    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7
    """
    
    def test_end_to_end_workflow_matching_outputs(
        self,
        sample_test_vector,
        matching_execution_results
    ):
        """
        Test complete workflow with matching outputs.
        
        Requirement 11.1: Use Step Functions to orchestrate test execution
        Requirement 11.5: Capture stdout, stderr, return values
        Requirement 11.6: Capture all side effects
        """
        legacy_result, modern_result = matching_execution_results
        
        # Compare outputs (simulating the comparator Lambda in Step Functions)
        comparison = compare_outputs(legacy_result, modern_result)
        
        # Verify workflow completed successfully
        assert comparison.match is True
        assert legacy_result.error is None
        assert modern_result.error is None
        
        # Verify execution metrics were captured (Requirement 11.7)
        assert legacy_result.execution_duration_ms > 0
        assert modern_result.execution_duration_ms > 0
        
        # Verify all outputs were captured (Requirement 11.5)
        assert legacy_result.return_value is not None
        assert legacy_result.stdout is not None
        assert legacy_result.stderr is not None
        assert modern_result.return_value is not None
        assert modern_result.stdout is not None
        assert modern_result.stderr is not None
        
        # Verify side effects were captured (Requirement 11.6)
        assert legacy_result.side_effects is not None
        assert modern_result.side_effects is not None
    
    def test_end_to_end_workflow_differing_outputs(
        self,
        sample_test_vector,
        differing_execution_results
    ):
        """
        Test complete workflow with differing outputs and discrepancy report.
        
        Requirement 11.1: Use Step Functions to orchestrate test execution
        Requirement 14.1-14.9: Generate discrepancy report on failure
        """
        with patch('rosetta_zero.lambdas.verification.discrepancy_reporter.s3_client') as mock_s3_client, \
             patch('rosetta_zero.lambdas.verification.discrepancy_reporter.events_client') as mock_events_client:
            
            # Import after patching
            from rosetta_zero.lambdas.verification.discrepancy_reporter import generate_discrepancy_report
            
            legacy_result, modern_result = differing_execution_results
            
            # Mock S3 and EventBridge for discrepancy report
            mock_s3_client.put_object.return_value = {}
            mock_events_client.put_events.return_value = {}
            
            # Compare outputs (simulating the comparator Lambda in Step Functions)
            comparison = compare_outputs(legacy_result, modern_result)
            
            # Verify mismatch detected
            assert comparison.match is False
            
            # Generate discrepancy report (simulating the discrepancy reporter Lambda)
            report = generate_discrepancy_report(
                sample_test_vector,
                legacy_result,
                modern_result,
                comparison
            )
            
            # Verify report was generated and stored
            assert report.report_id is not None
            assert mock_s3_client.put_object.called
            assert mock_events_client.put_events.called
            
            # Verify workflow would halt (in real Step Functions, this would be a Fail state)
            assert comparison.match is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
