"""Ingestion Engine implementation.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import boto3
from aws_lambda_powertools import Logger

from rosetta_zero.utils.logging import log_ingestion_decision
from .pii_scanner import PIIScanner
from .logic_map_extractor import LogicMapExtractor
from .ears_generator import EARSGenerator
from .error_handler import handle_ingestion_error

logger = Logger(child=True)


@dataclass
class IngestionResult:
    """Result of artifact ingestion."""
    
    artifact_id: str
    artifact_hash: str
    ingestion_timestamp: datetime
    s3_location: str
    logic_map_s3_key: Optional[str] = None
    ears_document_s3_key: Optional[str] = None


class IngestionEngine:
    """Analyzes legacy code and extracts behavioral logic.
    
    Requirements: 1.1, 1.2, 1.3, 1.4
    """
    
    def __init__(
        self,
        region: str,
        logic_maps_bucket: str,
        ears_bucket: str,
        kms_key_id: str,
        pii_reports_bucket: Optional[str] = None,
    ):
        """Initialize Ingestion Engine.
        
        Args:
            region: AWS region
            logic_maps_bucket: S3 bucket for Logic Maps
            ears_bucket: S3 bucket for EARS documents
            kms_key_id: KMS key ID for encryption
            pii_reports_bucket: S3 bucket for PII detection reports
        """
        self.region = region
        self.logic_maps_bucket = logic_maps_bucket
        self.ears_bucket = ears_bucket
        self.kms_key_id = kms_key_id
        self.pii_reports_bucket = pii_reports_bucket
        
        # Initialize AWS clients
        self.s3_client = boto3.client("s3", region_name=region)
        self.bedrock_client = boto3.client("bedrock-runtime", region_name=region)
        self.macie_client = boto3.client("macie2", region_name=region)
        
        # Initialize PII scanner
        self.pii_scanner = PIIScanner(
            region=region,
            s3_client=self.s3_client,
            macie_client=self.macie_client,
            pii_reports_bucket=pii_reports_bucket or logic_maps_bucket,
        )
        
        # Initialize Logic Map extractor
        self.logic_map_extractor = LogicMapExtractor(
            bedrock_client=self.bedrock_client,
            s3_client=self.s3_client,
            logic_maps_bucket=logic_maps_bucket,
        )
        
        # Initialize EARS generator
        self.ears_generator = EARSGenerator(
            s3_client=self.s3_client,
            ears_bucket=ears_bucket,
        )
    
    @handle_ingestion_error
    def ingest_artifact(
        self,
        s3_bucket: str,
        s3_key: str,
        artifact_type: str,
    ) -> IngestionResult:
        """Ingest a legacy artifact from S3.
        
        Requirements: 1.1, 1.2, 1.3, 1.4
        
        Args:
            s3_bucket: S3 bucket containing the artifact
            s3_key: S3 key of the artifact
            artifact_type: Type of artifact (COBOL, FORTRAN, MAINFRAME_BINARY)
        
        Returns:
            IngestionResult containing artifact hash, storage location,
            and ingestion timestamp.
        """
        # Generate unique artifact ID
        artifact_id = str(uuid.uuid4())
        ingestion_timestamp = datetime.utcnow()
        
        logger.info(
            "Reading artifact from S3",
            extra={
                "artifact_id": artifact_id,
                "s3_bucket": s3_bucket,
                "s3_key": s3_key,
            },
        )
        
        # Read artifact from S3
        response = self.s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        artifact_content = response["Body"].read()
        
        # Scan for PII (Requirements 20.1, 20.2)
        pii_findings = self.pii_scanner.scan_artifact(
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            artifact_id=artifact_id,
        )
        
        # Redact PII if detected
        if pii_findings:
            artifact_content = self.pii_scanner.redact_pii(
                content=artifact_content,
                findings=pii_findings,
                artifact_id=artifact_id,
            )
        
        # Generate SHA-256 hash for integrity verification (Requirement 1.3)
        artifact_hash = self._generate_hash(artifact_content)
        
        logger.info(
            "Generated artifact hash",
            extra={
                "artifact_id": artifact_id,
                "artifact_hash": artifact_hash,
                "artifact_size_bytes": len(artifact_content),
            },
        )
        
        # Store artifact metadata (Requirement 1.4)
        metadata = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "artifact_hash": artifact_hash,
            "ingestion_timestamp": ingestion_timestamp.isoformat(),
            "original_s3_bucket": s3_bucket,
            "original_s3_key": s3_key,
        }
        
        # Log storage event to CloudWatch (Requirement 1.4)
        log_ingestion_decision(
            artifact_id=artifact_id,
            decision="artifact_ingested",
            details={
                "artifact_type": artifact_type,
                "artifact_hash": artifact_hash,
                "s3_location": f"s3://{s3_bucket}/{s3_key}",
                **metadata
            }
        )
        
        # Extract Logic Map using Bedrock (Requirements 2.1-2.7)
        logic_map = self.logic_map_extractor.extract_logic_map(
            artifact_content=artifact_content,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
        )
        
        logic_map_s3_key = f"logic-maps/{artifact_id}/logic-map.json"
        
        # Generate EARS requirements (Requirements 3.1-3.4)
        ears_s3_key = self.ears_generator.generate_ears_requirements(
            logic_map=logic_map,
            artifact_id=artifact_id,
        )
        
        return IngestionResult(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            ingestion_timestamp=ingestion_timestamp,
            s3_location=f"s3://{s3_bucket}/{s3_key}",
            logic_map_s3_key=logic_map_s3_key,
            ears_document_s3_key=ears_s3_key,
        )
    
    def _generate_hash(self, content: bytes) -> str:
        """Generate SHA-256 hash of content.
        
        Requirement: 1.3
        
        Args:
            content: Content to hash
        
        Returns:
            SHA-256 hash as hex string with 'sha256:' prefix
        """
        hash_obj = hashlib.sha256(content)
        return f"sha256:{hash_obj.hexdigest()}"
