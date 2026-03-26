"""Timing behavior preservation for legacy systems.

Requirements: 22.1, 22.2
"""

from typing import List
from rosetta_zero.models.logic_map import LogicMap, SideEffect, TimingRequirement
from rosetta_zero.utils.logging import logger


def preserve_timing_behavior(logic_map: LogicMap) -> str:
    """
    Document timing requirements from Logic Map.
    
    Args:
        logic_map: Logic Map containing timing requirements
        
    Returns:
        Documentation string for timing behavior requirements
    """
    docs = []
    docs.append("# Timing Behavior Requirements\n")
    
    # Find side effects with timing requirements
    timing_side_effects = [
        se for se in logic_map.side_effects
        if se.timing_requirements is not None
    ]
    
    if not timing_side_effects:
        docs.append("No explicit timing requirements found in Logic Map.\n")
        logger.info(
            "No timing requirements to preserve",
            extra={"artifact_id": logic_map.artifact_id}
        )
        return "\n".join(docs)
    
    docs.append("The following timing behaviors must be preserved:\n")
    
    for se in timing_side_effects:
        timing = se.timing_requirements
        docs.append(f"\n## {se.description}")
        docs.append(f"- Operation Type: {se.operation_type.value}")
        docs.append(f"- Scope: {se.scope}")
        
        if timing.min_duration_ms is not None:
            docs.append(f"- Minimum Duration: {timing.min_duration_ms}ms")
        
        if timing.max_duration_ms is not None:
            docs.append(f"- Maximum Duration: {timing.max_duration_ms}ms")
        
        if timing.delay_ms is not None:
            docs.append(f"- Required Delay: {timing.delay_ms}ms")
            docs.append(f"- Implementation: Add `time.sleep({timing.delay_ms / 1000})` after operation")
        
        if timing.description:
            docs.append(f"- Notes: {timing.description}")
    
    # Add implementation guidance
    docs.append("\n## Implementation Guidance\n")
    docs.append("""
For timing-dependent logic:

1. **Deliberate Delays**: If the legacy system includes intentional delays (e.g., for hardware synchronization),
   implement equivalent delays using `time.sleep()`:
   ```python
   import time
   
   # Perform operation
   result = perform_operation()
   
   # Add required delay
   time.sleep(delay_seconds)
   ```

2. **Timing Constraints**: If operations must complete within specific time windows,
   document these constraints in code comments and implement timeout handling:
   ```python
   import signal
   
   def timeout_handler(signum, frame):
       raise TimeoutError("Operation exceeded maximum duration")
   
   signal.signal(signal.SIGALRM, timeout_handler)
   signal.alarm(max_duration_seconds)
   try:
       result = perform_operation()
   finally:
       signal.alarm(0)  # Cancel alarm
   ```

3. **Latency Simulation**: If the legacy system has specific latency characteristics,
   simulate equivalent latency in the modern implementation to maintain behavioral parity.

CRITICAL: Timing behavior affects test results. Any deviation in timing may cause
discrepancies in parallel testing.
""")
    
    timing_docs = "\n".join(docs)
    
    logger.info(
        "Timing requirements documented",
        extra={
            "artifact_id": logic_map.artifact_id,
            "timing_side_effects": len(timing_side_effects),
        }
    )
    
    return timing_docs


def extract_timing_requirements(logic_map: LogicMap) -> List[TimingRequirement]:
    """
    Extract all timing requirements from Logic Map.
    
    Args:
        logic_map: Logic Map to extract timing from
        
    Returns:
        List of timing requirements
    """
    timing_reqs = []
    
    for side_effect in logic_map.side_effects:
        if side_effect.timing_requirements:
            timing_reqs.append(side_effect.timing_requirements)
    
    return timing_reqs


def generate_timing_test_code(logic_map: LogicMap) -> str:
    """
    Generate test code to verify timing behavior preservation.
    
    Args:
        logic_map: Logic Map with timing requirements
        
    Returns:
        Python test code
    """
    timing_side_effects = [
        se for se in logic_map.side_effects
        if se.timing_requirements is not None
    ]
    
    if not timing_side_effects:
        return "# No timing tests required\n"
    
    test_code = []
    test_code.append("# Timing Behavior Tests\n")
    test_code.append("import time\n")
    test_code.append("import pytest\n\n")
    
    for i, se in enumerate(timing_side_effects):
        timing = se.timing_requirements
        test_name = se.description.lower().replace(' ', '_')
        
        test_code.append(f"def test_timing_{test_name}_{i}():")
        test_code.append(f"    \"\"\"Test timing for {se.description}\"\"\"")
        test_code.append(f"    start_time = time.time()")
        test_code.append(f"    ")
        test_code.append(f"    # Perform operation")
        test_code.append(f"    # TODO: Call the actual function")
        test_code.append(f"    ")
        test_code.append(f"    end_time = time.time()")
        test_code.append(f"    duration_ms = (end_time - start_time) * 1000")
        test_code.append(f"    ")
        
        if timing.min_duration_ms is not None:
            test_code.append(f"    assert duration_ms >= {timing.min_duration_ms}, \\")
            test_code.append(f"        f\"Operation too fast: {{duration_ms}}ms < {timing.min_duration_ms}ms\"")
        
        if timing.max_duration_ms is not None:
            test_code.append(f"    assert duration_ms <= {timing.max_duration_ms}, \\")
            test_code.append(f"        f\"Operation too slow: {{duration_ms}}ms > {timing.max_duration_ms}ms\"")
        
        test_code.append(f"\n")
    
    return "\n".join(test_code)
