"""
Unit tests for Hostile Auditor test vector generation.

Tests cover:
- Boundary value generation
- Date edge case generation
- Currency overflow generation
- Character encoding edge case generation
- Null/empty input generation
- Maximum length generation
- Branch coverage calculation
"""

import pytest
from datetime import date
from decimal import Decimal
from typing import List

from rosetta_zero.lambdas.hostile_auditor.test_generation import (
    generate_boundary_tests,
    generate_date_edge_tests,
    generate_currency_tests,
    generate_encoding_tests,
    generate_null_empty_tests,
    generate_max_length_tests,
    calculate_expected_coverage,
    create_strategy_for_entry_point,
)
from rosetta_zero.models.logic_map import (
    LogicMap,
    EntryPoint,
    Parameter,
    DataType,
    ControlFlowGraph,
    ControlFlowNode,
    ControlFlowEdge,
    DataStructure,
    Dependency,
    SideEffect,
    SideEffectType,
    PrecisionConfig,
)
from rosetta_zero.models.test_vector import TestVectorCategory


# Test fixtures

@pytest.fixture
def sample_logic_map():
    """Create a sample Logic Map for testing."""
    entry_points = [
        EntryPoint(
            name="calculate_interest",
            parameters=[
                Parameter(
                    name="principal",
                    type=DataType.DECIMAL,
                    description="Principal amount",
                    min_value=Decimal('0'),
                    max_value=Decimal('999999999.99'),
                    decimal_places=2,
                ),
                Parameter(
                    name="rate",
                    type=DataType.DECIMAL,
                    description="Interest rate",
                    min_value=Decimal('0'),
                    max_value=Decimal('100'),
                    decimal_places=4,
                ),
                Parameter(
                    name="years",
                    type=DataType.INTEGER,
                    description="Number of years",
                    min_value=1,
                    max_value=30,
                ),
            ],
            return_type=DataType.DECIMAL,
            description="Calculate compound interest",
        ),
        EntryPoint(
            name="validate_date",
            parameters=[
                Parameter(
                    name="input_date",
                    type=DataType.DATE,
                    description="Date to validate",
                ),
            ],
            return_type=DataType.BOOLEAN,
            description="Validate date format",
        ),
        EntryPoint(
            name="process_string",
            parameters=[
                Parameter(
                    name="input_text",
                    type=DataType.STRING,
                    description="Text to process",
                    max_length=255,
                ),
            ],
            return_type=DataType.STRING,
            description="Process input string",
        ),
    ]
    
    control_flow = ControlFlowGraph(
        nodes=[
            ControlFlowNode(node_id="start", type="entry", description="Entry point"),
            ControlFlowNode(node_id="branch1", type="condition", description="Check principal > 0"),
            ControlFlowNode(node_id="branch2", type="condition", description="Check rate > 0"),
            ControlFlowNode(node_id="calc", type="operation", description="Calculate interest"),
            ControlFlowNode(node_id="end", type="exit", description="Return result"),
        ],
        edges=[
            ControlFlowEdge(from_node="start", to_node="branch1"),
            ControlFlowEdge(from_node="branch1", to_node="branch2", condition="principal > 0"),
            ControlFlowEdge(from_node="branch1", to_node="end", condition="principal <= 0"),
            ControlFlowEdge(from_node="branch2", to_node="calc", condition="rate > 0"),
            ControlFlowEdge(from_node="branch2", to_node="end", condition="rate <= 0"),
            ControlFlowEdge(from_node="calc", to_node="end"),
        ],
    )
    
    return LogicMap(
        artifact_id="test-artifact-001",
        artifact_version="1.0.0",
        extraction_timestamp="2024-01-01T00:00:00Z",
        entry_points=entry_points,
        data_structures=[],
        control_flow=control_flow,
        dependencies=[],
        side_effects=[],
        arithmetic_precision=PrecisionConfig(
            fixed_point_operations=[],
            floating_point_precision={},
            rounding_modes={},
        ),
    )


# Test boundary value generation

def test_generate_boundary_tests_integer_parameters(sample_logic_map):
    """Test boundary value generation for integer parameters."""
    vectors = generate_boundary_tests(sample_logic_map, {})
    
    # Filter vectors for the years parameter
    years_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "years" in v.input_parameters
    ]
    
    # Should generate boundary values: min (1), max (30), 0, -1, 1, min+1 (2), max-1 (29)
    # But 0 and -1 are outside the valid range [1, 30], so they should be filtered
    years_values = [v.input_parameters["years"] for v in years_vectors]
    
    assert 1 in years_values, "Should include minimum value"
    assert 30 in years_values, "Should include maximum value"
    assert 2 in years_values, "Should include min+1"
    assert 29 in years_values, "Should include max-1"
    assert all(v.category == TestVectorCategory.BOUNDARY for v in years_vectors)


def test_generate_boundary_tests_decimal_parameters(sample_logic_map):
    """Test boundary value generation for decimal parameters."""
    vectors = generate_boundary_tests(sample_logic_map, {})
    
    # Filter vectors for the principal parameter
    principal_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "principal" in v.input_parameters
    ]
    
    principal_values = [v.input_parameters["principal"] for v in principal_vectors]
    
    assert Decimal('0') in principal_values, "Should include minimum value"
    assert Decimal('999999999.99') in principal_values, "Should include maximum value"
    assert Decimal('0.01') in principal_values, "Should include small positive value"
    assert all(v.category == TestVectorCategory.BOUNDARY for v in principal_vectors)


def test_boundary_tests_have_deterministic_seed(sample_logic_map):
    """Test that boundary tests use deterministic seed (0)."""
    vectors = generate_boundary_tests(sample_logic_map, {})
    
    assert all(v.random_seed == 0 for v in vectors), "Boundary tests should use seed 0"


# Test date edge case generation

def test_generate_date_edge_tests_leap_years(sample_logic_map):
    """Test date edge case generation includes leap years."""
    vectors = generate_date_edge_tests(sample_logic_map, {})
    
    # Filter vectors for date parameters
    date_vectors = [
        v for v in vectors
        if v.entry_point == "validate_date"
    ]
    
    date_values = [v.input_parameters["input_date"] for v in date_vectors]
    
    # Check for leap year dates
    assert date(2000, 2, 29) in date_values, "Should include leap year 2000"
    assert date(2004, 2, 29) in date_values, "Should include leap year 2004"
    assert date(2024, 2, 29) in date_values, "Should include leap year 2024"


def test_generate_date_edge_tests_century_boundaries(sample_logic_map):
    """Test date edge case generation includes century boundaries."""
    vectors = generate_date_edge_tests(sample_logic_map, {})
    
    date_vectors = [
        v for v in vectors
        if v.entry_point == "validate_date"
    ]
    
    date_values = [v.input_parameters["input_date"] for v in date_vectors]
    
    # Check for century boundaries
    assert date(1900, 2, 28) in date_values, "Should include 1900 (not a leap year)"
    assert date(2000, 2, 29) in date_values, "Should include 2000 (leap year)"
    assert date(2100, 2, 28) in date_values, "Should include 2100 (not a leap year)"


def test_generate_date_edge_tests_y2k(sample_logic_map):
    """Test date edge case generation includes Y2K scenarios."""
    vectors = generate_date_edge_tests(sample_logic_map, {})
    
    date_vectors = [
        v for v in vectors
        if v.entry_point == "validate_date"
    ]
    
    date_values = [v.input_parameters["input_date"] for v in date_vectors]
    
    # Check for Y2K dates
    assert date(1999, 12, 31) in date_values, "Should include day before Y2K"
    assert date(2000, 1, 1) in date_values, "Should include Y2K"


def test_date_edge_tests_category(sample_logic_map):
    """Test that date edge tests have correct category."""
    vectors = generate_date_edge_tests(sample_logic_map, {})
    
    assert all(v.category == TestVectorCategory.DATE_EDGE for v in vectors)


# Test currency overflow generation

def test_generate_currency_tests_maximum_precision(sample_logic_map):
    """Test currency overflow generation includes maximum precision values."""
    vectors = generate_currency_tests(sample_logic_map, {})
    
    # Filter vectors for decimal parameters
    currency_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "principal" in v.input_parameters
    ]
    
    principal_values = [v.input_parameters["principal"] for v in currency_vectors]
    
    # Check for maximum precision values
    assert Decimal('999999999.99') in principal_values, "Should include maximum value"
    assert Decimal('0.01') in principal_values, "Should include minimum positive"


def test_generate_currency_tests_rounding_boundaries(sample_logic_map):
    """Test currency overflow generation includes rounding boundaries."""
    vectors = generate_currency_tests(sample_logic_map, {})
    
    currency_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "principal" in v.input_parameters
    ]
    
    principal_values = [v.input_parameters["principal"] for v in currency_vectors]
    
    # Check for rounding boundary values
    assert Decimal('0.005') in principal_values, "Should include rounding boundary"
    assert Decimal('0.995') in principal_values, "Should include rounding boundary"


def test_generate_currency_tests_respects_bounds(sample_logic_map):
    """Test currency tests respect parameter bounds."""
    vectors = generate_currency_tests(sample_logic_map, {})
    
    # Check that all principal values are within bounds
    principal_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "principal" in v.input_parameters
    ]
    
    for vector in principal_vectors:
        principal = vector.input_parameters["principal"]
        assert Decimal('0') <= principal <= Decimal('999999999.99'), \
            f"Principal {principal} should be within bounds"


def test_currency_tests_category(sample_logic_map):
    """Test that currency tests have correct category."""
    vectors = generate_currency_tests(sample_logic_map, {})
    
    assert all(v.category == TestVectorCategory.CURRENCY for v in vectors)


# Test character encoding edge case generation

def test_generate_encoding_tests_empty_string(sample_logic_map):
    """Test encoding tests include empty string."""
    vectors = generate_encoding_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    string_values = [v.input_parameters["input_text"] for v in string_vectors]
    
    assert "" in string_values, "Should include empty string"


def test_generate_encoding_tests_special_characters(sample_logic_map):
    """Test encoding tests include special characters."""
    vectors = generate_encoding_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    string_values = [v.input_parameters["input_text"] for v in string_vectors]
    
    # Check for special characters
    assert "!@#$%^&*()" in string_values, "Should include special characters"
    assert any("\t" in s for s in string_values), "Should include tab character"
    assert any("\n" in s for s in string_values), "Should include newline"


def test_generate_encoding_tests_whitespace(sample_logic_map):
    """Test encoding tests include whitespace variations."""
    vectors = generate_encoding_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    string_values = [v.input_parameters["input_text"] for v in string_vectors]
    
    assert " " in string_values, "Should include single space"
    assert "\t" in string_values, "Should include tab"


def test_generate_encoding_tests_respects_max_length(sample_logic_map):
    """Test encoding tests respect max_length constraint."""
    vectors = generate_encoding_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    # Max length for process_string is 255
    for vector in string_vectors:
        text = vector.input_parameters["input_text"]
        assert len(text) <= 255, f"String length {len(text)} exceeds max_length 255"


def test_encoding_tests_category(sample_logic_map):
    """Test that encoding tests have correct category."""
    vectors = generate_encoding_tests(sample_logic_map, {})
    
    assert all(v.category == TestVectorCategory.ENCODING for v in vectors)


# Test null/empty input generation

def test_generate_null_empty_tests_string(sample_logic_map):
    """Test null/empty generation for string parameters."""
    vectors = generate_null_empty_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    assert len(string_vectors) > 0, "Should generate null/empty tests for strings"
    assert all(v.input_parameters["input_text"] == "" for v in string_vectors)


def test_generate_null_empty_tests_integer(sample_logic_map):
    """Test null/empty generation for integer parameters."""
    vectors = generate_null_empty_tests(sample_logic_map, {})
    
    integer_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "years" in v.input_parameters
    ]
    
    # For integers, "null" is represented as 0
    assert any(v.input_parameters["years"] == 0 for v in integer_vectors)


def test_generate_null_empty_tests_decimal(sample_logic_map):
    """Test null/empty generation for decimal parameters."""
    vectors = generate_null_empty_tests(sample_logic_map, {})
    
    decimal_vectors = [
        v for v in vectors
        if v.entry_point == "calculate_interest" and "principal" in v.input_parameters
    ]
    
    # For decimals, "null" is represented as Decimal('0')
    assert any(v.input_parameters["principal"] == Decimal('0') for v in decimal_vectors)


def test_null_empty_tests_category(sample_logic_map):
    """Test that null/empty tests have correct category."""
    vectors = generate_null_empty_tests(sample_logic_map, {})
    
    assert all(v.category == TestVectorCategory.NULL_EMPTY for v in vectors)


# Test maximum length generation

def test_generate_max_length_tests_string(sample_logic_map):
    """Test max length generation for string parameters."""
    vectors = generate_max_length_tests(sample_logic_map, {})
    
    string_vectors = [
        v for v in vectors
        if v.entry_point == "process_string"
    ]
    
    # Should generate tests at max_length (255) and max_length-1 (254)
    string_lengths = [len(v.input_parameters["input_text"]) for v in string_vectors]
    
    assert 255 in string_lengths, "Should include max length"
    assert 254 in string_lengths, "Should include max-1 length"


def test_generate_max_length_tests_array():
    """Test max length generation for array parameters."""
    # Create a logic map with array parameter
    entry_point = EntryPoint(
        name="process_array",
        parameters=[
            Parameter(
                name="items",
                type=DataType.ARRAY,
                description="Array of items",
                max_length=100,
            ),
        ],
        return_type=DataType.INTEGER,
        description="Process array",
    )
    
    logic_map = LogicMap(
        artifact_id="test-array",
        artifact_version="1.0.0",
        extraction_timestamp="2024-01-01T00:00:00Z",
        entry_points=[entry_point],
        data_structures=[],
        control_flow=ControlFlowGraph(nodes=[], edges=[]),
        dependencies=[],
        side_effects=[],
        arithmetic_precision=PrecisionConfig(
            fixed_point_operations=[],
            floating_point_precision={},
            rounding_modes={},
        ),
    )
    
    vectors = generate_max_length_tests(logic_map, {})
    
    array_vectors = [v for v in vectors if v.entry_point == "process_array"]
    array_lengths = [len(v.input_parameters["items"]) for v in array_vectors]
    
    assert 100 in array_lengths, "Should include max length"
    assert 99 in array_lengths, "Should include max-1 length"


def test_max_length_tests_category(sample_logic_map):
    """Test that max length tests have correct category."""
    vectors = generate_max_length_tests(sample_logic_map, {})
    
    assert all(v.category == TestVectorCategory.MAX_LENGTH for v in vectors)


# Test branch coverage calculation

def test_calculate_expected_coverage_entry_points(sample_logic_map):
    """Test coverage calculation counts entry points correctly."""
    # Generate some test vectors
    vectors = generate_boundary_tests(sample_logic_map, {})
    
    coverage = calculate_expected_coverage(vectors, sample_logic_map)
    
    # Should cover all 3 entry points
    assert coverage.total_entry_points == 3
    assert coverage.entry_points_covered <= 3


def test_calculate_expected_coverage_with_diverse_categories(sample_logic_map):
    """Test coverage improves with diverse test categories."""
    # Generate tests from multiple categories
    boundary_vectors = generate_boundary_tests(sample_logic_map, {})
    date_vectors = generate_date_edge_tests(sample_logic_map, {})
    currency_vectors = generate_currency_tests(sample_logic_map, {})
    
    all_vectors = boundary_vectors + date_vectors + currency_vectors
    
    coverage = calculate_expected_coverage(all_vectors, sample_logic_map)
    
    # With diverse categories, coverage should be reasonable
    assert coverage.branch_coverage_percent > 0
    assert coverage.branch_coverage_percent <= 100


def test_calculate_expected_coverage_empty_vectors(sample_logic_map):
    """Test coverage calculation with no test vectors."""
    coverage = calculate_expected_coverage([], sample_logic_map)
    
    assert coverage.entry_points_covered == 0
    assert coverage.total_entry_points == 3
    assert coverage.branch_coverage_percent >= 0


def test_calculate_expected_coverage_no_branches():
    """Test coverage calculation when control flow has no branches."""
    logic_map = LogicMap(
        artifact_id="test-no-branches",
        artifact_version="1.0.0",
        extraction_timestamp="2024-01-01T00:00:00Z",
        entry_points=[
            EntryPoint(
                name="simple_function",
                parameters=[],
                return_type=DataType.INTEGER,
                description="Simple function",
            ),
        ],
        data_structures=[],
        control_flow=ControlFlowGraph(nodes=[], edges=[]),
        dependencies=[],
        side_effects=[],
        arithmetic_precision=PrecisionConfig(
            fixed_point_operations=[],
            floating_point_precision={},
            rounding_modes={},
        ),
    )
    
    vectors = generate_boundary_tests(logic_map, {})
    coverage = calculate_expected_coverage(vectors, logic_map)
    
    # With no branches, coverage should be 100%
    assert coverage.branch_coverage_percent == 100.0


# Integration tests

def test_all_test_generators_produce_valid_vectors(sample_logic_map):
    """Test that all generators produce valid test vectors."""
    generators = [
        generate_boundary_tests,
        generate_date_edge_tests,
        generate_currency_tests,
        generate_encoding_tests,
        generate_null_empty_tests,
        generate_max_length_tests,
    ]
    
    for generator in generators:
        vectors = generator(sample_logic_map, {})
        
        for vector in vectors:
            # Check required fields
            assert vector.vector_id is not None
            assert vector.generation_timestamp is not None
            assert vector.entry_point in [ep.name for ep in sample_logic_map.entry_points]
            assert isinstance(vector.input_parameters, dict)
            assert isinstance(vector.category, TestVectorCategory)


def test_test_vectors_cover_all_entry_points(sample_logic_map):
    """Test that generated vectors cover all entry points."""
    # Generate tests from all categories
    all_vectors = []
    all_vectors.extend(generate_boundary_tests(sample_logic_map, {}))
    all_vectors.extend(generate_date_edge_tests(sample_logic_map, {}))
    all_vectors.extend(generate_currency_tests(sample_logic_map, {}))
    all_vectors.extend(generate_encoding_tests(sample_logic_map, {}))
    all_vectors.extend(generate_null_empty_tests(sample_logic_map, {}))
    all_vectors.extend(generate_max_length_tests(sample_logic_map, {}))
    
    # Check that all entry points are covered
    covered_entry_points = set(v.entry_point for v in all_vectors)
    expected_entry_points = set(ep.name for ep in sample_logic_map.entry_points)
    
    assert covered_entry_points == expected_entry_points, \
        f"Not all entry points covered. Expected {expected_entry_points}, got {covered_entry_points}"


def test_hypothesis_strategy_creation(sample_logic_map):
    """Test that Hypothesis strategies can be created for all entry points."""
    for entry_point in sample_logic_map.entry_points:
        strategy = create_strategy_for_entry_point(entry_point, random_seed=42)
        
        # Generate a sample to verify strategy works
        sample = strategy.example()
        
        # Verify sample has correct parameters
        assert isinstance(sample, dict)
        assert set(sample.keys()) == set(p.name for p in entry_point.parameters)
