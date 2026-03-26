"""
Output Comparator Lambda Function.

Compares legacy and modern execution outputs byte-by-byte.
Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 16.1, 16.2
"""

import hashlib
from datetime import datetime
from typing import List, Optional

from aws_lambda_powertools import Logger, Tracer

from rosetta_zero.models import (
    ExecutionResult,
    ComparisonResult,
    DifferenceDetails,
    ByteDiff,
    SideEffectDiff,
)
from rosetta_zero.utils import logger, tracer


@tracer.capture_method
def compare_outputs(
    legacy_result: ExecutionResult,
    modern_result: ExecutionResult
) -> ComparisonResult:
    """
    Compare outputs byte-by-byte with detailed diff generation.
    
    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 16.1, 16.2
    
    Compares:
    - Return values (byte-by-byte)
    - stdout content (byte-by-byte)
    - stderr content (byte-by-byte)
    - Side effects
    
    Generates SHA-256 hash of comparison result for integrity.
    
    Args:
        legacy_result: Execution result from legacy binary
        modern_result: Execution result from modern Lambda
        
    Returns:
        ComparisonResult with match status and detailed diffs
    """
    logger.info(
        f"Comparing outputs for test vector: {legacy_result.test_vector_id}",
        extra={
            'legacy_return': legacy_result.return_value,
            'modern_return': modern_result.return_value
        }
    )
    
    # Initialize comparison result
    comparison = ComparisonResult(
        test_vector_id=legacy_result.test_vector_id,
        comparison_timestamp=datetime.utcnow(),
        match=True,
        return_value_match=True,
        stdout_match=True,
        stderr_match=True,
        side_effects_match=True,
        differences=None,
        result_hash=""
    )
    
    differences = DifferenceDetails(
        return_value_diff=None,
        stdout_diff=None,
        stderr_diff=None,
        side_effect_diffs=[]
    )
    
    # Compare return values (Requirement 13.1)
    if legacy_result.return_value != modern_result.return_value:
        comparison.return_value_match = False
        comparison.match = False
        
        # Generate byte diff for return values
        legacy_bytes = str(legacy_result.return_value).encode('utf-8')
        modern_bytes = str(modern_result.return_value).encode('utf-8')
        differences.return_value_diff = generate_byte_diff(legacy_bytes, modern_bytes)
        
        logger.warning(
            "Return value mismatch",
            extra={
                'test_vector_id': legacy_result.test_vector_id,
                'legacy': legacy_result.return_value,
                'modern': modern_result.return_value
            }
        )
    
    # Compare stdout (Requirement 13.2)
    if legacy_result.stdout != modern_result.stdout:
        comparison.stdout_match = False
        comparison.match = False
        differences.stdout_diff = generate_byte_diff(
            legacy_result.stdout,
            modern_result.stdout
        )
        
        logger.warning(
            "stdout mismatch",
            extra={
                'test_vector_id': legacy_result.test_vector_id,
                'legacy_size': len(legacy_result.stdout),
                'modern_size': len(modern_result.stdout)
            }
        )
    
    # Compare stderr (Requirement 13.3)
    if legacy_result.stderr != modern_result.stderr:
        comparison.stderr_match = False
        comparison.match = False
        differences.stderr_diff = generate_byte_diff(
            legacy_result.stderr,
            modern_result.stderr
        )
        
        logger.warning(
            "stderr mismatch",
            extra={
                'test_vector_id': legacy_result.test_vector_id,
                'legacy_size': len(legacy_result.stderr),
                'modern_size': len(modern_result.stderr)
            }
        )
    
    # Compare side effects (Requirement 13.4)
    side_effect_diffs = compare_side_effects(
        legacy_result.side_effects,
        modern_result.side_effects
    )
    
    if side_effect_diffs:
        comparison.side_effects_match = False
        comparison.match = False
        differences.side_effect_diffs = side_effect_diffs
        
        logger.warning(
            "Side effects mismatch",
            extra={
                'test_vector_id': legacy_result.test_vector_id,
                'diff_count': len(side_effect_diffs)
            }
        )
    
    # Store differences if any mismatch (Requirement 13.6)
    if not comparison.match:
        comparison.differences = differences
    
    # Compute SHA-256 hash of comparison result (Requirements 16.1, 16.2)
    comparison.result_hash = compute_comparison_hash(comparison)
    
    logger.info(
        f"Comparison completed",
        extra={
            'test_vector_id': legacy_result.test_vector_id,
            'match': comparison.match,
            'result_hash': comparison.result_hash
        }
    )
    
    return comparison


@tracer.capture_method
def generate_byte_diff(
    legacy_bytes: bytes,
    modern_bytes: bytes,
    context_size: int = 20
) -> ByteDiff:
    """
    Generate byte-level diff with context.
    
    Requirement 13.5: Include byte-level diffs for all differences
    
    Args:
        legacy_bytes: Bytes from legacy execution
        modern_bytes: Bytes from modern execution
        context_size: Number of bytes to include before/after diff
        
    Returns:
        ByteDiff with offset, differing bytes, and context
    """
    # Find first differing byte
    min_len = min(len(legacy_bytes), len(modern_bytes))
    offset = 0
    
    for i in range(min_len):
        if legacy_bytes[i] != modern_bytes[i]:
            offset = i
            break
    else:
        # One is a prefix of the other
        offset = min_len
    
    # Extract context
    context_start = max(0, offset - context_size)
    context_end = min(max(len(legacy_bytes), len(modern_bytes)), offset + context_size)
    
    # Extract differing bytes
    legacy_diff_byte = legacy_bytes[offset:offset+1] if offset < len(legacy_bytes) else b''
    modern_diff_byte = modern_bytes[offset:offset+1] if offset < len(modern_bytes) else b''
    
    # Extract context
    context_before = legacy_bytes[context_start:offset]
    context_after = legacy_bytes[offset+1:context_end] if offset < len(legacy_bytes) else b''
    
    byte_diff = ByteDiff(
        offset=offset,
        legacy_bytes=legacy_diff_byte,
        modern_bytes=modern_diff_byte,
        context_before=context_before,
        context_after=context_after
    )
    
    logger.debug(
        f"Generated byte diff at offset {offset}",
        extra={
            'offset': offset,
            'legacy_byte': legacy_diff_byte.hex() if legacy_diff_byte else 'EOF',
            'modern_byte': modern_diff_byte.hex() if modern_diff_byte else 'EOF'
        }
    )
    
    return byte_diff


@tracer.capture_method
def compare_side_effects(
    legacy_side_effects: List,
    modern_side_effects: List
) -> List[SideEffectDiff]:
    """
    Compare side effects between legacy and modern executions.
    
    Requirement 13.4: Compare all side effects
    
    Args:
        legacy_side_effects: Side effects from legacy execution
        modern_side_effects: Side effects from modern execution
        
    Returns:
        List of SideEffectDiff objects for any differences
    """
    diffs = []
    
    # Compare counts
    if len(legacy_side_effects) != len(modern_side_effects):
        logger.warning(
            "Side effect count mismatch",
            extra={
                'legacy_count': len(legacy_side_effects),
                'modern_count': len(modern_side_effects)
            }
        )
    
    # Create sets for comparison
    legacy_set = {_side_effect_key(se) for se in legacy_side_effects}
    modern_set = {_side_effect_key(se) for se in modern_side_effects}
    
    # Find side effects only in legacy
    only_in_legacy = legacy_set - modern_set
    for key in only_in_legacy:
        diffs.append(SideEffectDiff(
            effect_type=key[0],
            operation=key[1],
            legacy_data=None,  # Could extract actual data if needed
            modern_data=None,
            description="Side effect present in legacy but not in modern"
        ))
    
    # Find side effects only in modern
    only_in_modern = modern_set - legacy_set
    for key in only_in_modern:
        diffs.append(SideEffectDiff(
            effect_type=key[0],
            operation=key[1],
            legacy_data=None,
            modern_data=None,  # Could extract actual data if needed
            description="Side effect present in modern but not in legacy"
        ))
    
    # Compare data for common side effects
    common = legacy_set & modern_set
    for key in common:
        legacy_se = _find_side_effect(legacy_side_effects, key)
        modern_se = _find_side_effect(modern_side_effects, key)
        
        if legacy_se and modern_se:
            # Compare data
            legacy_data = getattr(legacy_se, 'data', b'')
            modern_data = getattr(modern_se, 'data', b'')
            
            if legacy_data != modern_data:
                data_diff = generate_byte_diff(legacy_data, modern_data)
                diffs.append(SideEffectDiff(
                    effect_type=key[0],
                    operation=key[1],
                    legacy_data=legacy_data,
                    modern_data=modern_data,
                    description=f"Side effect data differs at offset {data_diff.offset}"
                ))
    
    return diffs


def _side_effect_key(side_effect) -> tuple:
    """Generate key for side effect comparison."""
    effect_type = getattr(side_effect, 'effect_type', 'UNKNOWN')
    operation = getattr(side_effect, 'operation', '')
    return (effect_type, operation)


def _find_side_effect(side_effects: List, key: tuple):
    """Find side effect by key."""
    for se in side_effects:
        if _side_effect_key(se) == key:
            return se
    return None


@tracer.capture_method
def compute_comparison_hash(comparison: ComparisonResult) -> str:
    """
    Compute SHA-256 hash of comparison result.
    
    Requirements 16.1, 16.2: Generate SHA-256 hash for cryptographic integrity
    
    Args:
        comparison: Comparison result
        
    Returns:
        SHA-256 hash as hex string
    """
    # Create canonical representation for hashing
    hash_input = f"{comparison.test_vector_id}|{comparison.match}|"
    hash_input += f"{comparison.return_value_match}|{comparison.stdout_match}|"
    hash_input += f"{comparison.stderr_match}|{comparison.side_effects_match}|"
    hash_input += f"{comparison.comparison_timestamp.isoformat()}"
    
    # Include difference details if present
    if comparison.differences:
        if comparison.differences.return_value_diff:
            diff = comparison.differences.return_value_diff
            hash_input += f"|return_diff:{diff.offset}:{diff.legacy_bytes.hex()}:{diff.modern_bytes.hex()}"
        
        if comparison.differences.stdout_diff:
            diff = comparison.differences.stdout_diff
            hash_input += f"|stdout_diff:{diff.offset}"
        
        if comparison.differences.stderr_diff:
            diff = comparison.differences.stderr_diff
            hash_input += f"|stderr_diff:{diff.offset}"
        
        for se_diff in comparison.differences.side_effect_diffs:
            hash_input += f"|se_diff:{se_diff.effect_type}:{se_diff.operation}"
    
    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(hash_input.encode('utf-8')).digest()
    hash_hex = hash_bytes.hex()
    
    logger.debug(
        f"Computed comparison hash",
        extra={
            'test_vector_id': comparison.test_vector_id,
            'hash': hash_hex
        }
    )
    
    return hash_hex
