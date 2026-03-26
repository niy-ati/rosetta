"""Arithmetic precision preservation for faithful transpilation.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from rosetta_zero.models.logic_map import LogicMap, PrecisionConfig, FixedPointOp, RoundingMode
from rosetta_zero.utils.logging import logger


def preserve_arithmetic_precision(logic_map: LogicMap) -> str:
    """
    Extract and document arithmetic precision requirements from Logic Map.
    
    Args:
        logic_map: Logic Map containing arithmetic precision config
        
    Returns:
        Documentation string for arithmetic precision requirements
    """
    precision_config = logic_map.arithmetic_precision
    
    docs = []
    docs.append("# Arithmetic Precision Requirements\n")
    
    # Document fixed-point operations
    if precision_config.fixed_point_operations:
        docs.append("## Fixed-Point Arithmetic\n")
        docs.append("The following fixed-point operations must be preserved:\n")
        
        for op in precision_config.fixed_point_operations:
            docs.append(f"\n### {op.operation}")
            docs.append(f"- Precision: {op.precision} digits")
            docs.append(f"- Scale: {op.scale} decimal places")
            docs.append(f"- Description: {op.description}")
            docs.append(f"- Implementation: Use Python Decimal with precision={op.precision}, scale={op.scale}")
    
    # Document floating-point precision
    if precision_config.floating_point_precision:
        docs.append("\n## Floating-Point Precision\n")
        docs.append("The following floating-point precision must be maintained:\n")
        
        for operation, precision_bits in precision_config.floating_point_precision.items():
            docs.append(f"\n### {operation}")
            docs.append(f"- Precision: {precision_bits} bits")
            
            if precision_bits == 32:
                docs.append("- Implementation: Use numpy.float32")
            elif precision_bits == 64:
                docs.append("- Implementation: Use numpy.float64 or Python float")
            elif precision_bits == 128:
                docs.append("- Implementation: Use numpy.float128 or decimal.Decimal")
            else:
                docs.append(f"- Implementation: Custom precision handling required")
    
    # Document rounding modes
    if precision_config.rounding_modes:
        docs.append("\n## Rounding Modes\n")
        docs.append("The following rounding modes must be applied:\n")
        
        for operation, rounding_mode in precision_config.rounding_modes.items():
            docs.append(f"\n### {operation}")
            docs.append(f"- Rounding Mode: {rounding_mode.value}")
            docs.append(f"- Implementation: {_get_python_rounding_mode(rounding_mode)}")
    
    # Add implementation guidance
    docs.append("\n## Implementation Guidance\n")
    docs.append("""
For fixed-point arithmetic, use Python's decimal module:
```python
from decimal import Decimal, getcontext, ROUND_HALF_UP

# Set precision
getcontext().prec = <precision>

# Perform operations
result = Decimal('value1') + Decimal('value2')
result = result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

For floating-point precision, use numpy:
```python
import numpy as np

# Use specific precision
value = np.float32(1.23456789)
result = np.float32(value * 2.0)
```

CRITICAL: All arithmetic operations must match legacy system precision exactly.
Any deviation in precision will cause test failures.
""")
    
    precision_docs = "\n".join(docs)
    
    logger.info(
        "Arithmetic precision requirements documented",
        extra={
            "artifact_id": logic_map.artifact_id,
            "fixed_point_ops": len(precision_config.fixed_point_operations),
            "floating_point_ops": len(precision_config.floating_point_precision),
            "rounding_modes": len(precision_config.rounding_modes),
        }
    )
    
    return precision_docs


def _get_python_rounding_mode(rounding_mode: RoundingMode) -> str:
    """Get Python decimal rounding mode constant."""
    mode_map = {
        RoundingMode.ROUND_HALF_UP: "decimal.ROUND_HALF_UP",
        RoundingMode.ROUND_HALF_DOWN: "decimal.ROUND_HALF_DOWN",
        RoundingMode.ROUND_HALF_EVEN: "decimal.ROUND_HALF_EVEN",
        RoundingMode.ROUND_UP: "decimal.ROUND_UP",
        RoundingMode.ROUND_DOWN: "decimal.ROUND_DOWN",
        RoundingMode.TRUNCATE: "decimal.ROUND_DOWN",
    }
    return mode_map.get(rounding_mode, "decimal.ROUND_HALF_UP")


def generate_precision_test_code(precision_config: PrecisionConfig) -> str:
    """
    Generate test code to verify arithmetic precision preservation.
    
    Args:
        precision_config: Precision configuration from Logic Map
        
    Returns:
        Python test code
    """
    test_code = []
    test_code.append("# Arithmetic Precision Tests\n")
    test_code.append("from decimal import Decimal, getcontext\n")
    test_code.append("import numpy as np\n\n")
    
    # Generate tests for fixed-point operations
    for i, op in enumerate(precision_config.fixed_point_operations):
        test_code.append(f"def test_fixed_point_{i}():")
        test_code.append(f"    \"\"\"Test {op.operation} with precision={op.precision}, scale={op.scale}\"\"\"")
        test_code.append(f"    getcontext().prec = {op.precision}")
        test_code.append(f"    # Add test cases for {op.operation}")
        test_code.append(f"    pass\n\n")
    
    # Generate tests for floating-point precision
    for operation, precision_bits in precision_config.floating_point_precision.items():
        test_code.append(f"def test_float_precision_{operation.replace(' ', '_')}():")
        test_code.append(f"    \"\"\"Test {operation} with {precision_bits}-bit precision\"\"\"")
        test_code.append(f"    # Add test cases for {operation}")
        test_code.append(f"    pass\n\n")
    
    return "\n".join(test_code)
