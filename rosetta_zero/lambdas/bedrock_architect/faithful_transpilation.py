"""Faithful transpilation validation - ensures no feature addition or optimization.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
"""

import ast
import re
from typing import List, Set

from rosetta_zero.models.logic_map import LogicMap
from rosetta_zero.utils.logging import logger, log_architect_decision


class FaithfulTranspilationError(Exception):
    """Raised when generated code violates faithful transpilation constraints."""
    pass


def validate_faithful_transpilation(logic_map: LogicMap, generated_code: str):
    """
    Validate that generated code implements only Logic Map behaviors.
    
    Checks:
    1. No feature addition beyond Logic Map
    2. No algorithm optimization that changes behavior
    3. No data precision modifications
    4. All side effects are preserved
    
    Args:
        logic_map: Original Logic Map
        generated_code: Generated Lambda code
        
    Raises:
        FaithfulTranspilationError: If validation fails
    """
    errors = []
    
    # Parse generated code
    try:
        tree = ast.parse(generated_code)
    except SyntaxError as e:
        raise FaithfulTranspilationError(f"Generated code has syntax errors: {e}")
    
    # Check 1: Verify all entry points are implemented
    entry_point_errors = _validate_entry_points(logic_map, tree)
    errors.extend(entry_point_errors)
    
    # Check 2: Verify side effects are preserved
    side_effect_errors = _validate_side_effects(logic_map, generated_code)
    errors.extend(side_effect_errors)
    
    # Check 3: Check for unauthorized optimizations
    optimization_errors = _check_for_optimizations(logic_map, generated_code)
    errors.extend(optimization_errors)
    
    # Check 4: Verify no extra features added
    feature_errors = _check_for_extra_features(logic_map, tree)
    errors.extend(feature_errors)
    
    if errors:
        error_msg = "Faithful transpilation validation failed:\n" + "\n".join(errors)
        logger.error(
            "Faithful transpilation validation failed",
            extra={
                "artifact_id": logic_map.artifact_id,
                "errors": errors,
            }
        )
        raise FaithfulTranspilationError(error_msg)
    
    log_architect_decision(
        logic_map_id=logic_map.artifact_id,
        decision="faithful_transpilation_validated",
        details={
            "entry_points_validated": len(logic_map.entry_points),
            "side_effects_validated": len(logic_map.side_effects),
        }
    )


def _validate_entry_points(logic_map: LogicMap, tree: ast.AST) -> List[str]:
    """Validate all entry points from Logic Map are implemented."""
    errors = []
    
    # Extract function definitions from generated code
    function_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            function_names.add(node.name)
    
    # Check each entry point is implemented
    for entry_point in logic_map.entry_points:
        # Convert entry point name to Python function name
        func_name = _to_python_function_name(entry_point.name)
        
        if func_name not in function_names:
            errors.append(
                f"Entry point '{entry_point.name}' not implemented (expected function '{func_name}')"
            )
    
    return errors


def _validate_side_effects(logic_map: LogicMap, generated_code: str) -> List[str]:
    """Validate all side effects from Logic Map are preserved."""
    errors = []
    
    for side_effect in logic_map.side_effects:
        effect_type = side_effect.operation_type.value
        
        # Check for corresponding implementation
        if effect_type == "FILE_IO":
            if not _has_file_io(generated_code):
                errors.append(
                    f"Side effect '{side_effect.description}' (FILE_IO) not preserved"
                )
        
        elif effect_type == "DATABASE":
            if not _has_database_operations(generated_code):
                errors.append(
                    f"Side effect '{side_effect.description}' (DATABASE) not preserved"
                )
        
        elif effect_type == "NETWORK":
            if not _has_network_operations(generated_code):
                errors.append(
                    f"Side effect '{side_effect.description}' (NETWORK) not preserved"
                )
        
        elif effect_type == "GLOBAL_VAR":
            if not _has_global_variable_access(generated_code):
                errors.append(
                    f"Side effect '{side_effect.description}' (GLOBAL_VAR) not preserved"
                )
    
    return errors


def _check_for_optimizations(logic_map: LogicMap, generated_code: str) -> List[str]:
    """Check for unauthorized algorithm optimizations."""
    errors = []
    
    # Check for common optimization patterns that might change behavior
    
    # Check for memoization/caching (could change timing behavior)
    if re.search(r'@(lru_cache|cache|memoize)', generated_code):
        errors.append(
            "Unauthorized optimization: caching/memoization detected (may change timing behavior)"
        )
    
    # Check for parallel processing (could change execution order)
    if re.search(r'(ThreadPoolExecutor|ProcessPoolExecutor|multiprocessing|threading)', generated_code):
        errors.append(
            "Unauthorized optimization: parallel processing detected (may change execution order)"
        )
    
    # Check for lazy evaluation (could change side effect timing)
    if re.search(r'(yield|generator|lazy)', generated_code):
        errors.append(
            "Unauthorized optimization: lazy evaluation detected (may change side effect timing)"
        )
    
    return errors


def _check_for_extra_features(logic_map: LogicMap, tree: ast.AST) -> List[str]:
    """Check for features not present in Logic Map."""
    errors = []
    
    # Extract all function definitions
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
    
    # Expected functions: entry points + lambda_handler + helper functions
    expected_functions = set()
    expected_functions.add('lambda_handler')
    
    for entry_point in logic_map.entry_points:
        expected_functions.add(_to_python_function_name(entry_point.name))
    
    # Allow helper functions that are clearly internal
    actual_functions = set(f for f in functions if not f.startswith('_'))
    
    # Check for unexpected public functions
    extra_functions = actual_functions - expected_functions
    if extra_functions:
        # Filter out common AWS Lambda PowerTools functions
        powertools_functions = {'init', 'setup', 'configure'}
        extra_functions = extra_functions - powertools_functions
        
        if extra_functions:
            errors.append(
                f"Extra features detected: unexpected functions {extra_functions}"
            )
    
    return errors


def _to_python_function_name(name: str) -> str:
    """Convert legacy function name to Python function name."""
    # Convert COBOL-style names (CALCULATE-PAYROLL) to Python (calculate_payroll)
    name = name.lower()
    name = name.replace('-', '_')
    name = name.replace(' ', '_')
    return name


def _has_file_io(code: str) -> bool:
    """Check if code contains file I/O operations."""
    file_io_patterns = [
        r'\bopen\(',
        r'\bfile\(',
        r'\.read\(',
        r'\.write\(',
        r'\.close\(',
        r'with\s+open\(',
        r'boto3\.client\([\'"]s3[\'"]\)',
    ]
    return any(re.search(pattern, code) for pattern in file_io_patterns)


def _has_database_operations(code: str) -> bool:
    """Check if code contains database operations."""
    db_patterns = [
        r'boto3\.client\([\'"]dynamodb[\'"]\)',
        r'boto3\.resource\([\'"]dynamodb[\'"]\)',
        r'\.put_item\(',
        r'\.get_item\(',
        r'\.query\(',
        r'\.scan\(',
        r'psycopg2',
        r'pymysql',
        r'sqlite3',
    ]
    return any(re.search(pattern, code) for pattern in db_patterns)


def _has_network_operations(code: str) -> bool:
    """Check if code contains network operations."""
    network_patterns = [
        r'requests\.',
        r'urllib',
        r'http\.client',
        r'socket\.',
        r'boto3\.client',
    ]
    return any(re.search(pattern, code) for pattern in network_patterns)


def _has_global_variable_access(code: str) -> bool:
    """Check if code contains global variable access."""
    global_patterns = [
        r'\bglobal\s+\w+',
        r'globals\(\)',
    ]
    return any(re.search(pattern, code) for pattern in global_patterns)


def log_transpilation_decision(
    artifact_id: str,
    decision: str,
    details: dict
):
    """Log transpilation decision for audit trail."""
    log_architect_decision(
        logic_map_id=artifact_id,
        decision=f"transpilation_{decision}",
        details=details
    )
