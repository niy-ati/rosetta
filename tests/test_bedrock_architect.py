"""
Unit tests for Bedrock Architect.

**Validates: Requirements 6.1-6.8**

Tests:
- Lambda code synthesis from Logic Maps
- Arithmetic precision preservation
- Faithful transpilation constraints
- CDK infrastructure generation
"""

import json
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, call
from io import BytesIO

import pytest
import boto3
from botocore.exceptions import ClientError

from rosetta_zero.lambdas.bedrock_architect.synthesis import (
    BedrockArchitect,
    SynthesisResult,
)
from rosetta_zero.lambdas.bedrock_architect.precision import (
    preserve_arithmetic_precision,
)
from rosetta_zero.lambdas.bedrock_architect.faithful_transpilation import (
    validate_faithful_transpilation,
    FaithfulTranspilationError,
)
from rosetta_zero.lambdas.bedrock_architect.cdk_generator import (
    generate_cdk_infrastructure,
)
from rosetta_zero.models.logic_map import (
    LogicMap, EntryPoint, Parameter, DataStructure, Field,
    ControlFlowGraph, ControlFlowNode, SideEffect, PrecisionConfig,
    DataType, SideEffectType, Dependency, FixedPointOp, RoundingMode,
)


# Sample Logic Maps for testing

def create_sample_logic_map(
    artifact_id='test-artifact',
    with_side_effects=False,
    with_precision=False,
) -> LogicMap:
    """Create a sample Logic Map for testing."""
    side_effects = []
    if with_side_effects:
        side_effects = [
            SideEffect(
                operation_type=SideEffectType.FILE_IO,
                scope='output.dat',
                description='Write output to file',
                timing_requirements=None
            ),
            SideEffect(
                operation_type=SideEffectType.DATABASE,
                scope='employee_table',
                description='Update employee records',
                timing_requirements=None
            ),
        ]
    
    precision_config = PrecisionConfig(
        fixed_point_operations=[],
        floating_point_precision={},
        rounding_modes={}
    )
    
    if with_precision:
        precision_config = PrecisionConfig(
            fixed_point_operations=[
                FixedPointOp(
                    operation='SALARY_CALCULATION',
                    precision=10,
                    scale=2,
                    description='Calculate salary with 2 decimal places'
                )
            ],
            floating_point_precision={
                'INTEREST_RATE': 64
            },
            rounding_modes={
                'SALARY_CALCULATION': RoundingMode.ROUND_HALF_UP
            }
        )
    
    return LogicMap(
        artifact_id=artifact_id,
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
        dependencies=[
            Dependency(type='COBOL', name='COPY-BOOK', description='Employee copy book')
        ],
        side_effects=side_effects,
        arithmetic_precision=precision_config
    )


SAMPLE_GENERATED_LAMBDA_CODE = '''
import json
from decimal import Decimal, getcontext, ROUND_HALF_UP
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()

@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda handler for CALCULATE-PAYROLL."""
    employee_id = event.get('employee_id')
    hours_worked = Decimal(str(event.get('hours_worked')))
    
    # Calculate payroll with fixed-point precision
    getcontext().prec = 10
    hourly_rate = Decimal('25.50')
    salary = hours_worked * hourly_rate
    salary = salary.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'employee_id': employee_id,
            'salary': str(salary)
        })
    }

def calculate_payroll(employee_id, hours_worked):
    """Calculate employee payroll."""
    getcontext().prec = 10
    hourly_rate = Decimal('25.50')
    salary = Decimal(str(hours_worked)) * hourly_rate
    return salary.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
'''


class TestBedrockArchitect:
    """Test Bedrock Architect Lambda synthesis."""
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create mock Bedrock Runtime client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock Bedrock Agent Runtime client."""
        client = Mock()
        return client
    
    @pytest.fixture
    def bedrock_architect(self, mock_s3_client, mock_bedrock_client, mock_bedrock_agent_client):
        """Create BedrockArchitect instance with mocked clients."""
        with patch('rosetta_zero.lambdas.bedrock_architect.synthesis.boto3') as mock_boto3:
            mock_boto3.client.side_effect = lambda service, **kwargs: {
                's3': mock_s3_client,
                'bedrock-runtime': mock_bedrock_client,
                'bedrock-agent-runtime': mock_bedrock_agent_client,
            }[service]
            
            architect = BedrockArchitect(
                region='us-east-1',
                modern_implementations_bucket='test-modern-impl',
                cdk_infrastructure_bucket='test-cdk-infra',
                kms_key_id='test-kms-key',
                bedrock_model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',
                cobol_kb_id='test-cobol-kb',
                fortran_kb_id='test-fortran-kb',
                mainframe_kb_id='test-mainframe-kb',
            )
            
            return architect
    
    def test_synthesize_lambda_from_logic_map(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test Lambda code synthesis from Logic Map.
        
        Validates: Requirement 6.1
        """
        # Setup mock S3 to return Logic Map
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        # Setup mock Bedrock to return generated Lambda code
        mock_bedrock_response = {
            'content': [{
                'text': SAMPLE_GENERATED_LAMBDA_CODE
            }],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        # Execute synthesis
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Verify result
        assert isinstance(result, SynthesisResult)
        assert result.artifact_id == 'test-artifact'
        assert result.modern_implementation_s3_key is not None
        assert result.cdk_infrastructure_s3_key is not None
        assert result.synthesis_timestamp is not None
        
        # Verify S3 get_object was called
        mock_s3_client.get_object.assert_called_once()
        
        # Verify Bedrock was invoked
        assert mock_bedrock_client.invoke_model.called
        
        # Verify Lambda code was stored in S3
        put_calls = [call for call in mock_s3_client.put_object.call_args_list]
        assert len(put_calls) >= 2  # Lambda code + CDK code
    
    def test_lambda_code_follows_aws_best_practices(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that generated Lambda code follows AWS best practices.
        
        Validates: Requirement 6.2
        """
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        mock_bedrock_response = {
            'content': [{'text': SAMPLE_GENERATED_LAMBDA_CODE}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get the stored Lambda code
        lambda_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'lambda.py' in str(call)
        ][0]
        stored_code = lambda_put_call[1]['Body'].decode('utf-8')
        
        # Verify AWS Lambda best practices
        assert 'lambda_handler' in stored_code
        assert 'event' in stored_code
        assert 'context' in stored_code
        assert 'aws_lambda_powertools' in stored_code or 'Logger' in stored_code
        assert 'statusCode' in stored_code or 'return' in stored_code
    
    def test_error_handling_in_generated_code(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that generated code implements error handling.
        
        Validates: Requirement 6.3
        """
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        # Generate code with error handling
        code_with_error_handling = SAMPLE_GENERATED_LAMBDA_CODE + '''
try:
    result = calculate_payroll(employee_id, hours_worked)
except Exception as e:
    logger.error(f"Error calculating payroll: {e}")
    return {
        'statusCode': 500,
        'body': json.dumps({'error': str(e)})
    }
'''
        
        mock_bedrock_response = {
            'content': [{'text': code_with_error_handling}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get stored code
        lambda_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'lambda.py' in str(call)
        ][0]
        stored_code = lambda_put_call[1]['Body'].decode('utf-8')
        
        # Verify error handling patterns
        assert 'try' in stored_code or 'except' in stored_code or 'Exception' in stored_code
    
    def test_logging_with_powertools(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that generated code uses AWS Lambda PowerTools for logging.
        
        Validates: Requirement 6.4
        """
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        mock_bedrock_response = {
            'content': [{'text': SAMPLE_GENERATED_LAMBDA_CODE}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get stored code
        lambda_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'lambda.py' in str(call)
        ][0]
        stored_code = lambda_put_call[1]['Body'].decode('utf-8')
        
        # Verify PowerTools usage
        assert 'aws_lambda_powertools' in stored_code or 'Logger' in stored_code
        assert '@logger.inject_lambda_context' in stored_code or 'logger' in stored_code
        assert '@tracer.capture_lambda_handler' in stored_code or 'Tracer' in stored_code
    
    def test_behavioral_logic_preservation(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that all behavioral logic from Logic Map is preserved.
        
        Validates: Requirement 6.5
        """
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        mock_bedrock_response = {
            'content': [{'text': SAMPLE_GENERATED_LAMBDA_CODE}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get stored code
        lambda_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'lambda.py' in str(call)
        ][0]
        stored_code = lambda_put_call[1]['Body'].decode('utf-8')
        
        # Verify entry points are implemented
        for entry_point in logic_map.entry_points:
            func_name = entry_point.name.lower().replace('-', '_')
            assert func_name in stored_code.lower()
    
    def test_side_effects_preservation(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that all side effects from Logic Map are preserved.
        
        Validates: Requirement 6.6
        """
        logic_map = create_sample_logic_map(with_side_effects=True)
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        # Generate code with side effects
        code_with_side_effects = SAMPLE_GENERATED_LAMBDA_CODE + '''
# Side effect: FILE_IO
with open('output.dat', 'w') as f:
    f.write(str(salary))

# Side effect: DATABASE
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('employee_table')
table.update_item(
    Key={'employee_id': employee_id},
    UpdateExpression='SET salary = :val',
    ExpressionAttributeValues={':val': str(salary)}
)
'''
        
        mock_bedrock_response = {
            'content': [{'text': code_with_side_effects}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get stored code
        lambda_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'lambda.py' in str(call)
        ][0]
        stored_code = lambda_put_call[1]['Body'].decode('utf-8')
        
        # Verify side effects are implemented
        assert 'open(' in stored_code or 's3' in stored_code.lower()  # FILE_IO
        assert 'dynamodb' in stored_code.lower() or 'table' in stored_code.lower()  # DATABASE
    
    def test_cdk_infrastructure_generation(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test CDK infrastructure code generation.
        
        Validates: Requirement 6.7
        """
        logic_map = create_sample_logic_map(with_side_effects=True)
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        # Generate code WITH side effects implemented
        code_with_side_effects = SAMPLE_GENERATED_LAMBDA_CODE + '''
# Side effect: FILE_IO
with open('output.dat', 'w') as f:
    f.write(str(salary))

# Side effect: DATABASE
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('employee_table')
table.put_item(Item={'employee_id': employee_id, 'salary': str(salary)})
'''
        
        mock_bedrock_response = {
            'content': [{'text': code_with_side_effects}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Get stored CDK code
        cdk_put_call = [
            call for call in mock_s3_client.put_object.call_args_list
            if 'stack.py' in str(call)
        ][0]
        stored_cdk_code = cdk_put_call[1]['Body'].decode('utf-8')
        
        # Verify CDK code structure
        assert 'aws_cdk' in stored_cdk_code or 'Stack' in stored_cdk_code
        assert 'lambda_' in stored_cdk_code or 'Function' in stored_cdk_code
        assert 'iam' in stored_cdk_code or 'Role' in stored_cdk_code
        
        # Verify resources for side effects
        assert 's3' in stored_cdk_code.lower() or 'Bucket' in stored_cdk_code  # FILE_IO
        assert 'dynamodb' in stored_cdk_code.lower() or 'Table' in stored_cdk_code  # DATABASE
    
    def test_code_storage_in_s3(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """
        Test that generated code is stored in S3 with encryption.
        
        Validates: Requirement 6.8
        """
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        mock_bedrock_response = {
            'content': [{'text': SAMPLE_GENERATED_LAMBDA_CODE}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_bedrock_client.invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        result = bedrock_architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Verify S3 put_object calls
        put_calls = mock_s3_client.put_object.call_args_list
        assert len(put_calls) >= 2  # Lambda code + CDK code
        
        # Verify Lambda code storage
        lambda_call = [call for call in put_calls if 'lambda.py' in str(call)][0]
        assert lambda_call[1]['Bucket'] == 'test-modern-impl'
        assert 'modern-implementations/' in lambda_call[1]['Key']
        assert lambda_call[1]['ServerSideEncryption'] == 'aws:kms'
        assert lambda_call[1]['SSEKMSKeyId'] == 'test-kms-key'
        
        # Verify CDK code storage
        cdk_call = [call for call in put_calls if 'stack.py' in str(call)][0]
        assert cdk_call[1]['Bucket'] == 'test-cdk-infra'
        assert 'cdk-infrastructure/' in cdk_call[1]['Key']
        assert cdk_call[1]['ServerSideEncryption'] == 'aws:kms'
    
    def test_error_handling_s3_failure(
        self, bedrock_architect, mock_s3_client
    ):
        """Test error handling when S3 read fails."""
        from rosetta_zero.utils.retry import PermanentError
        
        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
            'GetObject'
        )
        
        with pytest.raises((ValueError, PermanentError)):
            bedrock_architect.synthesize_lambda(
                logic_map_bucket='test-logic-maps',
                logic_map_key='logic-maps/missing/logic-map.json',
            )
    
    def test_error_handling_bedrock_throttling(
        self, bedrock_architect, mock_s3_client, mock_bedrock_client
    ):
        """Test error handling for Bedrock throttling."""
        from rosetta_zero.utils.retry import RetryExhaustedError
        
        logic_map = create_sample_logic_map()
        mock_s3_client.get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'ServiceName': 'bedrock-runtime'}
            },
            'InvokeModel'
        )
        
        # Should raise error after retries are exhausted
        with pytest.raises((ClientError, RetryExhaustedError)):
            bedrock_architect.synthesize_lambda(
                logic_map_bucket='test-logic-maps',
                logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
            )


class TestArithmeticPrecisionPreservation:
    """Test arithmetic precision preservation."""
    
    def test_preserve_fixed_point_arithmetic(self):
        """
        Test preservation of fixed-point arithmetic requirements.
        
        Validates: Requirement 8.1
        """
        logic_map = create_sample_logic_map(with_precision=True)
        
        precision_docs = preserve_arithmetic_precision(logic_map)
        
        # Verify documentation contains fixed-point requirements
        assert 'Fixed-Point Arithmetic' in precision_docs
        assert 'SALARY_CALCULATION' in precision_docs
        assert 'precision=10' in precision_docs
        assert 'scale=2' in precision_docs
        assert 'Decimal' in precision_docs
    
    def test_preserve_floating_point_precision(self):
        """
        Test preservation of floating-point precision requirements.
        
        Validates: Requirement 8.2
        """
        logic_map = create_sample_logic_map(with_precision=True)
        
        precision_docs = preserve_arithmetic_precision(logic_map)
        
        # Verify documentation contains floating-point requirements
        assert 'Floating-Point Precision' in precision_docs
        assert 'INTEREST_RATE' in precision_docs
        assert '64 bits' in precision_docs
    
    def test_preserve_rounding_modes(self):
        """
        Test preservation of rounding mode requirements.
        
        Validates: Requirement 8.3
        """
        logic_map = create_sample_logic_map(with_precision=True)
        
        precision_docs = preserve_arithmetic_precision(logic_map)
        
        # Verify documentation contains rounding mode requirements
        assert 'Rounding Modes' in precision_docs
        assert 'SALARY_CALCULATION' in precision_docs
        assert 'ROUND_HALF_UP' in precision_docs
        assert 'decimal.ROUND_HALF_UP' in precision_docs
    
    def test_arithmetic_precision_documentation(self):
        """
        Test that arithmetic precision decisions are documented.
        
        Validates: Requirement 8.4
        """
        logic_map = create_sample_logic_map(with_precision=True)
        
        precision_docs = preserve_arithmetic_precision(logic_map)
        
        # Verify implementation guidance is included
        assert 'Implementation Guidance' in precision_docs
        assert 'decimal module' in precision_docs
        assert 'getcontext()' in precision_docs
        assert 'quantize' in precision_docs
        
        # Verify critical warning is included
        assert 'CRITICAL' in precision_docs
        assert 'exact' in precision_docs.lower() or 'match' in precision_docs.lower()


class TestFaithfulTranspilation:
    """Test faithful transpilation constraints."""
    
    def test_validate_entry_points_implemented(self):
        """
        Test validation that all entry points are implemented.
        
        Validates: Requirement 7.1
        """
        logic_map = create_sample_logic_map()
        
        # Valid code with entry point implemented
        valid_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        # Should not raise error
        validate_faithful_transpilation(logic_map, valid_code)
    
    def test_validate_missing_entry_point_fails(self):
        """Test validation fails when entry point is missing."""
        logic_map = create_sample_logic_map()
        
        # Code without entry point
        invalid_code = '''
def lambda_handler(event, context):
    return {'statusCode': 200}
'''
        
        with pytest.raises(FaithfulTranspilationError) as exc_info:
            validate_faithful_transpilation(logic_map, invalid_code)
        
        assert 'entry point' in str(exc_info.value).lower()
    
    def test_validate_no_feature_addition(self):
        """
        Test validation prevents feature addition.
        
        Validates: Requirement 7.2
        """
        logic_map = create_sample_logic_map()
        
        # Code with extra features not in Logic Map
        code_with_extra_features = SAMPLE_GENERATED_LAMBDA_CODE + '''
def send_email_notification(employee_id, salary):
    """Extra feature not in Logic Map."""
    import boto3
    ses = boto3.client('ses')
    ses.send_email(
        Source='noreply@example.com',
        Destination={'ToAddresses': ['admin@example.com']},
        Message={'Subject': {'Data': 'Payroll Calculated'}}
    )
'''
        
        with pytest.raises(FaithfulTranspilationError) as exc_info:
            validate_faithful_transpilation(logic_map, code_with_extra_features)
        
        assert 'extra features' in str(exc_info.value).lower()
    
    def test_validate_no_unauthorized_optimization(self):
        """
        Test validation prevents unauthorized optimizations.
        
        Validates: Requirement 7.3
        """
        logic_map = create_sample_logic_map()
        
        # Code with caching optimization
        code_with_optimization = '''
from functools import lru_cache

@lru_cache(maxsize=128)
def calculate_payroll(employee_id, hours_worked):
    """Cached calculation - changes timing behavior."""
    return hours_worked * 25.50
'''
        
        with pytest.raises(FaithfulTranspilationError) as exc_info:
            validate_faithful_transpilation(logic_map, code_with_optimization)
        
        assert 'optimization' in str(exc_info.value).lower()
        assert 'caching' in str(exc_info.value).lower()
    
    def test_validate_side_effects_preserved(self):
        """
        Test validation ensures side effects are preserved.
        
        Validates: Requirement 7.1
        """
        logic_map = create_sample_logic_map(with_side_effects=True)
        
        # Code without side effects
        code_without_side_effects = SAMPLE_GENERATED_LAMBDA_CODE
        
        with pytest.raises(FaithfulTranspilationError) as exc_info:
            validate_faithful_transpilation(logic_map, code_without_side_effects)
        
        assert 'side effect' in str(exc_info.value).lower()
    
    def test_validate_side_effects_file_io(self):
        """Test validation of FILE_IO side effects."""
        logic_map = create_sample_logic_map(with_side_effects=True)
        
        # Code with FILE_IO side effect
        code_with_file_io = SAMPLE_GENERATED_LAMBDA_CODE + '''
# FILE_IO side effect
with open('output.dat', 'w') as f:
    f.write(str(salary))

# DATABASE side effect
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('employee_table')
table.put_item(Item={'employee_id': employee_id, 'salary': str(salary)})
'''
        
        # Should not raise error
        validate_faithful_transpilation(logic_map, code_with_file_io)
    
    def test_validate_synthesis_decisions_logged(self):
        """
        Test that synthesis decisions are logged.
        
        Validates: Requirement 7.5
        """
        logic_map = create_sample_logic_map()
        
        with patch('rosetta_zero.lambdas.bedrock_architect.faithful_transpilation.log_architect_decision') as mock_log:
            validate_faithful_transpilation(logic_map, SAMPLE_GENERATED_LAMBDA_CODE)
            
            # Verify logging was called
            assert mock_log.called
            call_args = mock_log.call_args
            assert call_args[1]['logic_map_id'] == logic_map.artifact_id
            assert 'validated' in call_args[1]['decision']


class TestCDKInfrastructureGeneration:
    """Test CDK infrastructure code generation."""
    
    def test_generate_basic_cdk_infrastructure(self):
        """
        Test basic CDK infrastructure generation.
        
        Validates: Requirement 6.7
        """
        logic_map = create_sample_logic_map()
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify CDK code structure
        assert 'from aws_cdk import' in cdk_code
        assert 'Stack' in cdk_code
        assert 'lambda_' in cdk_code or 'Lambda' in cdk_code
        assert 'Function' in cdk_code
        assert 'iam' in cdk_code
        assert 'Role' in cdk_code
    
    def test_generate_cdk_with_s3_for_file_io(self):
        """Test CDK generation includes S3 bucket for FILE_IO side effects."""
        logic_map = create_sample_logic_map(with_side_effects=True)
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify S3 bucket is included
        assert 's3' in cdk_code.lower()
        assert 'Bucket' in cdk_code
        assert 'data_bucket' in cdk_code or 'DataBucket' in cdk_code
    
    def test_generate_cdk_with_dynamodb_for_database(self):
        """Test CDK generation includes DynamoDB table for DATABASE side effects."""
        logic_map = create_sample_logic_map(with_side_effects=True)
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify DynamoDB table is included
        assert 'dynamodb' in cdk_code.lower()
        assert 'Table' in cdk_code
        assert 'data_table' in cdk_code or 'DataTable' in cdk_code
    
    def test_generate_cdk_with_vpc_for_network(self):
        """Test CDK generation includes VPC for NETWORK side effects."""
        # Create logic map with network side effect
        logic_map = create_sample_logic_map()
        logic_map.side_effects.append(
            SideEffect(
                operation_type=SideEffectType.NETWORK,
                scope='external_api',
                description='Call external API',
                timing_requirements=None
            )
        )
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify VPC is included
        assert 'vpc' in cdk_code.lower() or 'Vpc' in cdk_code
        assert 'security_group' in cdk_code or 'SecurityGroup' in cdk_code
    
    def test_generate_cdk_with_kms_encryption(self):
        """Test CDK generation includes KMS encryption."""
        logic_map = create_sample_logic_map()
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify KMS key is included
        assert 'kms' in cdk_code.lower()
        assert 'Key' in cdk_code
        assert 'encryption' in cdk_code.lower()
    
    def test_generate_cdk_with_iam_permissions(self):
        """Test CDK generation includes proper IAM permissions."""
        logic_map = create_sample_logic_map(with_side_effects=True)
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify IAM role and permissions
        assert 'iam' in cdk_code.lower()
        assert 'Role' in cdk_code
        assert 'grant' in cdk_code.lower() or 'policy' in cdk_code.lower()
    
    def test_generate_cdk_with_cloudwatch_logs(self):
        """Test CDK generation includes CloudWatch Logs configuration."""
        logic_map = create_sample_logic_map()
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify CloudWatch Logs retention
        assert 'log_retention' in cdk_code or 'logs' in cdk_code.lower()
        assert 'SEVEN_YEARS' in cdk_code or '2555' in cdk_code
    
    def test_generate_cdk_with_lambda_configuration(self):
        """Test CDK generation includes proper Lambda configuration."""
        logic_map = create_sample_logic_map()
        lambda_code = SAMPLE_GENERATED_LAMBDA_CODE
        
        cdk_code = generate_cdk_infrastructure(logic_map, lambda_code)
        
        # Verify Lambda configuration
        assert 'PYTHON_3_12' in cdk_code or 'python_3_12' in cdk_code.lower()
        assert 'timeout' in cdk_code.lower()
        assert 'memory_size' in cdk_code or 'memory' in cdk_code.lower()
        assert 'environment' in cdk_code.lower()


class TestKnowledgeBaseIntegration:
    """Test Knowledge Base integration for language documentation."""
    
    @pytest.fixture
    def mock_bedrock_agent_client(self):
        return Mock()
    
    def test_query_cobol_documentation(self, mock_bedrock_agent_client):
        """Test querying COBOL documentation from Knowledge Base."""
        from rosetta_zero.lambdas.bedrock_architect.knowledge_base import query_language_docs
        
        logic_map = create_sample_logic_map()
        
        # Mock Knowledge Base response
        mock_bedrock_agent_client.retrieve.return_value = {
            'retrievalResults': [
                {
                    'content': {'text': 'COBOL COMPUTE statement documentation...'},
                    'score': 0.95
                }
            ]
        }
        
        context = query_language_docs(
            bedrock_agent_client=mock_bedrock_agent_client,
            knowledge_base_id='test-cobol-kb',
            logic_map=logic_map,
            language='COBOL'
        )
        
        # Verify Knowledge Base was queried
        assert mock_bedrock_agent_client.retrieve.called
        assert 'COBOL' in context or 'documentation' in context.lower()
    
    def test_query_fortran_documentation(self, mock_bedrock_agent_client):
        """Test querying FORTRAN documentation from Knowledge Base."""
        from rosetta_zero.lambdas.bedrock_architect.knowledge_base import query_language_docs
        
        logic_map = create_sample_logic_map()
        logic_map.dependencies = [
            Dependency(type='FORTRAN', name='SUBROUTINE', description='Fortran subroutine')
        ]
        
        mock_bedrock_agent_client.retrieve.return_value = {
            'retrievalResults': [
                {
                    'content': {'text': 'FORTRAN SUBROUTINE documentation...'},
                    'score': 0.90
                }
            ]
        }
        
        context = query_language_docs(
            bedrock_agent_client=mock_bedrock_agent_client,
            knowledge_base_id='test-fortran-kb',
            logic_map=logic_map,
            language='FORTRAN'
        )
        
        assert mock_bedrock_agent_client.retrieve.called



class TestTimingBehaviorPreservation:
    """Test timing behavior preservation."""
    
    def test_preserve_timing_requirements(self):
        """Test preservation of timing requirements from Logic Map."""
        from rosetta_zero.lambdas.bedrock_architect.timing import preserve_timing_behavior
        from rosetta_zero.models.logic_map import TimingRequirement
        
        logic_map = create_sample_logic_map()
        # Add timing requirement with proper structure
        logic_map.side_effects.append(
            SideEffect(
                operation_type=SideEffectType.NETWORK,
                scope='external_api',
                description='Call external API with 1 second delay',
                timing_requirements=TimingRequirement(
                    operation='external_api_call',
                    min_duration_ms=1000,
                    max_duration_ms=1000,
                    description='1 second delay'
                )
            )
        )
        
        timing_docs = preserve_timing_behavior(logic_map)
        
        # Verify timing documentation
        assert 'timing' in timing_docs.lower() or 'delay' in timing_docs.lower() or 'duration' in timing_docs.lower()
        assert '1' in timing_docs or 'second' in timing_docs.lower()


class TestErrorHandling:
    """Test error handling in Bedrock Architect."""
    
    def test_handle_bedrock_500_error(self):
        """Test handling of Bedrock 500-level errors."""
        from rosetta_zero.lambdas.bedrock_architect.error_handler import handle_bedrock_error
        
        error = ClientError(
            {
                'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'},
                'ResponseMetadata': {'ServiceName': 'bedrock-runtime'}
            },
            'InvokeModel'
        )
        
        with pytest.raises(Exception):
            handle_bedrock_error(error, 'test_operation', 'test-artifact')
    
    def test_handle_bedrock_throttling_error(self):
        """Test handling of Bedrock throttling errors."""
        from rosetta_zero.lambdas.bedrock_architect.error_handler import handle_bedrock_error
        from rosetta_zero.utils.retry import TransientError
        
        error = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'ServiceName': 'bedrock-runtime'}
            },
            'InvokeModel'
        )
        
        with pytest.raises((TransientError, ClientError)):
            handle_bedrock_error(error, 'test_operation', 'test-artifact')


class TestIntegration:
    """Integration tests for complete synthesis workflow."""
    
    @pytest.fixture
    def mock_aws_services(self):
        """Mock all AWS services for integration testing."""
        with patch('boto3.client') as mock_client:
            mock_s3 = Mock()
            mock_bedrock = Mock()
            mock_bedrock_agent = Mock()
            
            def client_factory(service, **kwargs):
                if service == 's3':
                    return mock_s3
                elif service == 'bedrock-runtime':
                    return mock_bedrock
                elif service == 'bedrock-agent-runtime':
                    return mock_bedrock_agent
                return Mock()
            
            mock_client.side_effect = client_factory
            
            yield {
                's3': mock_s3,
                'bedrock': mock_bedrock,
                'bedrock_agent': mock_bedrock_agent,
            }
    
    def test_complete_synthesis_workflow(self, mock_aws_services):
        """
        Test complete synthesis workflow from Logic Map to CDK code.
        
        Validates: Requirements 6.1-6.8
        """
        # Setup Logic Map
        logic_map = create_sample_logic_map(with_side_effects=True, with_precision=True)
        
        # Setup S3 mock
        mock_aws_services['s3'].get_object.return_value = {
            'Body': BytesIO(logic_map.to_json().encode('utf-8'))
        }
        
        # Generate code WITH side effects implemented
        code_with_side_effects = SAMPLE_GENERATED_LAMBDA_CODE + '''
# Side effect: FILE_IO
with open('output.dat', 'w') as f:
    f.write(str(salary))

# Side effect: DATABASE
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('employee_table')
table.put_item(Item={'employee_id': employee_id, 'salary': str(salary)})
'''
        
        # Setup Bedrock mock
        mock_bedrock_response = {
            'content': [{'text': code_with_side_effects}],
            'usage': {'input_tokens': 1000, 'output_tokens': 500}
        }
        mock_aws_services['bedrock'].invoke_model.return_value = {
            'body': BytesIO(json.dumps(mock_bedrock_response).encode('utf-8'))
        }
        
        # Setup Knowledge Base mock
        mock_aws_services['bedrock_agent'].retrieve.return_value = {
            'retrievalResults': [
                {'content': {'text': 'COBOL documentation...'}, 'score': 0.95}
            ]
        }
        
        # Create architect
        architect = BedrockArchitect(
            region='us-east-1',
            modern_implementations_bucket='test-modern-impl',
            cdk_infrastructure_bucket='test-cdk-infra',
            kms_key_id='test-kms-key',
            bedrock_model_id='anthropic.claude-3-5-sonnet-20241022-v2:0',
            cobol_kb_id='test-cobol-kb',
        )
        
        # Execute synthesis
        result = architect.synthesize_lambda(
            logic_map_bucket='test-logic-maps',
            logic_map_key='logic-maps/test-artifact/1.0/logic-map.json',
        )
        
        # Verify complete workflow
        assert result.artifact_id == 'test-artifact'
        assert result.modern_implementation_s3_key is not None
        assert result.cdk_infrastructure_s3_key is not None
        
        # Verify all AWS services were called
        assert mock_aws_services['s3'].get_object.called
        assert mock_aws_services['bedrock'].invoke_model.called
        assert mock_aws_services['s3'].put_object.call_count >= 2
