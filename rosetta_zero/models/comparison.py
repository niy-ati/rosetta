"""Data models for comparison results and certificates."""

import hashlib
import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ByteDiff:
    """Byte-level difference between outputs."""
    offset: int
    legacy_bytes: bytes
    modern_bytes: bytes
    context_before: bytes
    context_after: bytes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'offset': self.offset,
            'legacy_bytes': self.legacy_bytes.hex(),
            'modern_bytes': self.modern_bytes.hex(),
            'context_before': self.context_before.hex(),
            'context_after': self.context_after.hex(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ByteDiff':
        """Create from dictionary."""
        return cls(
            offset=data['offset'],
            legacy_bytes=bytes.fromhex(data['legacy_bytes']),
            modern_bytes=bytes.fromhex(data['modern_bytes']),
            context_before=bytes.fromhex(data['context_before']),
            context_after=bytes.fromhex(data['context_after']),
        )


@dataclass
class SideEffectDiff:
    """Difference in side effects."""
    effect_type: str
    operation: str
    legacy_data: Optional[bytes]
    modern_data: Optional[bytes]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'effect_type': self.effect_type,
            'operation': self.operation,
            'legacy_data': self.legacy_data.hex() if self.legacy_data else None,
            'modern_data': self.modern_data.hex() if self.modern_data else None,
            'description': self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SideEffectDiff':
        """Create from dictionary."""
        return cls(
            effect_type=data['effect_type'],
            operation=data['operation'],
            legacy_data=bytes.fromhex(data['legacy_data']) if data.get('legacy_data') else None,
            modern_data=bytes.fromhex(data['modern_data']) if data.get('modern_data') else None,
            description=data['description'],
        )


@dataclass
class DifferenceDetails:
    """Detailed information about output differences."""
    return_value_diff: Optional[ByteDiff]
    stdout_diff: Optional[ByteDiff]
    stderr_diff: Optional[ByteDiff]
    side_effect_diffs: List[SideEffectDiff]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'return_value_diff': self.return_value_diff.to_dict() if self.return_value_diff else None,
            'stdout_diff': self.stdout_diff.to_dict() if self.stdout_diff else None,
            'stderr_diff': self.stderr_diff.to_dict() if self.stderr_diff else None,
            'side_effect_diffs': [sed.to_dict() for sed in self.side_effect_diffs],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DifferenceDetails':
        """Create from dictionary."""
        return cls(
            return_value_diff=ByteDiff.from_dict(data['return_value_diff']) if data.get('return_value_diff') else None,
            stdout_diff=ByteDiff.from_dict(data['stdout_diff']) if data.get('stdout_diff') else None,
            stderr_diff=ByteDiff.from_dict(data['stderr_diff']) if data.get('stderr_diff') else None,
            side_effect_diffs=[SideEffectDiff.from_dict(sed) for sed in data['side_effect_diffs']],
        )


@dataclass
class ComparisonResult:
    """Result of byte-by-byte output comparison."""
    test_vector_id: str
    comparison_timestamp: str
    match: bool
    return_value_match: bool
    stdout_match: bool
    stderr_match: bool
    side_effects_match: bool
    differences: Optional[DifferenceDetails]
    result_hash: str

    def to_json(self) -> str:
        """Serialize comparison result to JSON."""
        data = {
            'test_vector_id': self.test_vector_id,
            'comparison_timestamp': self.comparison_timestamp,
            'match': self.match,
            'return_value_match': self.return_value_match,
            'stdout_match': self.stdout_match,
            'stderr_match': self.stderr_match,
            'side_effects_match': self.side_effects_match,
            'differences': self.differences.to_dict() if self.differences else None,
            'result_hash': self.result_hash,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'ComparisonResult':
        """Deserialize comparison result from JSON."""
        data = json.loads(json_str)
        return cls(
            test_vector_id=data['test_vector_id'],
            comparison_timestamp=data['comparison_timestamp'],
            match=data['match'],
            return_value_match=data['return_value_match'],
            stdout_match=data['stdout_match'],
            stderr_match=data['stderr_match'],
            side_effects_match=data['side_effects_match'],
            differences=DifferenceDetails.from_dict(data['differences']) if data.get('differences') else None,
            result_hash=data['result_hash'],
        )


@dataclass
class DiscrepancyReport:
    """Report generated when outputs differ."""
    report_id: str
    generation_timestamp: str
    test_vector_id: str
    legacy_result_hash: str
    modern_result_hash: str
    comparison_result: ComparisonResult
    root_cause_analysis: Optional[str] = None

    def to_json(self) -> str:
        """Serialize discrepancy report to JSON."""
        data = {
            'report_id': self.report_id,
            'generation_timestamp': self.generation_timestamp,
            'test_vector_id': self.test_vector_id,
            'legacy_result_hash': self.legacy_result_hash,
            'modern_result_hash': self.modern_result_hash,
            'comparison_result': json.loads(self.comparison_result.to_json()),
            'root_cause_analysis': self.root_cause_analysis,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'DiscrepancyReport':
        """Deserialize discrepancy report from JSON."""
        data = json.loads(json_str)
        return cls(
            report_id=data['report_id'],
            generation_timestamp=data['generation_timestamp'],
            test_vector_id=data['test_vector_id'],
            legacy_result_hash=data['legacy_result_hash'],
            modern_result_hash=data['modern_result_hash'],
            comparison_result=ComparisonResult.from_json(json.dumps(data['comparison_result'])),
            root_cause_analysis=data.get('root_cause_analysis'),
        )

    def generate_html_report(self) -> str:
        """Generate human-readable HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Discrepancy Report {self.report_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #d32f2f; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                .match {{ color: #4caf50; }}
                .mismatch {{ color: #d32f2f; }}
                .hex {{ font-family: monospace; background: #f5f5f5; padding: 5px; }}
            </style>
        </head>
        <body>
            <h1>Behavioral Discrepancy Report</h1>
            <div class="section">
                <h2>Report Information</h2>
                <p><strong>Report ID:</strong> {self.report_id}</p>
                <p><strong>Generated:</strong> {self.generation_timestamp}</p>
                <p><strong>Test Vector ID:</strong> {self.test_vector_id}</p>
            </div>
            <div class="section">
                <h2>Comparison Results</h2>
                <p><strong>Overall Match:</strong> <span class="{'match' if self.comparison_result.match else 'mismatch'}">{self.comparison_result.match}</span></p>
                <p><strong>Return Value Match:</strong> <span class="{'match' if self.comparison_result.return_value_match else 'mismatch'}">{self.comparison_result.return_value_match}</span></p>
                <p><strong>Stdout Match:</strong> <span class="{'match' if self.comparison_result.stdout_match else 'mismatch'}">{self.comparison_result.stdout_match}</span></p>
                <p><strong>Stderr Match:</strong> <span class="{'match' if self.comparison_result.stderr_match else 'mismatch'}">{self.comparison_result.stderr_match}</span></p>
                <p><strong>Side Effects Match:</strong> <span class="{'match' if self.comparison_result.side_effects_match else 'mismatch'}">{self.comparison_result.side_effects_match}</span></p>
            </div>
            <div class="section">
                <h2>Result Hashes</h2>
                <p><strong>Legacy Result Hash:</strong> <span class="hex">{self.legacy_result_hash}</span></p>
                <p><strong>Modern Result Hash:</strong> <span class="hex">{self.modern_result_hash}</span></p>
            </div>
        """
        
        if self.root_cause_analysis:
            html += f"""
            <div class="section">
                <h2>Root Cause Analysis</h2>
                <p>{self.root_cause_analysis}</p>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        return html


@dataclass
class ArtifactMetadata:
    """Metadata for legacy or modern artifact."""
    identifier: str
    version: str
    sha256_hash: str
    s3_location: str
    creation_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'identifier': self.identifier,
            'version': self.version,
            'sha256_hash': self.sha256_hash,
            's3_location': self.s3_location,
            'creation_timestamp': self.creation_timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArtifactMetadata':
        """Create from dictionary."""
        return cls(
            identifier=data['identifier'],
            version=data['version'],
            sha256_hash=data['sha256_hash'],
            s3_location=data['s3_location'],
            creation_timestamp=data['creation_timestamp'],
        )


@dataclass
class CoverageReport:
    """Test coverage metrics."""
    branch_coverage_percent: float
    entry_points_covered: int
    total_entry_points: int
    uncovered_branches: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'branch_coverage_percent': self.branch_coverage_percent,
            'entry_points_covered': self.entry_points_covered,
            'total_entry_points': self.total_entry_points,
            'uncovered_branches': self.uncovered_branches,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoverageReport':
        """Create from dictionary."""
        return cls(
            branch_coverage_percent=data['branch_coverage_percent'],
            entry_points_covered=data['entry_points_covered'],
            total_entry_points=data['total_entry_points'],
            uncovered_branches=data['uncovered_branches'],
        )


@dataclass
class EquivalenceCertificate:
    """Certificate proving behavioral equivalence."""
    certificate_id: str
    generation_timestamp: str
    legacy_artifact: ArtifactMetadata
    modern_implementation: ArtifactMetadata
    total_test_vectors: int
    test_execution_start: str
    test_execution_end: str
    test_results_hash: str
    individual_test_hashes: List[str]
    random_seed: int
    coverage_report: CoverageReport

    def to_json(self) -> str:
        """Serialize certificate to JSON."""
        data = {
            'certificate_id': self.certificate_id,
            'generation_timestamp': self.generation_timestamp,
            'legacy_artifact': self.legacy_artifact.to_dict(),
            'modern_implementation': self.modern_implementation.to_dict(),
            'total_test_vectors': self.total_test_vectors,
            'test_execution_start': self.test_execution_start,
            'test_execution_end': self.test_execution_end,
            'test_results_hash': self.test_results_hash,
            'individual_test_hashes': self.individual_test_hashes,
            'random_seed': self.random_seed,
            'coverage_report': self.coverage_report.to_dict(),
        }
        return json.dumps(data, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> 'EquivalenceCertificate':
        """Deserialize certificate from JSON."""
        data = json.loads(json_str)
        return cls(
            certificate_id=data['certificate_id'],
            generation_timestamp=data['generation_timestamp'],
            legacy_artifact=ArtifactMetadata.from_dict(data['legacy_artifact']),
            modern_implementation=ArtifactMetadata.from_dict(data['modern_implementation']),
            total_test_vectors=data['total_test_vectors'],
            test_execution_start=data['test_execution_start'],
            test_execution_end=data['test_execution_end'],
            test_results_hash=data['test_results_hash'],
            individual_test_hashes=data['individual_test_hashes'],
            random_seed=data['random_seed'],
            coverage_report=CoverageReport.from_dict(data['coverage_report']),
        )


@dataclass
class SignedCertificate:
    """Cryptographically signed equivalence certificate."""
    certificate: EquivalenceCertificate
    signature: bytes
    signing_key_id: str
    signature_algorithm: str
    signing_timestamp: str

    def verify_signature(self, kms_client) -> bool:
        """Verify certificate signature using KMS."""
        # Recompute certificate hash
        certificate_json = self.certificate.to_json()
        certificate_bytes = certificate_json.encode('utf-8')
        certificate_hash = hashlib.sha256(certificate_bytes).digest()
        
        # Verify signature with KMS
        try:
            response = kms_client.verify(
                KeyId=self.signing_key_id,
                Message=certificate_hash,
                MessageType='DIGEST',
                Signature=self.signature,
                SigningAlgorithm=self.signature_algorithm
            )
            return response.get('SignatureValid', False)
        except Exception:
            return False

    def to_json(self) -> str:
        """Serialize signed certificate to JSON."""
        data = {
            'certificate': json.loads(self.certificate.to_json()),
            'signature': self.signature.hex(),
            'signing_key_id': self.signing_key_id,
            'signature_algorithm': self.signature_algorithm,
            'signing_timestamp': self.signing_timestamp,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'SignedCertificate':
        """Deserialize signed certificate from JSON."""
        data = json.loads(json_str)
        return cls(
            certificate=EquivalenceCertificate.from_json(json.dumps(data['certificate'])),
            signature=bytes.fromhex(data['signature']),
            signing_key_id=data['signing_key_id'],
            signature_algorithm=data['signature_algorithm'],
            signing_timestamp=data['signing_timestamp'],
        )

    def to_pem(self) -> str:
        """Export certificate in PEM format for regulatory submission."""
        import base64
        
        cert_json = self.to_json()
        cert_b64 = base64.b64encode(cert_json.encode('utf-8')).decode('utf-8')
        
        # Format as PEM with 64-character lines
        lines = [cert_b64[i:i+64] for i in range(0, len(cert_b64), 64)]
        
        pem = "-----BEGIN ROSETTA ZERO CERTIFICATE-----\n"
        pem += "\n".join(lines)
        pem += "\n-----END ROSETTA ZERO CERTIFICATE-----\n"
        
        return pem


@dataclass
class ComplianceReport:
    """Comprehensive compliance report for regulatory submission."""
    report_id: str
    generation_timestamp: str
    workflow_id: str
    
    # Test Results Summary
    total_test_vectors: int
    passed_tests: int
    failed_tests: int
    test_results_hash: str
    
    # Equivalence Certificate
    equivalence_certificate: Optional[SignedCertificate]
    
    # Discrepancy Reports (if any)
    discrepancy_reports: List[DiscrepancyReport]
    
    # Audit Log References
    audit_log_groups: List[str]
    audit_log_query_start: str
    audit_log_query_end: str
    
    # Artifacts
    legacy_artifact: ArtifactMetadata
    modern_implementation: ArtifactMetadata
    
    # Coverage
    coverage_report: CoverageReport
    
    # Compliance Status
    compliance_status: str  # "COMPLIANT" or "NON_COMPLIANT"
    compliance_notes: Optional[str] = None

    def to_json(self) -> str:
        """Serialize compliance report to JSON."""
        data = {
            'report_id': self.report_id,
            'generation_timestamp': self.generation_timestamp,
            'workflow_id': self.workflow_id,
            'total_test_vectors': self.total_test_vectors,
            'passed_tests': self.passed_tests,
            'failed_tests': self.failed_tests,
            'test_results_hash': self.test_results_hash,
            'equivalence_certificate': json.loads(self.equivalence_certificate.to_json()) if self.equivalence_certificate else None,
            'discrepancy_reports': [json.loads(dr.to_json()) for dr in self.discrepancy_reports],
            'audit_log_groups': self.audit_log_groups,
            'audit_log_query_start': self.audit_log_query_start,
            'audit_log_query_end': self.audit_log_query_end,
            'legacy_artifact': self.legacy_artifact.to_dict(),
            'modern_implementation': self.modern_implementation.to_dict(),
            'coverage_report': self.coverage_report.to_dict(),
            'compliance_status': self.compliance_status,
            'compliance_notes': self.compliance_notes,
        }
        return json.dumps(data, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> 'ComplianceReport':
        """Deserialize compliance report from JSON."""
        data = json.loads(json_str)
        return cls(
            report_id=data['report_id'],
            generation_timestamp=data['generation_timestamp'],
            workflow_id=data['workflow_id'],
            total_test_vectors=data['total_test_vectors'],
            passed_tests=data['passed_tests'],
            failed_tests=data['failed_tests'],
            test_results_hash=data['test_results_hash'],
            equivalence_certificate=SignedCertificate.from_json(json.dumps(data['equivalence_certificate'])) if data.get('equivalence_certificate') else None,
            discrepancy_reports=[DiscrepancyReport.from_json(json.dumps(dr)) for dr in data['discrepancy_reports']],
            audit_log_groups=data['audit_log_groups'],
            audit_log_query_start=data['audit_log_query_start'],
            audit_log_query_end=data['audit_log_query_end'],
            legacy_artifact=ArtifactMetadata.from_dict(data['legacy_artifact']),
            modern_implementation=ArtifactMetadata.from_dict(data['modern_implementation']),
            coverage_report=CoverageReport.from_dict(data['coverage_report']),
            compliance_status=data['compliance_status'],
            compliance_notes=data.get('compliance_notes'),
        )

    def generate_html_report(self) -> str:
        """Generate human-readable HTML compliance report for regulatory submission."""
        status_color = '#4caf50' if self.compliance_status == 'COMPLIANT' else '#d32f2f'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Rosetta Zero Compliance Report {self.report_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                h1 {{ color: #1976d2; border-bottom: 3px solid #1976d2; padding-bottom: 10px; }}
                h2 {{ color: #424242; border-bottom: 1px solid #ddd; padding-bottom: 5px; margin-top: 30px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; background: #fafafa; }}
                .status {{ font-size: 1.2em; font-weight: bold; color: {status_color}; }}
                .compliant {{ color: #4caf50; }}
                .non-compliant {{ color: #d32f2f; }}
                .hex {{ font-family: monospace; background: #f5f5f5; padding: 5px; word-break: break-all; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #1976d2; color: white; }}
                .summary-box {{ background: #e3f2fd; padding: 15px; border-left: 4px solid #1976d2; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Rosetta Zero Compliance Report</h1>
            
            <div class="summary-box">
                <h2>Executive Summary</h2>
                <p><strong>Report ID:</strong> {self.report_id}</p>
                <p><strong>Generated:</strong> {self.generation_timestamp}</p>
                <p><strong>Workflow ID:</strong> {self.workflow_id}</p>
                <p><strong>Compliance Status:</strong> <span class="status">{self.compliance_status}</span></p>
                {f'<p><strong>Notes:</strong> {self.compliance_notes}</p>' if self.compliance_notes else ''}
            </div>

            <div class="section">
                <h2>Test Results Summary</h2>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                    <tr>
                        <td>Total Test Vectors</td>
                        <td>{self.total_test_vectors:,}</td>
                    </tr>
                    <tr>
                        <td>Passed Tests</td>
                        <td class="compliant">{self.passed_tests:,}</td>
                    </tr>
                    <tr>
                        <td>Failed Tests</td>
                        <td class="{'compliant' if self.failed_tests == 0 else 'non-compliant'}">{self.failed_tests:,}</td>
                    </tr>
                    <tr>
                        <td>Pass Rate</td>
                        <td>{(self.passed_tests / self.total_test_vectors * 100) if self.total_test_vectors > 0 else 0:.2f}%</td>
                    </tr>
                    <tr>
                        <td>Test Results Hash (SHA-256)</td>
                        <td class="hex">{self.test_results_hash}</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h2>Coverage Report</h2>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                    </tr>
                    <tr>
                        <td>Branch Coverage</td>
                        <td>{self.coverage_report.branch_coverage_percent:.2f}%</td>
                    </tr>
                    <tr>
                        <td>Entry Points Covered</td>
                        <td>{self.coverage_report.entry_points_covered} / {self.coverage_report.total_entry_points}</td>
                    </tr>
                    <tr>
                        <td>Uncovered Branches</td>
                        <td>{len(self.coverage_report.uncovered_branches)}</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h2>Artifacts</h2>
                <h3>Legacy Artifact</h3>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
                    <tr><td>Identifier</td><td>{self.legacy_artifact.identifier}</td></tr>
                    <tr><td>Version</td><td>{self.legacy_artifact.version}</td></tr>
                    <tr><td>SHA-256 Hash</td><td class="hex">{self.legacy_artifact.sha256_hash}</td></tr>
                    <tr><td>S3 Location</td><td>{self.legacy_artifact.s3_location}</td></tr>
                    <tr><td>Creation Timestamp</td><td>{self.legacy_artifact.creation_timestamp}</td></tr>
                </table>

                <h3>Modern Implementation</h3>
                <table>
                    <tr><th>Property</th><th>Value</th></tr>
                    <tr><td>Identifier</td><td>{self.modern_implementation.identifier}</td></tr>
                    <tr><td>Version</td><td>{self.modern_implementation.version}</td></tr>
                    <tr><td>SHA-256 Hash</td><td class="hex">{self.modern_implementation.sha256_hash}</td></tr>
                    <tr><td>S3 Location</td><td>{self.modern_implementation.s3_location}</td></tr>
                    <tr><td>Creation Timestamp</td><td>{self.modern_implementation.creation_timestamp}</td></tr>
                </table>
            </div>

            <div class="section">
                <h2>Equivalence Certificate</h2>
        """
        
        if self.equivalence_certificate:
            cert = self.equivalence_certificate.certificate
            html += f"""
                <p><strong>Certificate ID:</strong> {cert.certificate_id}</p>
                <p><strong>Generated:</strong> {cert.generation_timestamp}</p>
                <p><strong>Test Execution Period:</strong> {cert.test_execution_start} to {cert.test_execution_end}</p>
                <p><strong>Random Seed:</strong> {cert.random_seed}</p>
                <p><strong>Signing Key ID:</strong> {self.equivalence_certificate.signing_key_id}</p>
                <p><strong>Signature Algorithm:</strong> {self.equivalence_certificate.signature_algorithm}</p>
                <p><strong>Signing Timestamp:</strong> {self.equivalence_certificate.signing_timestamp}</p>
                <p><strong>Signature (hex):</strong> <span class="hex">{self.equivalence_certificate.signature.hex()}</span></p>
            """
        else:
            html += "<p class='non-compliant'>No equivalence certificate available (tests failed)</p>"
        
        html += """
            </div>

            <div class="section">
                <h2>Discrepancy Reports</h2>
        """
        
        if self.discrepancy_reports:
            html += f"<p class='non-compliant'><strong>Total Discrepancies:</strong> {len(self.discrepancy_reports)}</p>"
            html += "<table><tr><th>Report ID</th><th>Test Vector ID</th><th>Timestamp</th></tr>"
            for dr in self.discrepancy_reports:
                html += f"<tr><td>{dr.report_id}</td><td>{dr.test_vector_id}</td><td>{dr.generation_timestamp}</td></tr>"
            html += "</table>"
        else:
            html += "<p class='compliant'>No discrepancies detected - all tests passed</p>"
        
        html += """
            </div>

            <div class="section">
                <h2>Audit Log References</h2>
                <p><strong>Query Period:</strong> {self.audit_log_query_start} to {self.audit_log_query_end}</p>
                <p><strong>CloudWatch Log Groups:</strong></p>
                <ul>
        """
        
        for log_group in self.audit_log_groups:
            html += f"<li>{log_group}</li>"
        
        html += """
                </ul>
                <p><em>All system decisions and operations are logged to these CloudWatch Log Groups with 7-year retention for regulatory compliance.</em></p>
            </div>

            <div class="section">
                <h2>Regulatory Compliance Statement</h2>
        """
        
        if self.compliance_status == 'COMPLIANT':
            html += """
                <p class="compliant">This report certifies that the modern implementation has been verified to be behaviorally equivalent 
                to the legacy system through comprehensive adversarial testing. All test vectors passed, demonstrating exact 
                byte-by-byte output matching across all entry points and side effects.</p>
                <p>The equivalence certificate has been cryptographically signed using AWS KMS and can be independently verified.</p>
            """
        else:
            html += """
                <p class="non-compliant">This report indicates that behavioral discrepancies were detected between the legacy 
                system and modern implementation. The system has halted further processing pending investigation and correction 
                of the identified discrepancies.</p>
                <p>No equivalence certificate has been issued. Refer to the discrepancy reports for detailed analysis.</p>
            """
        
        html += """
            </div>

            <div class="section">
                <h2>Document Integrity</h2>
                <p>This compliance report is generated by Rosetta Zero, an autonomous legacy code modernization system with 
                cryptographic proof of behavioral equivalence.</p>
                <p><strong>Report Hash (SHA-256):</strong> <span class="hex">{report_hash}</span></p>
                <p><em>This hash can be used to verify the integrity of this report.</em></p>
            </div>
        </body>
        </html>
        """.format(report_hash=hashlib.sha256(self.to_json().encode('utf-8')).hexdigest())
        
        return html
