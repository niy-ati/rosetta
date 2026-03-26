"""
Test vector generation using Hypothesis property-based testing.

This module implements adversarial test generation strategies for:
- Boundary values
- Date edge cases
- Currency overflow
- Character encoding edges
- Null/empty inputs
- Maximum length inputs
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Set

from hypothesis import strategies as st
from hypothesis import seed as hypothesis_seed

from rosetta_zero.models.logic_map import (
    LogicMap, EntryPoint, DataType, Parameter, ControlFlowGraph
)
from rosetta_zero.models.test_vector import TestVector, TestVectorCategory
from rosetta_zero.models.comparison import CoverageReport


def create_strategy_for_entry_point(
    entry_point: EntryPoint,
    random_seed: int
) -> st.SearchStrategy:
    """
    Create Hypothesis strategy for entry point parameters.
    
    Args:
        entry_point: Entry point definition from Logic Map
        random_seed: Random seed for reproducibility
        
    Returns:
        Hypothesis strategy that generates dictionaries of parameter values
    """
    # Set Hypothesis seed for reproducibility
    hypothesis_seed(random_seed)
    
    param_strategies = {}
    
    for param in entry_point.parameters:
        param_strategies[param.name] = _create_parameter_strategy(param)
    
    return st.fixed_dictionaries(param_strategies)


def _create_parameter_strategy(param: Parameter) -> st.SearchStrategy:
    """
    Create Hypothesis strategy for a single parameter.
    
    Args:
        param: Parameter definition
        
    Returns:
        Hypothesis strategy for the parameter type
    """
    if param.type == DataType.INTEGER:
        min_val = param.min_value if param.min_value is not None else -(2**31)
        max_val = param.max_value if param.max_value is not None else (2**31 - 1)
        return st.integers(min_value=min_val, max_value=max_val)
    
    elif param.type == DataType.STRING:
        max_len = param.max_length if param.max_length is not None else 1000
        return st.text(min_size=0, max_size=max_len)
    
    elif param.type == DataType.DATE:
        return st.dates(
            min_value=date(1900, 1, 1),
            max_value=date(2100, 12, 31)
        )
    
    elif param.type == DataType.DECIMAL:
        if param.decimal_places is not None:
            # Generate decimals with specific precision
            min_val = param.min_value if param.min_value is not None else -999999999
            max_val = param.max_value if param.max_value is not None else 999999999
            
            return st.decimals(
                min_value=Decimal(str(min_val)),
                max_value=Decimal(str(max_val)),
                places=param.decimal_places
            )
        else:
            return st.decimals(
                min_value=Decimal('-999999999.99'),
                max_value=Decimal('999999999.99')
            )
    
    elif param.type == DataType.BOOLEAN:
        return st.booleans()
    
    elif param.type == DataType.BINARY:
        max_len = param.max_length if param.max_length is not None else 1024
        return st.binary(min_size=0, max_size=max_len)
    
    elif param.type == DataType.ARRAY:
        # Generate arrays of integers by default
        max_len = param.max_length if param.max_length is not None else 100
        return st.lists(st.integers(), min_size=0, max_size=max_len)
    
    else:
        # Default to text for unknown types
        return st.text(max_size=100)


def generate_boundary_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for boundary values.
    
    Targets: MAX_INT, MIN_INT, zero, -1, 1 for integer parameters
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of boundary value test vectors
    """
    vectors = []
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            if param.type == DataType.INTEGER:
                # Define boundary values
                min_val = param.min_value if param.min_value is not None else -(2**31)
                max_val = param.max_value if param.max_value is not None else (2**31 - 1)
                
                boundary_values = [
                    min_val,
                    max_val,
                    0,
                    -1,
                    1,
                    min_val + 1,  # Just above minimum
                    max_val - 1,  # Just below maximum
                ]
                
                # Filter to valid range
                boundary_values = [
                    v for v in boundary_values
                    if min_val <= v <= max_val
                ]
                
                for value in boundary_values:
                    # Generate default values for other parameters
                    input_params = _generate_default_params(entry_point, param.name, value)
                    
                    vector = TestVector(
                        vector_id=str(uuid.uuid4()),
                        generation_timestamp=datetime.utcnow().isoformat(),
                        random_seed=0,  # Deterministic for boundary tests
                        entry_point=entry_point.name,
                        input_parameters=input_params,
                        expected_coverage=set(),  # Will be calculated later
                        category=TestVectorCategory.BOUNDARY
                    )
                    vectors.append(vector)
            
            elif param.type == DataType.DECIMAL:
                # Boundary values for decimals
                min_val = param.min_value if param.min_value is not None else Decimal('-999999999.99')
                max_val = param.max_value if param.max_value is not None else Decimal('999999999.99')
                
                boundary_values = [
                    min_val,
                    max_val,
                    Decimal('0'),
                    Decimal('0.01'),
                    Decimal('-0.01'),
                ]
                
                for value in boundary_values:
                    if min_val <= value <= max_val:
                        input_params = _generate_default_params(entry_point, param.name, value)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.BOUNDARY
                        )
                        vectors.append(vector)
    
    return vectors


def generate_date_edge_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for date edge cases.
    
    Targets: Leap years, century boundaries, Y2K scenarios
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of date edge case test vectors
    """
    vectors = []
    
    # Define date edge cases
    edge_dates = [
        date(1900, 2, 28),  # Century boundary (not a leap year)
        date(2000, 2, 29),  # Century boundary (leap year)
        date(2000, 1, 1),   # Y2K
        date(1999, 12, 31), # Day before Y2K
        date(2004, 2, 29),  # Leap year
        date(2100, 2, 28),  # Future century boundary (not a leap year)
        date(2024, 2, 29),  # Recent leap year
        date(1900, 1, 1),   # Start of range
        date(2100, 12, 31), # End of range
    ]
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            if param.type == DataType.DATE:
                for edge_date in edge_dates:
                    input_params = _generate_default_params(entry_point, param.name, edge_date)
                    
                    vector = TestVector(
                        vector_id=str(uuid.uuid4()),
                        generation_timestamp=datetime.utcnow().isoformat(),
                        random_seed=0,
                        entry_point=entry_point.name,
                        input_parameters=input_params,
                        expected_coverage=set(),
                        category=TestVectorCategory.DATE_EDGE
                    )
                    vectors.append(vector)
    
    return vectors


def generate_currency_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for currency overflow scenarios.
    
    Targets: Maximum precision, rounding boundaries, overflow
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of currency overflow test vectors
    """
    vectors = []
    
    # Define currency edge cases
    currency_values = [
        Decimal('999999999.99'),   # Maximum typical currency value
        Decimal('0.01'),            # Minimum positive currency
        Decimal('0.001'),           # Sub-cent (rounding test)
        Decimal('0.005'),           # Rounding boundary
        Decimal('0.995'),           # Rounding boundary
        Decimal('999999999.995'),   # Large value with rounding
        Decimal('-999999999.99'),   # Maximum negative
        Decimal('-0.01'),           # Minimum negative
    ]
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            if param.type == DataType.DECIMAL:
                for value in currency_values:
                    # Check if value is within parameter bounds
                    min_val = param.min_value if param.min_value is not None else Decimal('-999999999.99')
                    max_val = param.max_value if param.max_value is not None else Decimal('999999999.99')
                    
                    if min_val <= value <= max_val:
                        input_params = _generate_default_params(entry_point, param.name, value)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.CURRENCY
                        )
                        vectors.append(vector)
    
    return vectors


def generate_encoding_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for character encoding edge cases.
    
    Targets: EBCDIC mappings, special characters, encoding boundaries
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of encoding edge case test vectors
    """
    vectors = []
    
    # Define encoding edge cases
    encoding_strings = [
        "",                          # Empty string
        " ",                         # Single space
        "\t",                        # Tab
        "\n",                        # Newline
        "\r\n",                      # Windows newline
        "ABC",                       # Simple ASCII
        "abc123",                    # Alphanumeric
        "!@#$%^&*()",               # Special characters
        "ÄÖÜäöü",                   # Extended ASCII
        "€£¥",                       # Currency symbols
        "\x00",                      # Null character
        "\x7F",                      # DEL character
        "A" * 255,                   # Long string
    ]
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            if param.type == DataType.STRING:
                max_len = param.max_length if param.max_length is not None else 1000
                
                for test_string in encoding_strings:
                    # Truncate if exceeds max length
                    if len(test_string) <= max_len:
                        input_params = _generate_default_params(entry_point, param.name, test_string)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.ENCODING
                        )
                        vectors.append(vector)
    
    return vectors


def generate_null_empty_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for null and empty inputs.
    
    Targets: Null pointers, empty strings, zero-length arrays
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of null/empty test vectors
    """
    vectors = []
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            null_value = None
            
            if param.type == DataType.STRING:
                null_value = ""
            elif param.type == DataType.ARRAY:
                null_value = []
            elif param.type == DataType.BINARY:
                null_value = b""
            elif param.type == DataType.INTEGER:
                null_value = 0
            elif param.type == DataType.DECIMAL:
                null_value = Decimal('0')
            
            if null_value is not None:
                input_params = _generate_default_params(entry_point, param.name, null_value)
                
                vector = TestVector(
                    vector_id=str(uuid.uuid4()),
                    generation_timestamp=datetime.utcnow().isoformat(),
                    random_seed=0,
                    entry_point=entry_point.name,
                    input_parameters=input_params,
                    expected_coverage=set(),
                    category=TestVectorCategory.NULL_EMPTY
                )
                vectors.append(vector)
    
    return vectors


def generate_max_length_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy]
) -> List[TestVector]:
    """
    Generate test vectors for maximum length inputs.
    
    Targets: Buffer boundaries, string length limits, maximum array sizes
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        
    Returns:
        List of maximum length test vectors
    """
    vectors = []
    
    for entry_point in logic_map.entry_points:
        for param in entry_point.parameters:
            max_value = None
            
            if param.type == DataType.STRING and param.max_length:
                # Test at max length, max-1, and max+1 (if possible)
                for length in [param.max_length - 1, param.max_length]:
                    if length >= 0:
                        max_value = "A" * length
                        input_params = _generate_default_params(entry_point, param.name, max_value)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.MAX_LENGTH
                        )
                        vectors.append(vector)
            
            elif param.type == DataType.ARRAY and param.max_length:
                # Test at max length
                for length in [param.max_length - 1, param.max_length]:
                    if length >= 0:
                        max_value = [0] * length
                        input_params = _generate_default_params(entry_point, param.name, max_value)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.MAX_LENGTH
                        )
                        vectors.append(vector)
            
            elif param.type == DataType.BINARY and param.max_length:
                # Test at max length
                for length in [param.max_length - 1, param.max_length]:
                    if length >= 0:
                        max_value = b"\x00" * length
                        input_params = _generate_default_params(entry_point, param.name, max_value)
                        
                        vector = TestVector(
                            vector_id=str(uuid.uuid4()),
                            generation_timestamp=datetime.utcnow().isoformat(),
                            random_seed=0,
                            entry_point=entry_point.name,
                            input_parameters=input_params,
                            expected_coverage=set(),
                            category=TestVectorCategory.MAX_LENGTH
                        )
                        vectors.append(vector)
    
    return vectors


def generate_random_tests(
    logic_map: LogicMap,
    strategies: Dict[str, st.SearchStrategy],
    count: int,
    random_seed: int
) -> List[TestVector]:
    """
    Generate random test vectors using Hypothesis strategies.
    
    Args:
        logic_map: Logic Map defining system behavior
        strategies: Hypothesis strategies for each entry point
        count: Number of random tests to generate
        random_seed: Random seed for reproducibility
        
    Returns:
        List of random test vectors
    """
    vectors = []
    hypothesis_seed(random_seed)
    
    # Distribute tests across entry points
    tests_per_entry_point = count // len(logic_map.entry_points)
    remaining = count % len(logic_map.entry_points)
    
    for i, entry_point in enumerate(logic_map.entry_points):
        entry_point_count = tests_per_entry_point
        if i < remaining:
            entry_point_count += 1
        
        strategy = strategies[entry_point.name]
        
        # Generate test vectors using Hypothesis
        for _ in range(entry_point_count):
            input_params = strategy.example()
            
            vector = TestVector(
                vector_id=str(uuid.uuid4()),
                generation_timestamp=datetime.utcnow().isoformat(),
                random_seed=random_seed,
                entry_point=entry_point.name,
                input_parameters=input_params,
                expected_coverage=set(),
                category=TestVectorCategory.RANDOM
            )
            vectors.append(vector)
    
    return vectors


def calculate_expected_coverage(
    test_vectors: List[TestVector],
    logic_map: LogicMap
) -> CoverageReport:
    """
    Calculate expected branch coverage from test vectors.
    
    Args:
        test_vectors: List of test vectors
        logic_map: Logic Map with control flow graph
        
    Returns:
        CoverageReport with coverage metrics
    """
    # Count unique entry points covered
    covered_entry_points = set(v.entry_point for v in test_vectors)
    total_entry_points = len(logic_map.entry_points)
    
    # Estimate branch coverage based on test vector diversity
    # This is a simplified estimation - actual coverage would require execution
    total_branches = len(logic_map.control_flow.edges)
    
    if total_branches == 0:
        branch_coverage = 100.0
        uncovered_branches = []
    else:
        # Estimate coverage based on number of test vectors and categories
        category_counts = {}
        for vector in test_vectors:
            category_counts[vector.category] = category_counts.get(vector.category, 0) + 1
        
        # More diverse categories = better coverage
        diversity_factor = len(category_counts) / len(TestVectorCategory)
        
        # More test vectors = better coverage (with diminishing returns)
        volume_factor = min(1.0, len(test_vectors) / 10000)
        
        # Combine factors for estimated coverage
        branch_coverage = min(100.0, (diversity_factor * 0.5 + volume_factor * 0.5) * 100)
        
        # Identify potentially uncovered branches (simplified)
        covered_count = int((branch_coverage / 100.0) * total_branches)
        uncovered_count = total_branches - covered_count
        uncovered_branches = [
            f"branch_{i}" for i in range(uncovered_count)
        ]
    
    return CoverageReport(
        branch_coverage_percent=branch_coverage,
        entry_points_covered=len(covered_entry_points),
        total_entry_points=total_entry_points,
        uncovered_branches=uncovered_branches
    )


def generate_coverage_tests(
    logic_map: LogicMap,
    uncovered_branches: List[str],
    strategies: Dict[str, st.SearchStrategy],
    random_seed: int
) -> List[TestVector]:
    """
    Generate additional test vectors targeting uncovered branches.
    
    Args:
        logic_map: Logic Map defining system behavior
        uncovered_branches: List of branch IDs that are not covered
        strategies: Hypothesis strategies for each entry point
        random_seed: Random seed for reproducibility
        
    Returns:
        List of test vectors targeting uncovered branches
    """
    vectors = []
    hypothesis_seed(random_seed + 1)  # Different seed for coverage tests
    
    # Generate additional random tests to improve coverage
    # In a real implementation, this would use control flow analysis
    # to generate targeted tests for specific branches
    additional_count = min(len(uncovered_branches) * 10, 100000)
    
    vectors = generate_random_tests(
        logic_map,
        strategies,
        additional_count,
        random_seed + 1
    )
    
    return vectors


def _generate_default_params(
    entry_point: EntryPoint,
    target_param_name: str,
    target_value: Any
) -> Dict[str, Any]:
    """
    Generate default parameter values with one parameter set to a specific value.
    
    Args:
        entry_point: Entry point definition
        target_param_name: Name of parameter to set to specific value
        target_value: Value to set for target parameter
        
    Returns:
        Dictionary of parameter names to values
    """
    params = {}
    
    for param in entry_point.parameters:
        if param.name == target_param_name:
            params[param.name] = target_value
        else:
            # Generate safe default values
            if param.type == DataType.INTEGER:
                params[param.name] = 0
            elif param.type == DataType.STRING:
                params[param.name] = ""
            elif param.type == DataType.DATE:
                params[param.name] = date(2000, 1, 1)
            elif param.type == DataType.DECIMAL:
                params[param.name] = Decimal('0')
            elif param.type == DataType.BOOLEAN:
                params[param.name] = False
            elif param.type == DataType.BINARY:
                params[param.name] = b""
            elif param.type == DataType.ARRAY:
                params[param.name] = []
            else:
                params[param.name] = None
    
    return params
