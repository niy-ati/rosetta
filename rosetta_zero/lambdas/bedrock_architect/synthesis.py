"""Bedrock Architect - Synthesizes modern AWS Lambda functions from Logic Maps.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
"""

import json
import boto3
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from rosetta_zero.models.logic_map import LogicMap
from rosetta_zero.utils.logging import logger, log_architect_decision
from rosetta_zero.utils.retry import with_retry, TransientError

from .knowledge_base import query_language_docs
from .precision import preserve_arithmetic_precision
from .faithful_transpilation import validate_faithful_transpilation
from .timing import preserve_timing_behavior
from .cdk_generator import generate_cdk_infrastructure
from .error_handler import handle_bedrock_error


@dataclass
class SynthesisResult:
    """Result from Lambda synthesis."""
    artifact_id: str
    modern_implementation_s3_key: str
    cdk_infrastructure_s3_key: str
    synthesis_timestamp: datetime


class BedrockArchitect:
    """Synthesizes modern AWS Lambda functions from Logic Maps."""
    
    def __init__(
        self,
        region: str,
        modern_implementations_bucket: str,
        cdk_infrastructure_bucket: str,
        kms_key_id: str,
        bedrock_model_id: str,
        cobol_kb_id: Optional[str] = None,
        fortran_kb_id: Optional[str] = None,
        mainframe_kb_id: Optional[str] = None,
    ):
        """
        Initialize Bedrock Architect.
        
        Args:
            region: AWS region
            modern_implementations_bucket: S3 bucket for generated Lambda code
            cdk_infrastructure_bucket: S3 bucket for CDK infrastructure code
            kms_key_id: KMS key ID for encryption
            bedrock_model_id: Bedrock model ID (Claude 3.5 Sonnet)
            cobol_kb_id: Bedrock Knowledge Base ID for COBOL docs
            fortran_kb_id: Bedrock Knowledge Base ID for FORTRAN docs
            mainframe_kb_id: Bedrock Knowledge Base ID for mainframe docs
        """
        self.region = region
        self.modern_implementations_bucket = modern_implementations_bucket
        self.cdk_infrastructure_bucket = cdk_infrastructure_bucket
        self.kms_key_id = kms_key_id
        self.bedrock_model_id = bedrock_model_id
        
        # Knowledge Base IDs
        self.knowledge_base_ids = {
            'COBOL': cobol_kb_id,
            'FORTRAN': fortran_kb_id,
            'MAINFRAME': mainframe_kb_id,
        }
        
        # Initialize AWS clients
        self.s3_client = boto3.client('s3', region_name=region)
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=region)
        self.bedrock_agent_client = boto3.client('bedrock-agent-runtime', region_name=region)
    
    def synthesize_lambda(
        self,
        logic_map_bucket: str,
        logic_map_key: str,
    ) -> SynthesisResult:
        """
        Synthesize modern AWS Lambda function from Logic Map.
        
        Args:
            logic_map_bucket: S3 bucket containing Logic Map
            logic_map_key: S3 key for Logic Map JSON
            
        Returns:
            SynthesisResult with S3 locations of generated code
        """
        # Step 1: Read Logic Map from S3
        logic_map = self._read_logic_map(logic_map_bucket, logic_map_key)
        
        log_architect_decision(
            logic_map_id=logic_map.artifact_id,
            decision="logic_map_loaded",
            details={
                "entry_points": len(logic_map.entry_points),
                "side_effects": len(logic_map.side_effects),
            }
        )
        
        # Step 2: Query language documentation from Knowledge Bases
        language_context = self._query_language_documentation(logic_map)
        
        # Step 3: Preserve arithmetic precision requirements
        precision_config = preserve_arithmetic_precision(logic_map)
        
        # Step 4: Preserve timing behavior
        timing_docs = preserve_timing_behavior(logic_map)
        
        # Step 5: Generate modern Lambda code using Bedrock
        lambda_code = self._generate_lambda_code(
            logic_map,
            language_context,
            precision_config,
            timing_docs
        )
        
        # Step 6: Validate faithful transpilation
        validate_faithful_transpilation(logic_map, lambda_code)
        
        # Step 7: Store generated Lambda code in S3
        modern_impl_key = self._store_lambda_code(logic_map, lambda_code)
        
        # Step 8: Generate CDK infrastructure code
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Step 9: Store CDK code in S3
        cdk_key = self._store_cdk_code(logic_map, cdk_code)
        
        log_architect_decision(
            logic_map_id=logic_map.artifact_id,
            decision="synthesis_complete",
            details={
                "modern_implementation_key": modern_impl_key,
                "cdk_infrastructure_key": cdk_key,
            }
        )
        
        return SynthesisResult(
            artifact_id=logic_map.artifact_id,
            modern_implementation_s3_key=modern_impl_key,
            cdk_infrastructure_s3_key=cdk_key,
            synthesis_timestamp=datetime.utcnow(),
        )
    
    @with_retry(max_retries=3, base_delay_seconds=2)
    def _read_logic_map(self, bucket: str, key: str) -> LogicMap:
        """Read Logic Map from S3 with retry."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            logic_map_json = response['Body'].read().decode('utf-8')
            return LogicMap.from_json(logic_map_json)
        except self.s3_client.exceptions.NoSuchKey:
            raise ValueError(f"Logic Map not found: s3://{bucket}/{key}")
        except Exception as e:
            if self._is_transient_error(e):
                raise TransientError(f"Transient error reading Logic Map: {e}")
            raise
    
    def _query_language_documentation(self, logic_map: LogicMap) -> str:
        """Query Bedrock Knowledge Bases for language documentation."""
        # Determine language from artifact metadata or dependencies
        language = self._detect_language(logic_map)
        
        if language not in self.knowledge_base_ids or not self.knowledge_base_ids[language]:
            logger.warning(f"No Knowledge Base configured for {language}")
            return ""
        
        # Query Knowledge Base for relevant documentation
        context = query_language_docs(
            bedrock_agent_client=self.bedrock_agent_client,
            knowledge_base_id=self.knowledge_base_ids[language],
            logic_map=logic_map,
            language=language
        )
        
        log_architect_decision(
            logic_map_id=logic_map.artifact_id,
            decision="language_docs_queried",
            details={
                "language": language,
                "context_length": len(context),
            }
        )
        
        return context
    
    def _detect_language(self, logic_map: LogicMap) -> str:
        """Detect legacy language from Logic Map."""
        # Check dependencies for language hints
        for dep in logic_map.dependencies:
            if 'COBOL' in dep.type.upper() or 'CBL' in dep.type.upper():
                return 'COBOL'
            if 'FORTRAN' in dep.type.upper() or 'F77' in dep.type.upper():
                return 'FORTRAN'
        
        # Default to COBOL if unclear
        return 'COBOL'
    
    @with_retry(max_retries=3, base_delay_seconds=2)
    def _generate_lambda_code(
        self,
        logic_map: LogicMap,
        language_context: str,
        precision_config: str,
        timing_docs: str
    ) -> str:
        """Generate Lambda code using Bedrock with retry."""
        try:
            # Construct prompt for Bedrock
            prompt = self._construct_synthesis_prompt(
                logic_map,
                language_context,
                precision_config,
                timing_docs
            )
            
            # Invoke Bedrock
            response = self.bedrock_client.invoke_model(
                modelId=self.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 100000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0,  # Deterministic for faithful transpilation
                })
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            lambda_code = self._extract_code_from_response(response_body)
            
            log_architect_decision(
                logic_map_id=logic_map.artifact_id,
                decision="lambda_code_generated",
                details={
                    "code_length": len(lambda_code),
                    "model_id": self.bedrock_model_id,
                }
            )
            
            return lambda_code
            
        except Exception as e:
            return handle_bedrock_error(e, "generate_lambda_code", logic_map.artifact_id)
    
    def _construct_synthesis_prompt(
        self,
        logic_map: LogicMap,
        language_context: str,
        precision_config: str,
        timing_docs: str
    ) -> str:
        """Construct Bedrock prompt for Lambda synthesis."""
        prompt = f"""You are synthesizing a modern AWS Lambda function in Python 3.12 from a legacy system Logic Map.

CRITICAL REQUIREMENTS:
1. Implement ONLY the behaviors documented in the Logic Map - no feature addition
2. Preserve ALL side effects exactly as documented
3. Preserve arithmetic precision as specified
4. Follow AWS Lambda best practices
5. Use AWS Lambda PowerTools for logging
6. Implement comprehensive error handling

Logic Map:
{logic_map.to_json()}

Language Documentation Context:
{language_context}

Arithmetic Precision Requirements:
{precision_config}

Timing Behavior Requirements:
{timing_docs}

Generate a complete Python 3.12 Lambda function that:
- Has a lambda_handler(event, context) entry point
- Uses AWS Lambda PowerTools decorators (@logger.inject_lambda_context, @tracer.capture_lambda_handler)
- Implements all entry points from the Logic Map
- Preserves all side effects (file I/O, database operations, etc.)
- Includes detailed comments documenting arithmetic precision decisions
- Includes error handling with proper AWS Lambda error patterns
- Logs all operations using PowerTools logger

Output ONLY the Python code, no explanations."""
        
        return prompt
    
    def _extract_code_from_response(self, response_body: dict) -> str:
        """Extract generated code from Bedrock response."""
        content = response_body.get('content', [])
        if not content:
            raise ValueError("Empty response from Bedrock")
        
        # Extract text from response
        code = content[0].get('text', '')
        
        # Remove markdown code fences if present
        if code.startswith('```python'):
            code = code[len('```python'):].strip()
        if code.startswith('```'):
            code = code[3:].strip()
        if code.endswith('```'):
            code = code[:-3].strip()
        
        return code
    
    def _store_lambda_code(self, logic_map: LogicMap, code: str) -> str:
        """Store generated Lambda code in S3."""
        key = f"modern-implementations/{logic_map.artifact_id}/{logic_map.artifact_version}/lambda.py"
        
        self.s3_client.put_object(
            Bucket=self.modern_implementations_bucket,
            Key=key,
            Body=code.encode('utf-8'),
            ServerSideEncryption='aws:kms',
            SSEKMSKeyId=self.kms_key_id,
            ContentType='text/x-python',
        )
        
        logger.info(f"Stored Lambda code: s3://{self.modern_implementations_bucket}/{key}")
        return key
    
    def _store_cdk_code(self, logic_map: LogicMap, code: str) -> str:
        """Store generated CDK code in S3."""
        key = f"cdk-infrastructure/{logic_map.artifact_id}/{logic_map.artifact_version}/stack.py"
        
        self.s3_client.put_object(
            Bucket=self.cdk_infrastructure_bucket,
            Key=key,
            Body=code.encode('utf-8'),
            ServerSideEncryption='aws:kms',
            SSEKMSKeyId=self.kms_key_id,
            ContentType='text/x-python',
        )
        
        logger.info(f"Stored CDK code: s3://{self.cdk_infrastructure_bucket}/{key}")
        return key
    
    @staticmethod
    def _is_transient_error(error: Exception) -> bool:
        """Check if error is transient and should be retried."""
        error_str = str(error).lower()
        transient_indicators = [
            'throttling',
            'timeout',
            'connection',
            'service unavailable',
            '503',
            '500',
        ]
        return any(indicator in error_str for indicator in transient_indicators)
