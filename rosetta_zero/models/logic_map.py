"""Data models for Logic Maps and artifacts."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Set, Any


class DataType(Enum):
    """Data types in legacy systems."""
    INTEGER = "INTEGER"
    STRING = "STRING"
    DATE = "DATE"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    BINARY = "BINARY"
    ARRAY = "ARRAY"
    STRUCT = "STRUCT"


class SideEffectType(Enum):
    """Types of observable side effects."""
    FILE_IO = "FILE_IO"
    DATABASE = "DATABASE"
    NETWORK = "NETWORK"
    GLOBAL_VAR = "GLOBAL_VAR"
    HARDWARE = "HARDWARE"


class RoundingMode(Enum):
    """Arithmetic rounding modes."""
    ROUND_HALF_UP = "ROUND_HALF_UP"
    ROUND_HALF_DOWN = "ROUND_HALF_DOWN"
    ROUND_HALF_EVEN = "ROUND_HALF_EVEN"
    ROUND_UP = "ROUND_UP"
    ROUND_DOWN = "ROUND_DOWN"
    TRUNCATE = "TRUNCATE"


@dataclass
class Parameter:
    """Function parameter definition."""
    name: str
    type: DataType
    description: str
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    max_length: Optional[int] = None
    decimal_places: Optional[int] = None


@dataclass
class Field:
    """Data structure field definition."""
    name: str
    type: DataType
    offset: int
    size_bytes: int
    description: str


@dataclass
class TimingRequirement:
    """Timing behavior requirement."""
    operation: str
    min_duration_ms: Optional[int] = None
    max_duration_ms: Optional[int] = None
    delay_ms: Optional[int] = None
    description: str = ""


@dataclass
class FixedPointOp:
    """Fixed-point arithmetic operation."""
    operation: str
    precision: int
    scale: int
    description: str


@dataclass
class Dependency:
    """External dependency."""
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class Path:
    """Control flow path."""
    path_id: str
    nodes: List[str]
    description: str = ""


@dataclass
class EntryPoint:
    """Entry point in legacy system."""
    name: str
    parameters: List[Parameter]
    return_type: DataType
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'parameters': [
                {
                    'name': p.name,
                    'type': p.type.value,
                    'description': p.description,
                    'min_value': p.min_value,
                    'max_value': p.max_value,
                    'max_length': p.max_length,
                    'decimal_places': p.decimal_places,
                }
                for p in self.parameters
            ],
            'return_type': self.return_type.value,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EntryPoint':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            parameters=[
                Parameter(
                    name=p['name'],
                    type=DataType(p['type']),
                    description=p['description'],
                    min_value=p.get('min_value'),
                    max_value=p.get('max_value'),
                    max_length=p.get('max_length'),
                    decimal_places=p.get('decimal_places'),
                )
                for p in data['parameters']
            ],
            return_type=DataType(data['return_type']),
            description=data['description'],
        )


@dataclass
class DataStructure:
    """Data structure in legacy system."""
    name: str
    fields: List[Field]
    size_bytes: int
    alignment: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'fields': [
                {
                    'name': f.name,
                    'type': f.type.value,
                    'offset': f.offset,
                    'size_bytes': f.size_bytes,
                    'description': f.description,
                }
                for f in self.fields
            ],
            'size_bytes': self.size_bytes,
            'alignment': self.alignment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataStructure':
        """Create from dictionary."""
        return cls(
            name=data['name'],
            fields=[
                Field(
                    name=f['name'],
                    type=DataType(f['type']),
                    offset=f['offset'],
                    size_bytes=f['size_bytes'],
                    description=f['description'],
                )
                for f in data['fields']
            ],
            size_bytes=data['size_bytes'],
            alignment=data['alignment'],
        )


@dataclass
class ControlFlowNode:
    """Node in control flow graph."""
    node_id: str
    type: str
    description: str
    source_line: Optional[int] = None


@dataclass
class ControlFlowEdge:
    """Edge in control flow graph."""
    from_node: str
    to_node: str
    condition: Optional[str] = None


@dataclass
class ControlFlowGraph:
    """Control flow representation."""
    nodes: List[ControlFlowNode]
    edges: List[ControlFlowEdge]

    def calculate_branch_coverage(self, executed_paths: List[Path]) -> float:
        """Calculate branch coverage percentage."""
        if not self.edges:
            return 100.0
        
        executed_edges = set()
        for path in executed_paths:
            for i in range(len(path.nodes) - 1):
                edge = (path.nodes[i], path.nodes[i + 1])
                executed_edges.add(edge)
        
        total_edges = len(self.edges)
        covered_edges = sum(
            1 for edge in self.edges
            if (edge.from_node, edge.to_node) in executed_edges
        )
        
        return (covered_edges / total_edges) * 100.0 if total_edges > 0 else 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'nodes': [
                {
                    'node_id': n.node_id,
                    'type': n.type,
                    'description': n.description,
                    'source_line': n.source_line,
                }
                for n in self.nodes
            ],
            'edges': [
                {
                    'from_node': e.from_node,
                    'to_node': e.to_node,
                    'condition': e.condition,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControlFlowGraph':
        """Create from dictionary."""
        return cls(
            nodes=[
                ControlFlowNode(
                    node_id=n['node_id'],
                    type=n['type'],
                    description=n['description'],
                    source_line=n.get('source_line'),
                )
                for n in data['nodes']
            ],
            edges=[
                ControlFlowEdge(
                    from_node=e['from_node'],
                    to_node=e['to_node'],
                    condition=e.get('condition'),
                )
                for e in data['edges']
            ],
        )


@dataclass
class SideEffect:
    """Observable side effect in legacy system."""
    operation_type: SideEffectType
    scope: str
    description: str
    timing_requirements: Optional[TimingRequirement] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'operation_type': self.operation_type.value,
            'scope': self.scope,
            'description': self.description,
        }
        if self.timing_requirements:
            result['timing_requirements'] = {
                'operation': self.timing_requirements.operation,
                'min_duration_ms': self.timing_requirements.min_duration_ms,
                'max_duration_ms': self.timing_requirements.max_duration_ms,
                'delay_ms': self.timing_requirements.delay_ms,
                'description': self.timing_requirements.description,
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SideEffect':
        """Create from dictionary."""
        timing_req = None
        if 'timing_requirements' in data:
            tr = data['timing_requirements']
            timing_req = TimingRequirement(
                operation=tr['operation'],
                min_duration_ms=tr.get('min_duration_ms'),
                max_duration_ms=tr.get('max_duration_ms'),
                delay_ms=tr.get('delay_ms'),
                description=tr.get('description', ''),
            )
        
        return cls(
            operation_type=SideEffectType(data['operation_type']),
            scope=data['scope'],
            description=data['description'],
            timing_requirements=timing_req,
        )


@dataclass
class PrecisionConfig:
    """Arithmetic precision requirements."""
    fixed_point_operations: List[FixedPointOp]
    floating_point_precision: Dict[str, int]
    rounding_modes: Dict[str, RoundingMode]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'fixed_point_operations': [
                {
                    'operation': op.operation,
                    'precision': op.precision,
                    'scale': op.scale,
                    'description': op.description,
                }
                for op in self.fixed_point_operations
            ],
            'floating_point_precision': self.floating_point_precision,
            'rounding_modes': {
                k: v.value for k, v in self.rounding_modes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrecisionConfig':
        """Create from dictionary."""
        return cls(
            fixed_point_operations=[
                FixedPointOp(
                    operation=op['operation'],
                    precision=op['precision'],
                    scale=op['scale'],
                    description=op['description'],
                )
                for op in data['fixed_point_operations']
            ],
            floating_point_precision=data['floating_point_precision'],
            rounding_modes={
                k: RoundingMode(v) for k, v in data['rounding_modes'].items()
            },
        )


@dataclass
class LogicMap:
    """Implementation-agnostic representation of legacy system behavior."""
    artifact_id: str
    artifact_version: str
    extraction_timestamp: str
    entry_points: List[EntryPoint]
    data_structures: List[DataStructure]
    control_flow: ControlFlowGraph
    dependencies: List[Dependency]
    side_effects: List[SideEffect]
    arithmetic_precision: PrecisionConfig

    def to_json(self) -> str:
        """Serialize Logic Map to JSON for storage."""
        data = {
            'artifact_id': self.artifact_id,
            'artifact_version': self.artifact_version,
            'extraction_timestamp': self.extraction_timestamp,
            'entry_points': [ep.to_dict() for ep in self.entry_points],
            'data_structures': [ds.to_dict() for ds in self.data_structures],
            'control_flow': self.control_flow.to_dict(),
            'dependencies': [
                {
                    'name': d.name,
                    'type': d.type,
                    'description': d.description,
                    'required': d.required,
                }
                for d in self.dependencies
            ],
            'side_effects': [se.to_dict() for se in self.side_effects],
            'arithmetic_precision': self.arithmetic_precision.to_dict(),
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'LogicMap':
        """Deserialize Logic Map from JSON."""
        data = json.loads(json_str)
        return cls(
            artifact_id=data['artifact_id'],
            artifact_version=data['artifact_version'],
            extraction_timestamp=data['extraction_timestamp'],
            entry_points=[
                EntryPoint.from_dict(ep) for ep in data['entry_points']
            ],
            data_structures=[
                DataStructure.from_dict(ds) for ds in data['data_structures']
            ],
            control_flow=ControlFlowGraph.from_dict(data['control_flow']),
            dependencies=[
                Dependency(
                    name=d['name'],
                    type=d['type'],
                    description=d['description'],
                    required=d.get('required', True),
                )
                for d in data['dependencies']
            ],
            side_effects=[
                SideEffect.from_dict(se) for se in data['side_effects']
            ],
            arithmetic_precision=PrecisionConfig.from_dict(
                data['arithmetic_precision']
            ),
        )

    def validate(self) -> List[str]:
        """Validate Logic Map completeness and return list of errors."""
        errors = []
        
        if not self.artifact_id:
            errors.append("artifact_id is required")
        
        if not self.artifact_version:
            errors.append("artifact_version is required")
        
        if not self.entry_points:
            errors.append("at least one entry point is required")
        
        if not self.control_flow.nodes:
            errors.append("control flow graph must have at least one node")
        
        # Validate entry points
        for i, ep in enumerate(self.entry_points):
            if not ep.name:
                errors.append(f"entry point {i} missing name")
            if not ep.parameters and not ep.description:
                errors.append(f"entry point {ep.name} missing parameters or description")
        
        # Validate control flow edges reference valid nodes
        node_ids = {node.node_id for node in self.control_flow.nodes}
        for edge in self.control_flow.edges:
            if edge.from_node not in node_ids:
                errors.append(f"edge references invalid from_node: {edge.from_node}")
            if edge.to_node not in node_ids:
                errors.append(f"edge references invalid to_node: {edge.to_node}")
        
        return errors
