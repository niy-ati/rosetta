"""
Hostile Auditor Lambda handler.

Generates adversarial test vectors using property-based testing techniques
to maximize edge case coverage for behavioral verification.
"""

import json
import os
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

from rosetta_zero.models.logic_map import LogicMap
from rosetta_zero.models.test_vector import TestVector, TestVectorBatch
from rosetta_zero.utils.retry import RetryStrategy, TransientError

# Initialize PowerTools
logger = Logger(service="hostile-auditor")
tracer = Tracer(service="hostile-auditor")
metrics = Metrics(namespace="RosettaZero", service="hostile-auditor")

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


class HostileAuditor:
    """Generates adversarial test vectors for behavioral verification."""
    
    def __init__(
        self,
        s3_client,
        dynamodb_resource,
        target_count: int = 1_000_000,
        target_coverage: float = 0.95,
        batch_size: int = 10_000
    ):
        """
        Initialize Hostile Auditor.
        
        Args:
            s3_client: Boto3 S3 client
            dynamodb_resource: Boto3 DynamoDB resource
            target_count: Target number of test vectors to generate
            target_coverage: Target branch coverage percentage (0.0-1.0)
            batch_size: Number of test vectors per batch for storage
        """
        self.s3_client = s3_client
        self.dynamodb = dynamodb_resource
        self.target_count = target_count
        self.target_coverage = target_coverage
        self.batch_size = batch_size
        self.retry_strategy = RetryStrategy(max_retries=3, backoff_base=2)
    
    @tracer.capture_method
    def generate_test_vectors(
        self,
        logic_map: LogicMap,
        random_seed: Optional[int] = None
    ) -> List[TestVector]:
        """
        Generate adversarial test vectors using property-based testing.
        
        Uses Hypothesis library to generate diverse inputs targeting:
        - Boundary values (MAX_INT, MIN_INT)
        - Date edge cases (leap years, century boundaries)
        - Currency overflow scenarios
        - Character encoding edge cases (EBCDIC mappings)
        - Null and empty inputs
        - Maximum length strings
        
        Args:
            logic_map: Logic Map defining system behavior
            random_seed: Seed for reproducibility (stored with results)
            
        Returns:
            List of TestVector objects covering all entry points and
            control flow branches.
        """
        if random_seed is None:
            random_seed = int(time.time())
        
        logger.info(
            "Starting test vector generation",
            extra={
                "artifact_id": logic_map.artifact_id,
                "target_count": self.target_count,
                "random_seed": random_seed,
                "target_coverage": self.target_coverage
            }
        )
        
        # Store random seed for reproducibility
        self._store_random_seed(logic_map.artifact_id, random_seed)
        
        test_vectors = []
        
        # Import test generation modules (will be implemented in subsequent tasks)
        from .test_generation import (
            create_strategy_for_entry_point,
            generate_boundary_tests,
            generate_date_edge_tests,
            generate_currency_tests,
            generate_encoding_tests,
            generate_null_empty_tests,
            generate_max_length_tests,
            generate_random_tests,
            calculate_expected_coverage,
            generate_coverage_tests
        )
        
        # Define Hypothesis strategies for each entry point
        strategies = {}
        for entry_point in logic_map.entry_points:
            strategies[entry_point.name] = create_strategy_for_entry_point(
                entry_point, random_seed
            )
        
        # Generate targeted test vectors for each category
        logger.info("Generating boundary value tests")
        boundary_vectors = generate_boundary_tests(logic_map, strategies)
        test_vectors.extend(boundary_vectors)
        metrics.add_metric(
            name="BoundaryTestsGenerated",
            unit=MetricUnit.Count,
            value=len(boundary_vectors)
        )
        
        logger.info("Generating date edge case tests")
        date_vectors = generate_date_edge_tests(logic_map, strategies)
        test_vectors.extend(date_vectors)
        metrics.add_metric(
            name="DateEdgeTestsGenerated",
            unit=MetricUnit.Count,
            value=len(date_vectors)
        )
        
        logger.info("Generating currency overflow tests")
        currency_vectors = generate_currency_tests(logic_map, strategies)
        test_vectors.extend(currency_vectors)
        metrics.add_metric(
            name="CurrencyTestsGenerated",
            unit=MetricUnit.Count,
            value=len(currency_vectors)
        )
        
        logger.info("Generating character encoding tests")
        encoding_vectors = generate_encoding_tests(logic_map, strategies)
        test_vectors.extend(encoding_vectors)
        metrics.add_metric(
            name="EncodingTestsGenerated",
            unit=MetricUnit.Count,
            value=len(encoding_vectors)
        )
        
        logger.info("Generating null/empty input tests")
        null_vectors = generate_null_empty_tests(logic_map, strategies)
        test_vectors.extend(null_vectors)
        metrics.add_metric(
            name="NullEmptyTestsGenerated",
            unit=MetricUnit.Count,
            value=len(null_vectors)
        )
        
        logger.info("Generating maximum length tests")
        max_length_vectors = generate_max_length_tests(logic_map, strategies)
        test_vectors.extend(max_length_vectors)
        metrics.add_metric(
            name="MaxLengthTestsGenerated",
            unit=MetricUnit.Count,
            value=len(max_length_vectors)
        )
        
        # Generate random tests to reach target count
        remaining_count = self.target_count - len(test_vectors)
        if remaining_count > 0:
            logger.info(f"Generating {remaining_count} random tests")
            random_vectors = generate_random_tests(
                logic_map, strategies, remaining_count, random_seed
            )
            test_vectors.extend(random_vectors)
            metrics.add_metric(
                name="RandomTestsGenerated",
                unit=MetricUnit.Count,
                value=len(random_vectors)
            )
        
        # Verify branch coverage
        logger.info("Verifying branch coverage")
        coverage = calculate_expected_coverage(test_vectors, logic_map)
        
        logger.info(
            "Branch coverage calculated",
            extra={
                "coverage_percent": coverage.branch_coverage_percent,
                "target_percent": self.target_coverage * 100
            }
        )
        
        metrics.add_metric(
            name="BranchCoverage",
            unit=MetricUnit.Percent,
            value=coverage.branch_coverage_percent
        )
        
        # Generate additional tests for uncovered branches if needed
        if coverage.branch_coverage_percent < (self.target_coverage * 100):
            logger.warning(
                "Coverage below target, generating additional tests",
                extra={
                    "uncovered_branches": len(coverage.uncovered_branches)
                }
            )
            additional_vectors = generate_coverage_tests(
                logic_map, coverage.uncovered_branches, strategies, random_seed
            )
            test_vectors.extend(additional_vectors)
            
            # Recalculate coverage
            coverage = calculate_expected_coverage(test_vectors, logic_map)
            logger.info(
                "Updated coverage after additional tests",
                extra={"coverage_percent": coverage.branch_coverage_percent}
            )
        
        logger.info(
            "Test vector generation complete",
            extra={
                "total_vectors": len(test_vectors),
                "final_coverage": coverage.branch_coverage_percent
            }
        )
        
        metrics.add_metric(
            name="TotalTestVectorsGenerated",
            unit=MetricUnit.Count,
            value=len(test_vectors)
        )
        
        return test_vectors
    
    @tracer.capture_method
    def store_test_vectors_batched(
        self,
        test_vectors: List[TestVector],
        artifact_id: str,
        bucket_name: str
    ) -> None:
        """
        Store test vectors in S3 in batches for parallel processing.
        
        Args:
            test_vectors: List of test vectors to store
            artifact_id: Artifact identifier for organizing storage
            bucket_name: S3 bucket name for test vectors
        """
        logger.info(
            "Storing test vectors in batches",
            extra={
                "total_vectors": len(test_vectors),
                "batch_size": self.batch_size,
                "artifact_id": artifact_id
            }
        )
        
        batch_count = (len(test_vectors) + self.batch_size - 1) // self.batch_size
        
        for batch_index in range(batch_count):
            start_idx = batch_index * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(test_vectors))
            batch_vectors = test_vectors[start_idx:end_idx]
            
            batch = TestVectorBatch(
                batch_id=f"{artifact_id}-batch-{batch_index:06d}",
                vectors=batch_vectors,
                total_count=len(test_vectors),
                batch_index=batch_index
            )
            
            # Store batch in S3
            s3_key = f"test-vectors/{artifact_id}/batch-{batch_index:06d}.json"
            
            def store_batch():
                self.s3_client.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=batch.to_json().encode('utf-8'),
                    ContentType='application/json'
                )
            
            try:
                self.retry_strategy.execute_with_retry(
                    store_batch,
                    operation_name=f"store_batch_{batch_index}"
                )
                
                logger.debug(
                    "Stored test vector batch",
                    extra={
                        "batch_index": batch_index,
                        "batch_size": len(batch_vectors),
                        "s3_key": s3_key
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to store test vector batch",
                    extra={
                        "batch_index": batch_index,
                        "error": str(e)
                    }
                )
                raise
        
        logger.info(
            "Test vector storage complete",
            extra={
                "total_batches": batch_count,
                "artifact_id": artifact_id
            }
        )
        
        metrics.add_metric(
            name="TestVectorBatchesStored",
            unit=MetricUnit.Count,
            value=batch_count
        )
    
    def _store_random_seed(self, artifact_id: str, random_seed: int) -> None:
        """
        Store random seed in DynamoDB for reproducibility.
        
        Args:
            artifact_id: Artifact identifier
            random_seed: Random seed used for test generation
        """
        table = self.dynamodb.Table(os.environ.get('WORKFLOW_TABLE_NAME', 'rosetta-zero-workflow-phases'))
        
        table.put_item(
            Item={
                'workflow_id': artifact_id,
                'phase_name': 'aggression',
                'status': 'in_progress',
                'random_seed': random_seed,
                'start_timestamp': datetime.utcnow().isoformat(),
                'metadata': {
                    'target_count': self.target_count,
                    'target_coverage': self.target_coverage
                }
            }
        )
        
        logger.info(
            "Stored random seed for reproducibility",
            extra={
                "artifact_id": artifact_id,
                "random_seed": random_seed
            }
        )


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for Hostile Auditor.
    
    Expected event structure:
    {
        "logic_map_s3_bucket": "bucket-name",
        "logic_map_s3_key": "logic-maps/artifact-id/version/logic-map.json",
        "test_vectors_s3_bucket": "bucket-name",
        "target_count": 1000000,
        "random_seed": 12345 (optional),
        "target_coverage": 0.95
    }
    
    Returns:
        {
            "statusCode": 200,
            "body": {
                "artifact_id": "...",
                "total_vectors": 1000000,
                "coverage_percent": 95.5,
                "random_seed": 12345,
                "batches_stored": 100
            }
        }
    """
    try:
        # Extract parameters from event
        logic_map_bucket = event['logic_map_s3_bucket']
        logic_map_key = event['logic_map_s3_key']
        test_vectors_bucket = event['test_vectors_s3_bucket']
        target_count = event.get('target_count', 1_000_000)
        random_seed = event.get('random_seed')
        target_coverage = event.get('target_coverage', 0.95)
        
        logger.info(
            "Hostile Auditor invoked",
            extra={
                "logic_map_key": logic_map_key,
                "target_count": target_count,
                "random_seed": random_seed
            }
        )
        
        # Load Logic Map from S3
        logger.info("Loading Logic Map from S3")
        response = s3_client.get_object(
            Bucket=logic_map_bucket,
            Key=logic_map_key
        )
        logic_map_json = response['Body'].read().decode('utf-8')
        logic_map = LogicMap.from_json(logic_map_json)
        
        logger.info(
            "Logic Map loaded",
            extra={
                "artifact_id": logic_map.artifact_id,
                "entry_points": len(logic_map.entry_points),
                "control_flow_nodes": len(logic_map.control_flow.nodes)
            }
        )
        
        # Initialize Hostile Auditor
        auditor = HostileAuditor(
            s3_client=s3_client,
            dynamodb_resource=dynamodb,
            target_count=target_count,
            target_coverage=target_coverage
        )
        
        # Generate test vectors
        test_vectors = auditor.generate_test_vectors(
            logic_map=logic_map,
            random_seed=random_seed
        )
        
        # Store test vectors in batches
        auditor.store_test_vectors_batched(
            test_vectors=test_vectors,
            artifact_id=logic_map.artifact_id,
            bucket_name=test_vectors_bucket
        )
        
        # Calculate final metrics
        from .test_generation import calculate_expected_coverage
        coverage = calculate_expected_coverage(test_vectors, logic_map)
        
        batch_count = (len(test_vectors) + auditor.batch_size - 1) // auditor.batch_size
        
        result = {
            "artifact_id": logic_map.artifact_id,
            "total_vectors": len(test_vectors),
            "coverage_percent": coverage.branch_coverage_percent,
            "random_seed": random_seed or int(time.time()),
            "batches_stored": batch_count,
            "entry_points_covered": coverage.entry_points_covered,
            "total_entry_points": coverage.total_entry_points
        }
        
        logger.info(
            "Hostile Auditor completed successfully",
            extra=result
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
        
    except KeyError as e:
        logger.error(f"Missing required parameter: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Missing required parameter",
                "parameter": str(e)
            })
        }
    
    except Exception as e:
        logger.exception("Hostile Auditor failed")
        metrics.add_metric(name="Errors", unit=MetricUnit.Count, value=1)
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
