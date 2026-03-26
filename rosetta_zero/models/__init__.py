"""Data models for Rosetta Zero."""

from .logic_map import (
    LogicMap,
    EntryPoint,
    DataStructure,
    ControlFlowGraph,
    ControlFlowNode,
    ControlFlowEdge,
    SideEffect,
    PrecisionConfig,
    Parameter,
    Field,
    DataType,
    SideEffectType,
    TimingRequirement,
    FixedPointOp,
    RoundingMode,
    Dependency,
    Path,
)

from .test_vector import (
    TestVector,
    TestVectorBatch,
    TestVectorCategory,
    ExecutionResult,
    ExecutionError,
    ObservedSideEffect,
    ImplementationType,
)

from .comparison import (
    ComparisonResult,
    DifferenceDetails,
    ByteDiff,
    SideEffectDiff,
    DiscrepancyReport,
    EquivalenceCertificate,
    SignedCertificate,
    ArtifactMetadata,
    CoverageReport,
)

from .config import (
    RosettaZeroConfig,
    parse_configuration,
    format_configuration,
)

__all__ = [
    # Logic Map models
    "LogicMap",
    "EntryPoint",
    "DataStructure",
    "ControlFlowGraph",
    "ControlFlowNode",
    "ControlFlowEdge",
    "SideEffect",
    "PrecisionConfig",
    "Parameter",
    "Field",
    "DataType",
    "SideEffectType",
    "TimingRequirement",
    "FixedPointOp",
    "RoundingMode",
    "Dependency",
    "Path",
    # Test Vector models
    "TestVector",
    "TestVectorBatch",
    "TestVectorCategory",
    "ExecutionResult",
    "ExecutionError",
    "ObservedSideEffect",
    "ImplementationType",
    # Comparison models
    "ComparisonResult",
    "DifferenceDetails",
    "ByteDiff",
    "SideEffectDiff",
    "DiscrepancyReport",
    "EquivalenceCertificate",
    "SignedCertificate",
    "ArtifactMetadata",
    "CoverageReport",
    # Configuration
    "RosettaZeroConfig",
    "parse_configuration",
    "format_configuration",
]
