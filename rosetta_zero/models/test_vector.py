"""Data models for test vectors and execution results."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Set


class TestVectorCategory(Enum):
    """Categories of test vectors."""
    BOUNDARY = "BOUNDARY"
    DATE_EDGE = "DATE_EDGE"
    CURRENCY = "CURRENCY"
    ENCODING = "ENCODING"
    NULL_EMPTY = "NULL_EMPTY"
    MAX_LENGTH = "MAX_LENGTH"
    RANDOM = "RANDOM"


class ImplementationType(Enum):
    """Type of implementation being tested."""
    LEGACY = "LEGACY"
    MODERN = "MODERN"


@dataclass
class TestVector:
    """Test input for behavioral verification."""
    vector_id: str
    generation_timestamp: str
    random_seed: int
    entry_point: str
    input_parameters: Dict[str, Any]
    expected_coverage: Set[str]
    category: TestVectorCategory

    def to_json(self) -> str:
        """Serialize test vector to JSON."""
        data = {
            'vector_id': self.vector_id,
            'generation_timestamp': self.generation_timestamp,
            'random_seed': self.random_seed,
            'entry_point': self.entry_point,
            'input_parameters': self.input_parameters,
            'expected_coverage': list(self.expected_coverage),
            'category': self.category.value,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'TestVector':
        """Deserialize test vector from JSON."""
        data = json.loads(json_str)
        return cls(
            vector_id=data['vector_id'],
            generation_timestamp=data['generation_timestamp'],
            random_seed=data['random_seed'],
            entry_point=data['entry_point'],
            input_parameters=data['input_parameters'],
            expected_coverage=set(data['expected_coverage']),
            category=TestVectorCategory(data['category']),
        )


@dataclass
class TestVectorBatch:
    """Batch of test vectors for parallel processing."""
    batch_id: str
    vectors: List[TestVector]
    total_count: int
    batch_index: int

    def to_json(self) -> str:
        """Serialize batch to JSON."""
        data = {
            'batch_id': self.batch_id,
            'vectors': [
                json.loads(v.to_json()) for v in self.vectors
            ],
            'total_count': self.total_count,
            'batch_index': self.batch_index,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'TestVectorBatch':
        """Deserialize batch from JSON."""
        data = json.loads(json_str)
        return cls(
            batch_id=data['batch_id'],
            vectors=[
                TestVector.from_json(json.dumps(v)) for v in data['vectors']
            ],
            total_count=data['total_count'],
            batch_index=data['batch_index'],
        )


@dataclass
class ObservedSideEffect:
    """Side effect observed during execution."""
    effect_type: str
    operation: str
    data: bytes
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'effect_type': self.effect_type,
            'operation': self.operation,
            'data': self.data.hex(),
            'timestamp': self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObservedSideEffect':
        """Create from dictionary."""
        return cls(
            effect_type=data['effect_type'],
            operation=data['operation'],
            data=bytes.fromhex(data['data']),
            timestamp=data['timestamp'],
        )


@dataclass
class ExecutionError:
    """Error that occurred during execution."""
    error_type: str
    message: str
    traceback: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result from executing a test vector."""
    test_vector_id: str
    implementation_type: ImplementationType
    execution_timestamp: str
    return_value: bytes
    stdout: bytes
    stderr: bytes
    side_effects: List[ObservedSideEffect]
    execution_duration_ms: int
    error: Optional[ExecutionError] = None

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of execution result."""
        hasher = hashlib.sha256()
        hasher.update(self.return_value)
        hasher.update(self.stdout)
        hasher.update(self.stderr)
        
        # Include side effects in hash
        for side_effect in sorted(self.side_effects, key=lambda x: x.timestamp):
            hasher.update(side_effect.data)
        
        return hasher.hexdigest()

    def to_json(self) -> str:
        """Serialize execution result to JSON."""
        data = {
            'test_vector_id': self.test_vector_id,
            'implementation_type': self.implementation_type.value,
            'execution_timestamp': self.execution_timestamp,
            'return_value': self.return_value.hex(),
            'stdout': self.stdout.hex(),
            'stderr': self.stderr.hex(),
            'side_effects': [se.to_dict() for se in self.side_effects],
            'execution_duration_ms': self.execution_duration_ms,
            'error': {
                'error_type': self.error.error_type,
                'message': self.error.message,
                'traceback': self.error.traceback,
            } if self.error else None,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'ExecutionResult':
        """Deserialize execution result from JSON."""
        data = json.loads(json_str)
        
        error = None
        if data.get('error'):
            error = ExecutionError(
                error_type=data['error']['error_type'],
                message=data['error']['message'],
                traceback=data['error'].get('traceback'),
            )
        
        return cls(
            test_vector_id=data['test_vector_id'],
            implementation_type=ImplementationType(data['implementation_type']),
            execution_timestamp=data['execution_timestamp'],
            return_value=bytes.fromhex(data['return_value']),
            stdout=bytes.fromhex(data['stdout']),
            stderr=bytes.fromhex(data['stderr']),
            side_effects=[
                ObservedSideEffect.from_dict(se) for se in data['side_effects']
            ],
            execution_duration_ms=data['execution_duration_ms'],
            error=error,
        )
