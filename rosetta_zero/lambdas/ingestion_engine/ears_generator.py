"""EARS requirements generation from Logic Maps.

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from typing import List

import boto3
from aws_lambda_powertools import Logger

from rosetta_zero.models import LogicMap, EntryPoint, SideEffect
from rosetta_zero.utils.logging import log_ingestion_decision

logger = Logger(child=True)


class EARSGenerator:
    """Generates EARS-compliant requirements from Logic Maps.
    
    EARS (Easy Approach to Requirements Syntax) uses structured patterns:
    - WHEN <trigger> THE <system> SHALL <action>
    - WHERE <condition> THE <system> SHALL <action>
    - IF <condition> THEN THE <system> SHALL <action>
    
    Requirements: 3.1, 3.2, 3.3, 3.4
    """
    
    def __init__(
        self,
        s3_client: boto3.client,
        ears_bucket: str,
    ):
        """Initialize EARS Generator.
        
        Args:
            s3_client: Boto3 S3 client
            ears_bucket: S3 bucket for EARS documents
        """
        self.s3_client = s3_client
        self.ears_bucket = ears_bucket
    
    def generate_ears_requirements(
        self,
        logic_map: LogicMap,
        artifact_id: str,
    ) -> str:
        """Generate EARS-compliant requirements from Logic Map.
        
        Requirements: 3.1, 3.2
        
        Args:
            logic_map: Logic Map containing behavioral logic
            artifact_id: Unique artifact identifier
        
        Returns:
            S3 key of stored EARS document
        """
        logger.info(
            "Generating EARS requirements",
            extra={
                "artifact_id": artifact_id,
                "entry_points_count": len(logic_map.entry_points),
            },
        )
        
        # Generate EARS document
        ears_document = self._generate_document(logic_map, artifact_id)
        
        # Store EARS document in S3 (Requirement 3.3)
        s3_key = self._store_ears_document(ears_document, artifact_id)
        
        # Log EARS generation event (Requirement 3.4)
        log_ingestion_decision(
            artifact_id=artifact_id,
            decision="ears_generated",
            details={
                "ears_s3_key": s3_key,
                "requirements_count": ears_document.count("SHALL"),
            }
        )
        
        logger.info(
            "EARS requirements generated",
            extra={
                "artifact_id": artifact_id,
                "ears_s3_key": s3_key,
            },
        )
        
        return s3_key
    
    def _generate_document(self, logic_map: LogicMap, artifact_id: str) -> str:
        """Generate EARS document from Logic Map.
        
        Requirement: 3.2
        
        Args:
            logic_map: Logic Map
            artifact_id: Artifact identifier
        
        Returns:
            EARS document as markdown string
        """
        lines = []
        
        # Header
        lines.append(f"# EARS Requirements Document")
        lines.append(f"")
        lines.append(f"**Artifact ID:** {artifact_id}")
        lines.append(f"**Generated:** {logic_map.extraction_timestamp}")
        lines.append(f"")
        lines.append(f"## Overview")
        lines.append(f"")
        lines.append(f"This document contains EARS-compliant behavioral requirements ")
        lines.append(f"extracted from the legacy system.")
        lines.append(f"")
        
        # Entry Point Requirements
        lines.append(f"## Entry Point Requirements")
        lines.append(f"")
        
        for idx, entry_point in enumerate(logic_map.entry_points, 1):
            lines.extend(self._generate_entry_point_requirements(entry_point, idx))
        
        # Side Effect Requirements
        if logic_map.side_effects:
            lines.append(f"## Side Effect Requirements")
            lines.append(f"")
            
            for idx, side_effect in enumerate(logic_map.side_effects, 1):
                lines.extend(self._generate_side_effect_requirements(side_effect, idx))
        
        # Control Flow Requirements
        lines.append(f"## Control Flow Requirements")
        lines.append(f"")
        
        if logic_map.control_flow and logic_map.control_flow.nodes:
            lines.append(f"### REQ-CF-1: Control Flow Execution")
            lines.append(f"")
            lines.append(f"WHEN the system executes, THE system SHALL follow the control ")
            lines.append(f"flow graph with {len(logic_map.control_flow.nodes)} nodes and ")
            lines.append(f"{len(logic_map.control_flow.edges)} edges.")
            lines.append(f"")
        
        # Data Structure Requirements
        if logic_map.data_structures:
            lines.append(f"## Data Structure Requirements")
            lines.append(f"")
            
            for idx, data_structure in enumerate(logic_map.data_structures, 1):
                lines.append(f"### REQ-DS-{idx}: {data_structure.name}")
                lines.append(f"")
                lines.append(f"THE system SHALL maintain data structure `{data_structure.name}` ")
                lines.append(f"with {len(data_structure.fields)} fields and total size of ")
                lines.append(f"{data_structure.size_bytes} bytes.")
                lines.append(f"")
        
        # Dependency Requirements
        if logic_map.dependencies:
            lines.append(f"## Dependency Requirements")
            lines.append(f"")
            
            for idx, dependency in enumerate(logic_map.dependencies, 1):
                lines.append(f"### REQ-DEP-{idx}: {dependency.name}")
                lines.append(f"")
                lines.append(f"THE system SHALL interact with external dependency ")
                lines.append(f"`{dependency.name}` of type {dependency.type}.")
                lines.append(f"")
                lines.append(f"**Description:** {dependency.description}")
                lines.append(f"")
        
        # Arithmetic Precision Requirements
        if logic_map.arithmetic_precision:
            lines.append(f"## Arithmetic Precision Requirements")
            lines.append(f"")
            
            if logic_map.arithmetic_precision.fixed_point_operations:
                lines.append(f"### REQ-AP-1: Fixed-Point Arithmetic")
                lines.append(f"")
                lines.append(f"WHERE fixed-point arithmetic is performed, THE system SHALL ")
                lines.append(f"maintain the exact precision and scale as specified in the ")
                lines.append(f"legacy implementation.")
                lines.append(f"")
            
            if logic_map.arithmetic_precision.floating_point_precision:
                lines.append(f"### REQ-AP-2: Floating-Point Precision")
                lines.append(f"")
                lines.append(f"WHERE floating-point arithmetic is performed, THE system SHALL ")
                lines.append(f"use the exact precision (number of bits) as specified in the ")
                lines.append(f"legacy implementation.")
                lines.append(f"")
            
            if logic_map.arithmetic_precision.rounding_modes:
                lines.append(f"### REQ-AP-3: Rounding Modes")
                lines.append(f"")
                lines.append(f"WHERE rounding is performed, THE system SHALL use the exact ")
                lines.append(f"rounding mode as specified in the legacy implementation.")
                lines.append(f"")
        
        return "\n".join(lines)
    
    def _generate_entry_point_requirements(
        self,
        entry_point: EntryPoint,
        index: int,
    ) -> List[str]:
        """Generate EARS requirements for an entry point.
        
        Args:
            entry_point: Entry point from Logic Map
            index: Requirement index
        
        Returns:
            List of requirement lines
        """
        lines = []
        
        lines.append(f"### REQ-EP-{index}: {entry_point.name}")
        lines.append(f"")
        
        # Main requirement
        param_names = ", ".join([p.name for p in entry_point.parameters])
        lines.append(f"WHEN the entry point `{entry_point.name}` is invoked with ")
        lines.append(f"parameters ({param_names}), THE system SHALL execute the ")
        lines.append(f"behavioral logic and return a value of type {entry_point.return_type}.")
        lines.append(f"")
        
        # Description
        lines.append(f"**Description:** {entry_point.description}")
        lines.append(f"")
        
        # Parameter requirements
        if entry_point.parameters:
            lines.append(f"**Parameters:**")
            lines.append(f"")
            for param in entry_point.parameters:
                lines.append(f"- `{param.name}` ({param.type}): {param.description}")
                if hasattr(param, 'min_value') and param.min_value is not None:
                    lines.append(f"  - Minimum value: {param.min_value}")
                if hasattr(param, 'max_value') and param.max_value is not None:
                    lines.append(f"  - Maximum value: {param.max_value}")
                if hasattr(param, 'max_length') and param.max_length is not None:
                    lines.append(f"  - Maximum length: {param.max_length}")
            lines.append(f"")
        
        return lines
    
    def _generate_side_effect_requirements(
        self,
        side_effect: SideEffect,
        index: int,
    ) -> List[str]:
        """Generate EARS requirements for a side effect.
        
        Args:
            side_effect: Side effect from Logic Map
            index: Requirement index
        
        Returns:
            List of requirement lines
        """
        lines = []
        
        lines.append(f"### REQ-SE-{index}: {side_effect.operation_type} Side Effect")
        lines.append(f"")
        
        lines.append(f"WHEN the system executes, THE system SHALL perform ")
        lines.append(f"{side_effect.operation_type} operations in scope `{side_effect.scope}` ")
        lines.append(f"exactly as specified in the legacy implementation.")
        lines.append(f"")
        
        lines.append(f"**Description:** {side_effect.description}")
        lines.append(f"")
        
        if side_effect.timing_requirements:
            lines.append(f"**Timing Requirements:** The system SHALL maintain timing ")
            lines.append(f"behavior equivalent to the legacy implementation.")
            lines.append(f"")
        
        return lines
    
    def _store_ears_document(self, ears_document: str, artifact_id: str) -> str:
        """Store EARS document in S3.
        
        Requirement: 3.3
        
        Args:
            ears_document: EARS document content
            artifact_id: Artifact identifier
        
        Returns:
            S3 key of stored document
        """
        s3_key = f"ears-requirements/{artifact_id}/ears.md"
        
        self.s3_client.put_object(
            Bucket=self.ears_bucket,
            Key=s3_key,
            Body=ears_document.encode("utf-8"),
            ContentType="text/markdown",
        )
        
        logger.info(
            "EARS document stored in S3",
            extra={
                "artifact_id": artifact_id,
                "s3_key": s3_key,
                "bucket": self.ears_bucket,
            },
        )
        
        return s3_key
