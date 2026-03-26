"""
Unit tests for Ingestion Engine.

**Validates: Requirements 1.5, 1.6, 1.7**

Tests:
- Artifact ingestion with valid COBOL, FORTRAN, and binary files
- PII detection and redaction
- Logic Map extraction and validation
- Error handling for invalid artifacts
"""

import json
import hashlib
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from io import BytesIO

import pytest
import boto3
from botocore.exceptions import ClientError

from rosetta_zero.lambdas.ingestion_engine.ingestion import (
    IngestionEngine,
    IngestionResult,
)
from rosetta_zero.lambdas.ingestion_engine.pii_scanner import (
    PIIScanner,
    PIIFinding,
)
from rosetta_zero.lambdas.ingestion_engine.logic_map_extractor import (
    LogicMapExtractor,
)
from rosetta_zero.lambdas.ingestion_engine.ears_generator import (
    EARSGenerator,
)
from rosetta_zero.models import LogicMap


# Sample artifacts for testing

SAMPLE_COBOL_CODE = b"""
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 EMPLOYEE-RECORD.
          05 EMP-ID PIC 9(6).
          05 EMP-NAME PIC X(30).
          05 EMP-SALARY PIC 9(7)V99.
       
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           DISPLAY "Processing payroll".
           STOP RUN.
"""

SAMPLE_FORTRAN_CODE = b"""
      PROGRAM CALCULATE
      IMPLICIT NONE
      REAL :: X, Y, RESULT
      
      X = 10.0
      Y = 20.0
      RESULT = X + Y
      
      PRINT *, 'Result:', RESULT
      END PROGRAM CALCULATE
"""

SAMPLE_BINARY_DATA = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100


class TestIngestionEngine:
    """Test Ingestion Engine with valid artifacts."""
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create mock Bedrock client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_macie_client(self):
        """Create mock Macie client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def ingestion_engine(self, mock_s3_client, mock_bedrock_client, mock_macie_client):
        """Create IngestionEngine instance with mocked clients."""
        with patch('rosetta_zero.lambdas.ingestion_engine.ingestion.boto3') as mock_boto3:
            mock_boto3.client.side_effect = lambda service, **kwargs: {
                's3': mock_s3_client,
                'bedrock-runtime': mock_bedrock_client,
                'macie2': mock_macie_client,
            }[service]
            
            engine = IngestionEngine(
                region='us-east-1',
                logic_maps_bucket='test-logic-maps',
                ears_bucket='test-ears',
                kms_key_id='test-kms-key',
                pii_reports_bucket='test-pii-reports',
            )
            
            return engine
    
    def test_ingest_cobol_artifact(self, ingestion_engine, mock_s3_client, mock_bedrock_client):
        """
        Test artifact ingestion with valid COBOL file.
        
        Validates: Requirement 1.5
        """
        # Setup mock S3 response
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(SAMPLE_COBOL_CODE)
        }
        
        # Setup mock Bedrock response
        mock_logic_map = self._create_mock_logic_map_response()
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_logic_map).encode('utf-8'))
        }
        
        # Mock PII scanner to return no findings
        with patch.object(ingestion_engine.pii_scanner, 'scan_artifact', return_value=[]):
            # Execute ingestion
            result = ingestion_engine.ingest_artifact(
                s3_bucket='test-bucket',
                s3_key='artifacts/cobol/payroll.cbl',
                artifact_type='COBOL',
            )
        
        # Verify result
        assert isinstance(result, IngestionResult)
        assert result.artifact_id is not None
        assert result.artifact_hash.startswith('sha256:')
        assert result.ingestion_timestamp is not None
        assert result.logic_map_s3_key is not None
        assert result.ears_document_s3_key is not None
        
        # Verify S3 get_object was called
        mock_s3_client.get_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='artifacts/cobol/payroll.cbl'
        )
        
        # Verify Bedrock was invoked
        assert mock_bedrock_client.invoke_model.called
    
    def test_ingest_fortran_artifact(self, ingestion_engine, mock_s3_client, mock_bedrock_client):
        """
        Test artifact ingestion with valid FORTRAN file.
        
        Validates: Requirement 1.6
        """
        # Setup mock S3 response
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(SAMPLE_FORTRAN_CODE)
        }
        
        # Setup mock Bedrock response
        mock_logic_map = self._create_mock_logic_map_response()
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_logic_map).encode('utf-8'))
        }
        
        # Mock PII scanner
        with patch.object(ingestion_engine.pii_scanner, 'scan_artifact', return_value=[]):
            result = ingestion_engine.ingest_artifact(
                s3_bucket='test-bucket',
                s3_key='artifacts/fortran/calculate.f90',
                artifact_type='FORTRAN',
            )
        
        assert isinstance(result, IngestionResult)
        assert result.artifact_hash.startswith('sha256:')
    
    def test_ingest_binary_artifact(self, ingestion_engine, mock_s3_client, mock_bedrock_client):
        """
        Test artifact ingestion with mainframe binary file.
        
        Validates: Requirement 1.7
        """
        # Setup mock S3 response
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(SAMPLE_BINARY_DATA)
        }
        
        # Setup mock Bedrock response
        mock_logic_map = self._create_mock_logic_map_response()
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_logic_map).encode('utf-8'))
        }
        
        # Mock PII scanner
        with patch.object(ingestion_engine.pii_scanner, 'scan_artifact', return_value=[]):
            result = ingestion_engine.ingest_artifact(
                s3_bucket='test-bucket',
                s3_key='artifacts/binary/mainframe.bin',
                artifact_type='MAINFRAME_BINARY',
            )
        
        assert isinstance(result, IngestionResult)
        assert result.artifact_hash.startswith('sha256:')
    
    def test_artifact_hash_generation(self, ingestion_engine):
        """Test SHA-256 hash generation for artifact integrity."""
        content = b"test content"
        expected_hash = f"sha256:{hashlib.sha256(content).hexdigest()}"
        
        actual_hash = ingestion_engine._generate_hash(content)
        
        assert actual_hash == expected_hash
    
    def test_pii_detection_and_redaction(self, ingestion_engine, mock_s3_client, mock_bedrock_client):
        """
        Test PII detection and redaction during ingestion.
        
        Validates: Requirements 20.1, 20.2
        """
        # Artifact with PII
        artifact_with_pii = b"Employee SSN: 123-45-6789"
        
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(artifact_with_pii)
        }
        
        # Mock PII findings
        pii_findings = [
            PIIFinding(
                finding_type='SSN',
                location=14,
                length=11,
                confidence='HIGH'
            )
        ]
        
        # Mock Bedrock response
        mock_logic_map = self._create_mock_logic_map_response()
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_logic_map).encode('utf-8'))
        }
        
        # Mock PII scanner to return findings
        with patch.object(ingestion_engine.pii_scanner, 'scan_artifact', return_value=pii_findings):
            with patch.object(ingestion_engine.pii_scanner, 'redact_pii') as mock_redact:
                mock_redact.return_value = b"Employee SSN: [REDACTED-SSN]"
                
                result = ingestion_engine.ingest_artifact(
                    s3_bucket='test-bucket',
                    s3_key='artifacts/cobol/employee.cbl',
                    artifact_type='COBOL',
                )
                
                # Verify PII scanner was called
                ingestion_engine.pii_scanner.scan_artifact.assert_called_once()
                
                # Verify redaction was called
                mock_redact.assert_called_once()
                assert mock_redact.call_args[1]['findings'] == pii_findings
    
    def test_error_handling_invalid_artifact(self, ingestion_engine, mock_s3_client):
        """
        Test error handling for invalid artifacts.
        
        Validates: Error handling requirements
        """
        # Mock S3 to raise error
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )
        
        # Should raise error
        with pytest.raises(ClientError):
            ingestion_engine.ingest_artifact(
                s3_bucket='test-bucket',
                s3_key='artifacts/invalid.cbl',
                artifact_type='COBOL',
            )
    
    def test_error_handling_bedrock_throttling(self, ingestion_engine, mock_s3_client, mock_bedrock_client):
        """Test error handling for Bedrock throttling."""
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(SAMPLE_COBOL_CODE)
        }
        
        # Mock Bedrock to raise throttling error
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'ServiceName': 'bedrock-runtime'}
            },
            'InvokeModel'
        )
        
        with patch.object(ingestion_engine.pii_scanner, 'scan_artifact', return_value=[]):
            # Should raise throttling error (will be retried by decorator)
            with pytest.raises(ClientError):
                ingestion_engine.ingest_artifact(
                    s3_bucket='test-bucket',
                    s3_key='artifacts/cobol/payroll.cbl',
                    artifact_type='COBOL',
                )
    
    def _create_mock_logic_map_response(self):
        """Create mock Bedrock response with Logic Map."""
        return {
            'content': [{
                'text': json.dumps({
                    'artifact_id': 'test-artifact',
                    'artifact_version': '1.0',
                    'extraction_timestamp': datetime.utcnow().isoformat(),
                    'entry_points': [{
                        'name': 'MAIN-LOGIC',
                        'parameters': [],
                        'return_type': 'INTEGER',
                        'description': 'Main entry point'
                    }],
                    'data_structures': [],
                    'control_flow': {
                        'nodes': [{
                            'node_id': 'node1',
                            'type': 'BASIC_BLOCK',
                            'description': 'Main block'
                        }],
                        'edges': []
                    },
                    'dependencies': [],
                    'side_effects': [],
                    'arithmetic_precision': {
                        'fixed_point_operations': [],
                        'floating_point_precision': {},
                        'rounding_modes': {}
                    }
                })
            }],
            'usage': {
                'input_tokens': 100,
                'output_tokens': 200
            }
        }


class TestPIIScanner:
    """Test PII Scanner functionality."""
    
    @pytest.fixture
    def mock_s3_client(self):
        return Mock()
    
    @pytest.fixture
    def mock_macie_client(self):
        return Mock()
    
    @pytest.fixture
    def pii_scanner(self, mock_s3_client, mock_macie_client):
        return PIIScanner(
            region='us-east-1',
            s3_client=mock_s3_client,
            macie_client=mock_macie_client,
            pii_reports_bucket='test-pii-reports',
        )
    
    def test_redact_pii_single_finding(self, pii_scanner):
        """Test PII redaction with single finding."""
        content = b"SSN: 123-45-6789"
        findings = [
            PIIFinding(
                finding_type='SSN',
                location=5,
                length=11,
                confidence='HIGH'
            )
        ]
        
        redacted = pii_scanner.redact_pii(content, findings, 'test-artifact')
        
        assert b'[REDACTED-SSN]' in redacted
        assert b'123-45-6789' not in redacted
    
    def test_redact_pii_multiple_findings(self, pii_scanner):
        """Test PII redaction with multiple findings."""
        content = b"SSN: 123-45-6789, Email: test@example.com"
        findings = [
            PIIFinding(finding_type='SSN', location=5, length=11, confidence='HIGH'),
            PIIFinding(finding_type='EMAIL_ADDRESS', location=25, length=16, confidence='HIGH'),
        ]
        
        redacted = pii_scanner.redact_pii(content, findings, 'test-artifact')
        
        assert b'[REDACTED-SSN]' in redacted
        assert b'[REDACTED-EMAIL_ADDRESS]' in redacted
        assert b'123-45-6789' not in redacted
        assert b'test@example.com' not in redacted
    
    def test_redact_pii_no_findings(self, pii_scanner):
        """Test PII redaction with no findings returns original content."""
        content = b"No PII here"
        findings = []
        
        redacted = pii_scanner.redact_pii(content, findings, 'test-artifact')
        
        assert redacted == content


class TestLogicMapExtractor:
    """Test Logic Map Extractor functionality."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        return Mock()
    
    @pytest.fixture
    def mock_s3_client(self):
        return Mock()
    
    @pytest.fixture
    def logic_map_extractor(self, mock_bedrock_client, mock_s3_client):
        return LogicMapExtractor(
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            logic_maps_bucket='test-logic-maps',
        )
    
    def test_extract_logic_map_from_cobol(self, logic_map_extractor, mock_bedrock_client, mock_s3_client):
        """Test Logic Map extraction from COBOL code."""
        # Mock Bedrock response
        mock_response = {
            'content': [{
                'text': json.dumps({
                    'artifact_id': 'test-artifact',
                    'artifact_version': '1.0',
                    'extraction_timestamp': datetime.utcnow().isoformat(),
                    'entry_points': [{
                        'name': 'MAIN-LOGIC',
                        'parameters': [],
                        'return_type': 'VOID',
                        'description': 'Main entry point'
                    }],
                    'data_structures': [{
                        'name': 'EMPLOYEE-RECORD',
                        'fields': [
                            {'name': 'EMP-ID', 'type': 'INTEGER', 'size_bytes': 6, 'offset': 0},
                            {'name': 'EMP-NAME', 'type': 'STRING', 'size_bytes': 30, 'offset': 6},
                        ],
                        'size_bytes': 36,
                        'alignment': 1
                    }],
                    'control_flow': {
                        'nodes': [{'id': 'node1', 'type': 'BASIC_BLOCK', 'description': 'Main'}],
                        'edges': []
                    },
                    'dependencies': [],
                    'side_effects': [],
                    'arithmetic_precision': {
                        'fixed_point_operations': [],
                        'floating_point_precision': {},
                        'rounding_modes': {}
                    }
                })
            }],
            'usage': {'input_tokens': 100, 'output_tokens': 200}
        }
        
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_response).encode('utf-8'))
        }
        
        # Extract Logic Map
        logic_map = logic_map_extractor.extract_logic_map(
            artifact_content=SAMPLE_COBOL_CODE,
            artifact_id='test-artifact',
            artifact_type='COBOL',
        )
        
        # Verify Logic Map structure
        assert isinstance(logic_map, LogicMap)
        assert len(logic_map.entry_points) > 0
        assert logic_map.control_flow is not None
    
    def test_validate_logic_map_missing_entry_points(self, logic_map_extractor):
        """Test Logic Map validation fails when entry points are missing."""
        # Create invalid Logic Map (no entry points)
        with patch('rosetta_zero.models.LogicMap') as MockLogicMap:
            invalid_logic_map = Mock()
            invalid_logic_map.entry_points = []
            invalid_logic_map.control_flow = Mock()
            invalid_logic_map.control_flow.nodes = [Mock()]
            
            with pytest.raises(ValueError) as exc_info:
                logic_map_extractor._validate_logic_map(invalid_logic_map, 'test-artifact')
            
            assert 'entry points' in str(exc_info.value).lower()
    
    def test_validate_logic_map_missing_control_flow(self, logic_map_extractor):
        """Test Logic Map validation fails when control flow is missing."""
        invalid_logic_map = Mock()
        invalid_logic_map.entry_points = [Mock()]
        invalid_logic_map.control_flow = None
        
        with pytest.raises(ValueError) as exc_info:
            logic_map_extractor._validate_logic_map(invalid_logic_map, 'test-artifact')
        
        assert 'control flow' in str(exc_info.value).lower()
    
    def test_extract_json_from_markdown(self, logic_map_extractor):
        """Test JSON extraction from markdown code blocks."""
        # JSON wrapped in markdown
        content_with_markdown = '```json\n{"key": "value"}\n```'
        extracted = logic_map_extractor._extract_json(content_with_markdown)
        assert extracted == '{"key": "value"}'
        
        # JSON without markdown
        content_plain = '{"key": "value"}'
        extracted = logic_map_extractor._extract_json(content_plain)
        assert extracted == '{"key": "value"}'
    
    def test_construct_prompt_for_cobol(self, logic_map_extractor):
        """Test prompt construction for COBOL artifact."""
        prompt = logic_map_extractor._construct_prompt(SAMPLE_COBOL_CODE, 'COBOL')
        
        assert 'COBOL' in prompt
        assert 'Logic Map' in prompt
        assert 'entry points' in prompt.lower()
        assert 'data structures' in prompt.lower()
        assert 'control flow' in prompt.lower()
    
    def test_construct_prompt_for_binary(self, logic_map_extractor):
        """Test prompt construction for binary artifact."""
        prompt = logic_map_extractor._construct_prompt(SAMPLE_BINARY_DATA, 'MAINFRAME_BINARY')
        
        assert 'MAINFRAME_BINARY' in prompt
        assert '[Binary content' in prompt


class TestEARSGenerator:
    """Test EARS Generator functionality."""
    
    @pytest.fixture
    def mock_s3_client(self):
        return Mock()
    
    @pytest.fixture
    def ears_generator(self, mock_s3_client):
        return EARSGenerator(
            s3_client=mock_s3_client,
            ears_bucket='test-ears',
        )
    
    @pytest.fixture
    def sample_logic_map(self):
        """Create sample Logic Map for testing."""
        from rosetta_zero.models.logic_map import (
            LogicMap, EntryPoint, Parameter, DataStructure, Field,
            ControlFlowGraph, ControlFlowNode, SideEffect, PrecisionConfig,
            DataType, SideEffectType, Dependency
        )
        
        return LogicMap(
            artifact_id='test-artifact',
            artifact_version='1.0',
            extraction_timestamp=datetime.utcnow().isoformat(),
            entry_points=[
                EntryPoint(
                    name='CALCULATE-PAYROLL',
                    parameters=[
                        Parameter(name='employee_id', type=DataType.INTEGER, description='Employee ID'),
                        Parameter(name='hours_worked', type=DataType.DECIMAL, description='Hours worked'),
                    ],
                    return_type=DataType.DECIMAL,
                    description='Calculate employee payroll'
                )
            ],
            data_structures=[
                DataStructure(
                    name='EMPLOYEE-RECORD',
                    fields=[
                        Field(name='EMP-ID', type=DataType.INTEGER, size_bytes=4, offset=0, description='Employee ID'),
                        Field(name='EMP-NAME', type=DataType.STRING, size_bytes=30, offset=4, description='Employee name'),
                    ],
                    size_bytes=34,
                    alignment=4
                )
            ],
            control_flow=ControlFlowGraph(
                nodes=[
                    ControlFlowNode(node_id='node1', type='BASIC_BLOCK', description='Main logic')
                ],
                edges=[]
            ),
            dependencies=[],
            side_effects=[
                SideEffect(
                    operation_type=SideEffectType.FILE_IO,
                    scope='payroll.dat',
                    description='Write payroll data to file',
                    timing_requirements=None
                )
            ],
            arithmetic_precision=PrecisionConfig(
                fixed_point_operations=[],
                floating_point_precision={},
                rounding_modes={}
            )
        )
    
    def test_generate_ears_requirements(self, ears_generator, sample_logic_map, mock_s3_client):
        """Test EARS requirements generation from Logic Map."""
        s3_key = ears_generator.generate_ears_requirements(
            logic_map=sample_logic_map,
            artifact_id='test-artifact',
        )
        
        # Verify S3 key format
        assert s3_key.startswith('ears-requirements/')
        assert s3_key.endswith('.md')
        
        # Verify S3 put_object was called
        assert mock_s3_client.put_object.called
        call_args = mock_s3_client.put_object.call_args
        
        # Verify bucket and key
        assert call_args[1]['Bucket'] == 'test-ears'
        assert call_args[1]['Key'] == s3_key
        
        # Verify content
        content = call_args[1]['Body'].decode('utf-8')
        assert 'EARS Requirements Document' in content
        assert 'SHALL' in content
        assert 'WHEN' in content or 'THE' in content
    
    def test_ears_document_contains_entry_points(self, ears_generator, sample_logic_map):
        """Test EARS document contains entry point requirements."""
        document = ears_generator._generate_document(sample_logic_map, 'test-artifact')
        
        assert 'CALCULATE-PAYROLL' in document
        assert 'Entry Point Requirements' in document
        assert 'SHALL' in document
    
    def test_ears_document_contains_side_effects(self, ears_generator, sample_logic_map):
        """Test EARS document contains side effect requirements."""
        document = ears_generator._generate_document(sample_logic_map, 'test-artifact')
        
        assert 'Side Effect Requirements' in document
        assert 'FILE_IO' in document
        assert 'payroll.dat' in document
    
    def test_ears_document_contains_data_structures(self, ears_generator, sample_logic_map):
        """Test EARS document contains data structure requirements."""
        document = ears_generator._generate_document(sample_logic_map, 'test-artifact')
        
        assert 'Data Structure Requirements' in document
        assert 'EMPLOYEE-RECORD' in document
    
    def test_ears_entry_point_requirements_format(self, ears_generator, sample_logic_map):
        """Test EARS entry point requirements use correct format."""
        entry_point = sample_logic_map.entry_points[0]
        lines = ears_generator._generate_entry_point_requirements(entry_point, 1)
        
        requirements_text = '\n'.join(lines)
        
        # Should contain EARS pattern
        assert 'WHEN' in requirements_text
        assert 'SHALL' in requirements_text
        assert entry_point.name in requirements_text
    
    def test_ears_side_effect_requirements_format(self, ears_generator, sample_logic_map):
        """Test EARS side effect requirements use correct format."""
        side_effect = sample_logic_map.side_effects[0]
        lines = ears_generator._generate_side_effect_requirements(side_effect, 1)
        
        requirements_text = '\n'.join(lines)
        
        # Should contain EARS pattern
        assert 'WHEN' in requirements_text
        assert 'SHALL' in requirements_text
        assert side_effect.operation_type in requirements_text


class TestErrorHandling:
    """Test error handling and retry logic."""
    
    def test_aws_500_error_detection(self):
        """Test AWS 500-level error detection."""
        from rosetta_zero.lambdas.ingestion_engine.error_handler import AWS500Error
        
        error = AWS500Error(
            service='bedrock-runtime',
            operation='InvokeModel',
            error_code='InternalServerError',
            message='Internal error'
        )
        
        assert error.service == 'bedrock-runtime'
        assert error.operation == 'InvokeModel'
        assert error.error_code == 'InternalServerError'
    
    def test_bedrock_throttling_error(self):
        """Test Bedrock throttling error classification."""
        from rosetta_zero.lambdas.ingestion_engine.error_handler import BedrockThrottlingError
        
        error = BedrockThrottlingError('Rate exceeded')
        assert str(error) == 'Rate exceeded'
    
    def test_macie_error(self):
        """Test Macie error classification."""
        from rosetta_zero.lambdas.ingestion_engine.error_handler import MacieError
        
        error = MacieError('Macie service unavailable')
        assert str(error) == 'Macie service unavailable'


class TestIntegration:
    """Integration tests for complete ingestion workflow."""
    
    @pytest.fixture
    def mock_aws_services(self):
        """Mock all AWS services for integration testing."""
        with patch('boto3.client') as mock_client:
            # Create mock clients
            mock_s3 = Mock()
            mock_bedrock = Mock()
            mock_macie = Mock()
            
            def client_factory(service, **kwargs):
                if service == 's3':
                    return mock_s3
                elif service == 'bedrock-runtime':
                    return mock_bedrock
                elif service == 'macie2':
                    return mock_macie
                elif service == 'sts':
                    sts = Mock()
                    sts.get_caller_identity.return_value = {'Account': '123456789012'}
                    return sts
                elif service == 'ssm':
                    ssm = Mock()
                    ssm.get_parameter.return_value = {
                        'Parameter': {'Value': 'arn:aws:sns:us-east-1:123456789012:alerts'}
                    }
                    return ssm
                return Mock()
            
            mock_client.side_effect = client_factory
            
            yield {
                's3': mock_s3,
                'bedrock': mock_bedrock,
                'macie': mock_macie,
            }
    
    def test_complete_ingestion_workflow(self, mock_aws_services):
        """
        Test complete ingestion workflow from artifact to EARS document.
        
        Validates: Requirements 1.5, 1.6, 1.7
        """
        # Setup S3 mock
        mock_aws_services['s3'].get_object.return_value = {
            'Body': BytesIO(SAMPLE_COBOL_CODE)
        }
        
        # Setup Bedrock mock
        mock_logic_map_response = {
            'content': [{
                'text': json.dumps({
                    'artifact_id': 'test',
                    'artifact_version': '1.0',
                    'extraction_timestamp': datetime.utcnow().isoformat(),
                    'entry_points': [{'name': 'MAIN', 'parameters': [], 'return_type': 'INTEGER', 'description': 'Main'}],
                    'data_structures': [],
                    'control_flow': {'nodes': [{'node_id': 'n1', 'type': 'BASIC_BLOCK', 'description': 'Main'}], 'edges': []},
                    'dependencies': [],
                    'side_effects': [],
                    'arithmetic_precision': {'fixed_point_operations': [], 'floating_point_precision': {}, 'rounding_modes': {}}
                })
            }],
            'usage': {'input_tokens': 100, 'output_tokens': 200}
        }
        mock_aws_services['bedrock'].invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_logic_map_response).encode('utf-8'))
        }
        
        # Setup Macie mock (no PII)
        mock_aws_services['macie'].create_classification_job.return_value = {
            'jobId': 'test-job-id'
        }
        mock_aws_services['macie'].describe_classification_job.return_value = {
            'jobStatus': 'COMPLETE'
        }
        mock_aws_services['macie'].list_findings.return_value = {
            'findingIds': []
        }
        
        # Create engine
        engine = IngestionEngine(
            region='us-east-1',
            logic_maps_bucket='test-logic-maps',
            ears_bucket='test-ears',
            kms_key_id='test-kms-key',
        )
        
        # Execute ingestion
        result = engine.ingest_artifact(
            s3_bucket='test-bucket',
            s3_key='artifacts/cobol/test.cbl',
            artifact_type='COBOL',
        )
        
        # Verify complete workflow
        assert result.artifact_id is not None
        assert result.artifact_hash.startswith('sha256:')
        assert result.logic_map_s3_key is not None
        assert result.ears_document_s3_key is not None
        
        # Verify all services were called
        assert mock_aws_services['s3'].get_object.called
        assert mock_aws_services['bedrock'].invoke_model.called
        assert mock_aws_services['s3'].put_object.call_count >= 2  # Logic Map + EARS


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
