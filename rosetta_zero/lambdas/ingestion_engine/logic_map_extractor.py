"""Logic Map extraction using Amazon Bedrock.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
"""

import json
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger

from rosetta_zero.models import LogicMap
from rosetta_zero.utils.logging import log_ingestion_decision

logger = Logger(child=True)


class LogicMapExtractor:
    """Extracts Logic Maps from legacy code using Amazon Bedrock.
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
    """
    
    def __init__(
        self,
        bedrock_client: boto3.client,
        s3_client: boto3.client,
        logic_maps_bucket: str,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
    ):
        """Initialize Logic Map Extractor.
        
        Args:
            bedrock_client: Boto3 Bedrock Runtime client
            s3_client: Boto3 S3 client
            logic_maps_bucket: S3 bucket for storing Logic Maps
            model_id: Bedrock model ID (default: Claude 3.5 Sonnet)
        """
        self.bedrock_client = bedrock_client
        self.s3_client = s3_client
        self.logic_maps_bucket = logic_maps_bucket
        self.model_id = model_id
    
    def extract_logic_map(
        self,
        artifact_content: bytes,
        artifact_id: str,
        artifact_type: str,
    ) -> LogicMap:
        """Extract Logic Map from legacy artifact using Bedrock.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
        
        Args:
            artifact_content: Legacy code content (after PII redaction)
            artifact_id: Unique artifact identifier
            artifact_type: Type of artifact (COBOL, FORTRAN, MAINFRAME_BINARY)
        
        Returns:
            LogicMap containing behavioral logic
        """
        logger.info(
            "Extracting Logic Map with Amazon Bedrock",
            extra={
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "model_id": self.model_id,
            },
        )
        
        # Construct structured prompt for Bedrock
        prompt = self._construct_prompt(artifact_content, artifact_type)
        
        # Invoke Bedrock (Requirement 2.1)
        response = self._invoke_bedrock(prompt, artifact_id)
        
        # Parse Bedrock response into LogicMap (Requirement 2.2)
        logic_map = self._parse_response(response, artifact_id, artifact_type)
        
        # Validate Logic Map completeness (Requirements 2.3, 2.4, 2.5, 2.6)
        self._validate_logic_map(logic_map, artifact_id)
        
        # Store Logic Map in S3 (Requirement 2.7)
        s3_key = self._store_logic_map(logic_map, artifact_id)
        
        logger.info(
            "Logic Map extraction completed",
            extra={
                "artifact_id": artifact_id,
                "logic_map_s3_key": s3_key,
                "entry_points_count": len(logic_map.entry_points),
                "data_structures_count": len(logic_map.data_structures),
            },
        )
        
        return logic_map
    
    def _construct_prompt(self, artifact_content: bytes, artifact_type: str) -> str:
        """Construct structured prompt for Bedrock.
        
        Args:
            artifact_content: Legacy code content
            artifact_type: Type of artifact
        
        Returns:
            Structured prompt for Logic Map extraction
        """
        # Decode content (handle binary artifacts)
        try:
            code_text = artifact_content.decode("utf-8")
        except UnicodeDecodeError:
            # For binary artifacts, provide hex representation
            code_text = f"[Binary content, {len(artifact_content)} bytes]\n{artifact_content[:1000].hex()}"
        
        prompt = f"""Analyze the following {artifact_type} code and extract behavioral logic into a Logic Map.

A Logic Map is an implementation-agnostic representation of system behavior. Extract:

1. **Entry Points**: All functions, procedures, or entry points with:
   - Name
   - Parameters (name, type, constraints)
   - Return type
   - Description of behavior

2. **Data Structures**: All data structures with:
   - Name
   - Fields (name, type, size)
   - Size in bytes
   - Alignment requirements

3. **Control Flow**: Control flow graph with:
   - Nodes (basic blocks, conditions, loops)
   - Edges (control flow transitions)
   - Branch conditions

4. **Dependencies**: External dependencies:
   - File system operations
   - Database operations
   - Network operations
   - Hardware interactions
   - External libraries

5. **Side Effects**: Observable side effects:
   - Global variable accesses
   - File I/O operations
   - Database operations
   - Hardware interactions
   - Network operations
   - Include operation type and scope

6. **Arithmetic Precision**: Arithmetic requirements:
   - Fixed-point operations
   - Floating-point precision
   - Rounding modes

Code to analyze:
```
{code_text}
```

Output the Logic Map as a JSON object matching this schema:
{{
  "artifact_id": "string",
  "artifact_version": "string",
  "extraction_timestamp": "ISO 8601 timestamp",
  "entry_points": [
    {{
      "name": "string",
      "parameters": [
        {{
          "name": "string",
          "type": "INTEGER|STRING|DATE|DECIMAL|BOOLEAN|BINARY",
          "description": "string",
          "min_value": number (optional),
          "max_value": number (optional),
          "max_length": number (optional)
        }}
      ],
      "return_type": "string",
      "description": "string"
    }}
  ],
  "data_structures": [
    {{
      "name": "string",
      "fields": [
        {{
          "name": "string",
          "type": "string",
          "size_bytes": number,
          "offset": number
        }}
      ],
      "size_bytes": number,
      "alignment": number
    }}
  ],
  "control_flow": {{
    "nodes": [
      {{
        "id": "string",
        "type": "BASIC_BLOCK|CONDITION|LOOP|FUNCTION_CALL",
        "description": "string"
      }}
    ],
    "edges": [
      {{
        "from_node": "string",
        "to_node": "string",
        "condition": "string (optional)"
      }}
    ]
  }},
  "dependencies": [
    {{
      "name": "string",
      "type": "FILE|DATABASE|NETWORK|HARDWARE|LIBRARY",
      "description": "string"
    }}
  ],
  "side_effects": [
    {{
      "operation_type": "FILE_IO|DATABASE|NETWORK|GLOBAL_VAR|HARDWARE",
      "scope": "string",
      "description": "string"
    }}
  ],
  "arithmetic_precision": {{
    "fixed_point_operations": [
      {{
        "operation": "string",
        "precision_bits": number,
        "scale": number
      }}
    ],
    "floating_point_precision": {{
      "operation_name": precision_bits
    }},
    "rounding_modes": {{
      "operation_name": "ROUND_HALF_UP|ROUND_HALF_DOWN|TRUNCATE|CEILING|FLOOR"
    }}
  }}
}}

Provide ONLY the JSON output, no additional text."""
        
        return prompt
    
    def _invoke_bedrock(self, prompt: str, artifact_id: str) -> Dict[str, Any]:
        """Invoke Amazon Bedrock with Claude 3.5 Sonnet.
        
        Args:
            prompt: Structured prompt
            artifact_id: Artifact identifier for logging
        
        Returns:
            Bedrock response
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0.0,  # Deterministic output
        }
        
        logger.info(
            "Invoking Bedrock",
            extra={
                "artifact_id": artifact_id,
                "model_id": self.model_id,
                "prompt_length": len(prompt),
            },
        )
        
        response = self.bedrock_client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
        )
        
        response_body = json.loads(response["body"].read())
        
        log_ingestion_decision(
            artifact_id=artifact_id,
            decision="bedrock_invoked",
            details={
                "model_id": self.model_id,
                "input_tokens": response_body.get("usage", {}).get("input_tokens", 0),
                "output_tokens": response_body.get("usage", {}).get("output_tokens", 0),
            }
        )
        
        return response_body
    
    def _parse_response(
        self,
        response: Dict[str, Any],
        artifact_id: str,
        artifact_type: str,
    ) -> LogicMap:
        """Parse Bedrock response into LogicMap dataclass.
        
        Args:
            response: Bedrock response
            artifact_id: Artifact identifier
            artifact_type: Artifact type
        
        Returns:
            LogicMap object
        """
        # Extract content from response
        content = response["content"][0]["text"]
        
        # Extract JSON from content (may be wrapped in markdown code blocks)
        json_str = self._extract_json(content)
        
        # Parse JSON
        logic_map_dict = json.loads(json_str)
        
        # Update with artifact metadata
        logic_map_dict["artifact_id"] = artifact_id
        logic_map_dict["artifact_version"] = "1.0"
        
        # Convert to LogicMap dataclass
        logic_map = LogicMap.from_json(json.dumps(logic_map_dict))
        
        return logic_map
    
    def _extract_json(self, content: str) -> str:
        """Extract JSON from Bedrock response content.
        
        Args:
            content: Response content (may include markdown)
        
        Returns:
            JSON string
        """
        # Remove markdown code blocks if present
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            return content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            return content[start:end].strip()
        else:
            return content.strip()
    
    def _validate_logic_map(self, logic_map: LogicMap, artifact_id: str) -> None:
        """Validate Logic Map completeness.
        
        Requirements: 2.3, 2.4, 2.5, 2.6
        
        Args:
            logic_map: Logic Map to validate
            artifact_id: Artifact identifier
        
        Raises:
            ValueError: If Logic Map is incomplete
        """
        errors = []
        
        # Requirement 2.3: Identify all entry points
        if not logic_map.entry_points:
            errors.append("No entry points identified")
        
        # Requirement 2.4: Identify all data structures
        # (May be empty for simple programs)
        
        # Requirement 2.5: Identify all control flow paths
        if not logic_map.control_flow or not logic_map.control_flow.nodes:
            errors.append("No control flow identified")
        
        # Requirement 2.6: Identify all external dependencies
        # (May be empty for self-contained programs)
        
        if errors:
            logger.error(
                "Logic Map validation failed",
                extra={
                    "artifact_id": artifact_id,
                    "validation_errors": errors,
                },
            )
            raise ValueError(f"Logic Map validation failed: {', '.join(errors)}")
        
        logger.info(
            "Logic Map validation passed",
            extra={"artifact_id": artifact_id},
        )
    
    def _store_logic_map(self, logic_map: LogicMap, artifact_id: str) -> str:
        """Store Logic Map in S3 with versioning.
        
        Requirement: 2.7
        
        Args:
            logic_map: Logic Map to store
            artifact_id: Artifact identifier
        
        Returns:
            S3 key of stored Logic Map
        """
        s3_key = f"logic-maps/{artifact_id}/logic-map.json"
        
        self.s3_client.put_object(
            Bucket=self.logic_maps_bucket,
            Key=s3_key,
            Body=logic_map.to_json().encode("utf-8"),
            ContentType="application/json",
        )
        
        logger.info(
            "Logic Map stored in S3",
            extra={
                "artifact_id": artifact_id,
                "s3_key": s3_key,
                "bucket": self.logic_maps_bucket,
            },
        )
        
        return s3_key
