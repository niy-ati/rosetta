"""PII detection and redaction using Amazon Macie.

Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
"""

import json
import re
import time
from dataclasses import dataclass
from typing import List, Dict, Any

import boto3
from aws_lambda_powertools import Logger

from rosetta_zero.utils.logging import log_pii_detection

logger = Logger(child=True)


@dataclass
class PIIFinding:
    """PII finding from Macie scan."""
    
    finding_type: str  # e.g., "EMAIL_ADDRESS", "SSN", "CREDIT_CARD"
    location: int  # Byte offset in content
    length: int  # Length of PII data
    confidence: str  # HIGH, MEDIUM, LOW


class PIIScanner:
    """PII detection and redaction using Amazon Macie.
    
    Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
    """
    
    def __init__(
        self,
        region: str,
        s3_client: boto3.client,
        macie_client: boto3.client,
        pii_reports_bucket: str,
    ):
        """Initialize PII Scanner.
        
        Args:
            region: AWS region
            s3_client: Boto3 S3 client
            macie_client: Boto3 Macie2 client
            pii_reports_bucket: S3 bucket for PII detection reports
        """
        self.region = region
        self.s3_client = s3_client
        self.macie_client = macie_client
        self.pii_reports_bucket = pii_reports_bucket
    
    def scan_artifact(
        self,
        s3_bucket: str,
        s3_key: str,
        artifact_id: str,
    ) -> List[PIIFinding]:
        """Scan artifact for PII using Amazon Macie.
        
        Requirement: 20.1
        
        Args:
            s3_bucket: S3 bucket containing artifact
            s3_key: S3 key of artifact
            artifact_id: Unique artifact identifier
        
        Returns:
            List of PII findings
        """
        logger.info(
            "Starting PII scan with Amazon Macie",
            extra={
                "artifact_id": artifact_id,
                "s3_bucket": s3_bucket,
                "s3_key": s3_key,
            },
        )
        
        try:
            # Create a classification job for the specific S3 object
            job_response = self.macie_client.create_classification_job(
                jobType="ONE_TIME",
                name=f"rosetta-zero-pii-scan-{artifact_id}",
                s3JobDefinition={
                    "bucketDefinitions": [
                        {
                            "accountId": boto3.client("sts").get_caller_identity()["Account"],
                            "buckets": [s3_bucket],
                        }
                    ],
                    "scoping": {
                        "includes": {
                            "and": [
                                {
                                    "simpleScopeTerm": {
                                        "comparator": "EQ",
                                        "key": "OBJECT_KEY",
                                        "values": [s3_key],
                                    }
                                }
                            ]
                        }
                    },
                },
                description=f"PII scan for artifact {artifact_id}",
            )
            
            job_id = job_response["jobId"]
            
            logger.info(
                "Macie classification job created",
                extra={"artifact_id": artifact_id, "job_id": job_id},
            )
            
            # Wait for job to complete (with timeout)
            findings = self._wait_for_job_completion(job_id, artifact_id, timeout_seconds=300)
            
            # Store PII detection report in S3 (Requirement 20.5)
            if findings:
                self._store_pii_report(artifact_id, findings)
            
            return findings
            
        except Exception as e:
            logger.error(
                f"Macie PII scan failed: {e}",
                extra={"artifact_id": artifact_id},
            )
            # Return empty findings list on error - don't block ingestion
            return []
    
    def redact_pii(
        self,
        content: bytes,
        findings: List[PIIFinding],
        artifact_id: str,
    ) -> bytes:
        """Redact detected PII from artifact content.
        
        Requirement: 20.2
        
        Args:
            content: Original artifact content
            findings: List of PII findings
            artifact_id: Unique artifact identifier
        
        Returns:
            Content with PII redacted
        """
        if not findings:
            return content
        
        logger.info(
            "Redacting PII from artifact",
            extra={
                "artifact_id": artifact_id,
                "pii_finding_count": len(findings),
            },
        )
        
        # Sort findings by location in reverse order to maintain offsets
        sorted_findings = sorted(findings, key=lambda f: f.location, reverse=True)
        
        # Convert to bytearray for in-place modification
        redacted_content = bytearray(content)
        
        for finding in sorted_findings:
            # Replace PII with [REDACTED-{type}]
            redaction_text = f"[REDACTED-{finding.finding_type}]".encode("utf-8")
            start = finding.location
            end = finding.location + finding.length
            
            # Replace the PII bytes with redaction text
            redacted_content[start:end] = redaction_text
        
        # Log PII detection event to CloudWatch (Requirement 20.4)
        log_pii_detection(
            artifact_id=artifact_id,
            pii_types=[f.finding_type for f in findings],
            redaction_count=len(findings),
        )
        
        return bytes(redacted_content)
    
    def _wait_for_job_completion(
        self,
        job_id: str,
        artifact_id: str,
        timeout_seconds: int = 300,
    ) -> List[PIIFinding]:
        """Wait for Macie job to complete and retrieve findings.
        
        Args:
            job_id: Macie job ID
            artifact_id: Artifact identifier
            timeout_seconds: Maximum wait time
        
        Returns:
            List of PII findings
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Check job status
            job_response = self.macie_client.describe_classification_job(jobId=job_id)
            job_status = job_response["jobStatus"]
            
            if job_status == "COMPLETE":
                # Retrieve findings
                findings_response = self.macie_client.list_findings(
                    findingCriteria={
                        "criterion": {
                            "classificationDetails.jobId": {
                                "eq": [job_id]
                            }
                        }
                    }
                )
                
                findings = []
                for finding_id in findings_response.get("findingIds", []):
                    finding_details = self.macie_client.get_findings(
                        findingIds=[finding_id]
                    )
                    
                    for finding in finding_details.get("findings", []):
                        # Extract PII finding details
                        if "sensitiveData" in finding:
                            for detection in finding["sensitiveData"]:
                                findings.append(
                                    PIIFinding(
                                        finding_type=detection.get("category", "UNKNOWN"),
                                        location=detection.get("location", {}).get("offset", 0),
                                        length=detection.get("location", {}).get("length", 0),
                                        confidence=detection.get("confidence", "UNKNOWN"),
                                    )
                                )
                
                logger.info(
                    "Macie job completed",
                    extra={
                        "artifact_id": artifact_id,
                        "job_id": job_id,
                        "findings_count": len(findings),
                    },
                )
                
                return findings
            
            elif job_status in ["CANCELLED", "FAILED"]:
                logger.error(
                    f"Macie job {job_status.lower()}",
                    extra={"artifact_id": artifact_id, "job_id": job_id},
                )
                return []
            
            # Wait before checking again
            time.sleep(5)
        
        logger.warning(
            "Macie job timeout",
            extra={"artifact_id": artifact_id, "job_id": job_id},
        )
        return []
    
    def _store_pii_report(self, artifact_id: str, findings: List[PIIFinding]) -> None:
        """Store PII detection report in S3.
        
        Requirement: 20.5
        
        Args:
            artifact_id: Artifact identifier
            findings: List of PII findings
        """
        report = {
            "artifact_id": artifact_id,
            "scan_timestamp": time.time(),
            "findings_count": len(findings),
            "findings": [
                {
                    "type": f.finding_type,
                    "location": f.location,
                    "length": f.length,
                    "confidence": f.confidence,
                }
                for f in findings
            ],
        }
        
        report_key = f"pii-reports/{artifact_id}/report.json"
        
        self.s3_client.put_object(
            Bucket=self.pii_reports_bucket,
            Key=report_key,
            Body=json.dumps(report, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        
        logger.info(
            "PII detection report stored",
            extra={
                "artifact_id": artifact_id,
                "report_s3_key": report_key,
            },
        )
