"""
Unit tests for enhanced error recovery with AWS 500-level error detection.

Requirements: 19.2, 19.3, 19.4, 19.5, 25.1, 25.2, 25.3, 25.4, 25.5
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from rosetta_zero.utils.error_recovery import (
    EnhancedRetryStrategy,
    AWS500LevelError,
    is_aws_500_error,
    is_transient_error,
    with_enhanced_retry,
)
from rosetta_zero.utils.retry import (
    TransientError,
    PermanentError,
    BehavioralDiscrepancyError,
    RetryExhaustedError,
)


class TestAWS500ErrorDetection:
    """Test AWS 500-level error detection."""
    
    def test_is_aws_500_error_with_500_status_code(self):
        """Test detection of AWS 500-level error by HTTP status code."""
        error = ClientError(
            {
                'Error': {'Code': 'InternalError', 'Message': 'Internal server error'},
                'ResponseMetadata': {'HTTPStatusCode': 500}
            },
            'TestOperation'
        )
        
        assert is_aws_500_error(error) is True
    
    def test_is_aws_500_error_with_503_status_code(self):
        """Test detection of AWS 503 Service Unavailable error."""
        error = ClientError(
            {
                'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'},
                'ResponseMetadata': {'HTTPStatusCode': 503}
            },
            'TestOperation'
        )
        
        assert is_aws_500_error(error) is True
    
    def test_is_aws_500_error_with_known_error_code(self):
        """Test detection of AWS 500-level error by error code."""
        error = ClientError(
            {
                'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'},
                'ResponseMetadata': {'HTTPStatusCode': 200}
            },
            'TestOperation'
        )
        
        assert is_aws_500_error(error) is True
    
    def test_is_aws_500_error_with_400_error(self):
        """Test that 400-level errors are not detected as 500-level."""
        error = ClientError(
            {
                'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'},
                'ResponseMetadata': {'HTTPStatusCode': 400}
            },
            'TestOperation'
        )
        
        assert is_aws_500_error(error) is False
    
    def test_is_aws_500_error_with_non_client_error(self):
        """Test that non-ClientError exceptions are not detected as 500-level."""
        error = ValueError("Some error")
        
        assert is_aws_500_error(error) is False


class TestTransientErrorDetection:
    """Test transient error detection."""
    
    def test_is_transient_error_with_transient_error_class(self):
        """Test detection of TransientError class."""
        error = TransientError("Temporary failure")
        
        assert is_transient_error(error) is True
    
    def test_is_transient_error_with_throttling(self):
        """Test detection of throttling errors."""
        error = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'HTTPStatusCode': 400}
            },
            'TestOperation'
        )
        
        assert is_transient_error(error) is True
    
    def test_is_transient_error_with_timeout(self):
        """Test detection of timeout errors."""
        error = ClientError(
            {
                'Error': {'Code': 'RequestTimeout', 'Message': 'Request timed out'},
                'ResponseMetadata': {'HTTPStatusCode': 408}
            },
            'TestOperation'
        )
        
        assert is_transient_error(error) is True
    
    def test_is_transient_error_with_permanent_error(self):
        """Test that permanent errors are not detected as transient."""
        error = ClientError(
            {
                'Error': {'Code': 'ValidationException', 'Message': 'Invalid input'},
                'ResponseMetadata': {'HTTPStatusCode': 400}
            },
            'TestOperation'
        )
        
        assert is_transient_error(error) is False


class TestEnhancedRetryStrategy:
    """Test enhanced retry strategy with AWS 500-level error handling."""
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_successful_operation_no_retry(self, mock_event_mgr, mock_sns_mgr):
        """Test successful operation without retry."""
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        operation = Mock(return_value="success")
        
        result = strategy.execute_with_retry(operation, operation_name='test_op')
        
        assert result == "success"
        operation.assert_called_once()
        mock_sns_mgr.return_value.publish_operator_alert.assert_not_called()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_transient_error_retry_success(self, mock_sleep, mock_event_mgr, mock_sns_mgr):
        """
        Test retry on transient error with eventual success.
        
        Requirement 19.2: Retry transient failures with exponential backoff
        Requirement 19.5: Resume execution after transient failures resolved
        """
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            base_delay_seconds=2,
            component_name='test_component'
        )
        
        operation = Mock(side_effect=[
            TransientError("Temporary failure"),
            "success"
        ])
        
        result = strategy.execute_with_retry(operation, operation_name='test_op')
        
        assert result == "success"
        assert operation.call_count == 2
        mock_sleep.assert_called_once_with(2)  # Exponential backoff: 2 * (2^0) = 2
        mock_sns_mgr.return_value.publish_operator_alert.assert_not_called()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_transient_error_exponential_backoff(self, mock_sleep, mock_event_mgr, mock_sns_mgr):
        """
        Test exponential backoff on multiple transient errors.
        
        Requirement 25.3: Retry with exponential backoff
        """
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            base_delay_seconds=2,
            component_name='test_component'
        )
        
        operation = Mock(side_effect=[
            TransientError("Failure 1"),
            TransientError("Failure 2"),
            "success"
        ])
        
        result = strategy.execute_with_retry(operation, operation_name='test_op')
        
        assert result == "success"
        assert operation.call_count == 3
        
        # Verify exponential backoff: 2, 4 seconds
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(2)  # 2 * (2^0) = 2
        mock_sleep.assert_any_call(4)  # 2 * (2^1) = 4
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_aws_500_error_notification_and_halt(self, mock_event_mgr, mock_sns_mgr):
        """
        Test AWS 500-level error triggers SNS notification and halts execution.
        
        Requirement 19.3: Notify operators via SNS on AWS 500-level errors
        Requirement 19.4: Pause execution until operator intervention
        """
        mock_sns_instance = Mock()
        mock_sns_mgr.return_value = mock_sns_instance
        
        mock_event_instance = Mock()
        mock_event_mgr.return_value = mock_event_instance
        
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        error = ClientError(
            {
                'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'},
                'ResponseMetadata': {
                    'HTTPStatusCode': 500,
                    'ServiceId': 'bedrock'
                }
            },
            'InvokeModel'
        )
        
        operation = Mock(side_effect=error)
        
        with pytest.raises(AWS500LevelError) as exc_info:
            strategy.execute_with_retry(operation, operation_name='test_op')
        
        # Verify error details
        assert exc_info.value.service == 'bedrock'
        assert exc_info.value.operation == 'test_op'
        assert exc_info.value.error_code == 'InternalServerError'
        
        # Verify SNS notification was sent
        mock_sns_instance.publish_aws_500_error_alert.assert_called_once()
        call_args = mock_sns_instance.publish_aws_500_error_alert.call_args[1]
        assert call_args['service'] == 'bedrock'
        assert call_args['operation'] == 'test_op'
        assert call_args['error_code'] == 'InternalServerError'
        
        # Verify EventBridge event was published
        mock_event_instance.publish_error_event.assert_called_once()
        
        # Verify operation was only called once (no retry on 500 errors)
        operation.assert_called_once()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_retry_exhausted_notification(self, mock_sleep, mock_event_mgr, mock_sns_mgr):
        """
        Test operator notification when retries are exhausted.
        
        Requirement 25.4: Notify operators on permanent failures
        """
        mock_sns_instance = Mock()
        mock_sns_mgr.return_value = mock_sns_instance
        
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        operation = Mock(side_effect=TransientError("Persistent failure"))
        
        with pytest.raises(RetryExhaustedError):
            strategy.execute_with_retry(operation, operation_name='test_op')
        
        # Verify operation was called max_retries + 1 times
        assert operation.call_count == 4
        
        # Verify SNS notification was sent for permanent failure
        assert mock_sns_instance.publish_operator_alert.call_count >= 1
        
        # Find the call with "Permanent Failure" in subject
        calls = mock_sns_instance.publish_operator_alert.call_args_list
        permanent_failure_call = None
        for call in calls:
            if 'Permanent Failure' in call[1].get('subject', ''):
                permanent_failure_call = call
                break
        
        assert permanent_failure_call is not None
        assert permanent_failure_call[1]['severity'] == 'CRITICAL'
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_permanent_error_no_retry(self, mock_event_mgr, mock_sns_mgr):
        """Test that permanent errors are not retried."""
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        operation = Mock(side_effect=PermanentError("Permanent failure"))
        
        with pytest.raises(PermanentError):
            strategy.execute_with_retry(operation, operation_name='test_op')
        
        # Verify operation was only called once (no retry)
        operation.assert_called_once()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_behavioral_discrepancy_no_retry(self, mock_event_mgr, mock_sns_mgr):
        """Test that behavioral discrepancies are not retried."""
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        operation = Mock(side_effect=BehavioralDiscrepancyError("Test failed"))
        
        with pytest.raises(BehavioralDiscrepancyError):
            strategy.execute_with_retry(operation, operation_name='test_op')
        
        # Verify operation was only called once (no retry)
        operation.assert_called_once()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_client_error_transient_retry(self, mock_sleep, mock_event_mgr, mock_sns_mgr):
        """Test retry on transient ClientError."""
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='test_component'
        )
        
        error = ClientError(
            {
                'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'},
                'ResponseMetadata': {'HTTPStatusCode': 400}
            },
            'TestOperation'
        )
        
        operation = Mock(side_effect=[error, "success"])
        
        result = strategy.execute_with_retry(operation, operation_name='test_op')
        
        assert result == "success"
        assert operation.call_count == 2
        mock_sleep.assert_called_once()


class TestEnhancedRetryDecorator:
    """Test enhanced retry decorator."""
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_decorator_with_transient_error(self, mock_sleep, mock_event_mgr, mock_sns_mgr):
        """Test decorator handles transient errors."""
        
        call_count = {'count': 0}
        
        @with_enhanced_retry(max_retries=3, component_name='test_component')
        def test_function():
            call_count['count'] += 1
            if call_count['count'] < 2:
                raise TransientError("Temporary failure")
            return "success"
        
        result = test_function()
        
        assert result == "success"
        assert call_count['count'] == 2
        mock_sleep.assert_called_once()
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_decorator_with_aws_500_error(self, mock_event_mgr, mock_sns_mgr):
        """Test decorator handles AWS 500-level errors."""
        
        @with_enhanced_retry(max_retries=3, component_name='test_component')
        def test_function():
            raise ClientError(
                {
                    'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'},
                    'ResponseMetadata': {
                        'HTTPStatusCode': 500,
                        'ServiceId': 'test-service'
                    }
                },
                'TestOperation'
            )
        
        with pytest.raises(AWS500LevelError):
            test_function()


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery across workflow."""
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    @patch('time.sleep')
    def test_workflow_resilience_to_transient_failures(
        self,
        mock_sleep,
        mock_event_mgr,
        mock_sns_mgr
    ):
        """
        Test workflow continues after transient failures are resolved.
        
        Requirement 19.5: Resume execution after transient failures resolved
        """
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='workflow_orchestrator'
        )
        
        # Simulate multiple operations with transient failures
        operations = [
            Mock(side_effect=[TransientError("Failure 1"), "success 1"]),
            Mock(return_value="success 2"),
            Mock(side_effect=[TransientError("Failure 2"), "success 3"]),
        ]
        
        results = []
        for i, operation in enumerate(operations):
            result = strategy.execute_with_retry(
                operation,
                operation_name=f'operation_{i}'
            )
            results.append(result)
        
        assert results == ["success 1", "success 2", "success 3"]
        assert operations[0].call_count == 2
        assert operations[1].call_count == 1
        assert operations[2].call_count == 2
    
    @patch('rosetta_zero.utils.error_recovery.SNSNotificationManager')
    @patch('rosetta_zero.utils.error_recovery.EventBridgeManager')
    def test_workflow_halts_on_aws_500_error(self, mock_event_mgr, mock_sns_mgr):
        """
        Test workflow halts on AWS 500-level error.
        
        Requirement 19.4: Pause execution on AWS 500-level errors
        """
        mock_sns_instance = Mock()
        mock_sns_mgr.return_value = mock_sns_instance
        
        strategy = EnhancedRetryStrategy(
            max_retries=3,
            component_name='workflow_orchestrator'
        )
        
        # First operation succeeds
        operation1 = Mock(return_value="success 1")
        result1 = strategy.execute_with_retry(operation1, operation_name='op1')
        assert result1 == "success 1"
        
        # Second operation encounters AWS 500 error
        error = ClientError(
            {
                'Error': {'Code': 'InternalServerError', 'Message': 'Internal error'},
                'ResponseMetadata': {
                    'HTTPStatusCode': 500,
                    'ServiceId': 'lambda'
                }
            },
            'Invoke'
        )
        operation2 = Mock(side_effect=error)
        
        with pytest.raises(AWS500LevelError):
            strategy.execute_with_retry(operation2, operation_name='op2')
        
        # Verify SNS notification was sent
        mock_sns_instance.publish_aws_500_error_alert.assert_called_once()
        
        # Third operation should not be executed (workflow halted)
        operation3 = Mock(return_value="success 3")
        # This would not be reached in actual workflow due to exception


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
