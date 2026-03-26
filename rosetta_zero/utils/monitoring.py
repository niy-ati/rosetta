"""Monitoring, logging, and event infrastructure for Rosetta Zero."""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

from rosetta_zero.utils.logging import (
    logger,
    log_error,
    publish_metric,
)


class CloudWatchLogsManager:
    """Manages CloudWatch Logs configuration with encryption and retention."""
    
    def __init__(
        self,
        kms_key_id: Optional[str] = None,
        retention_days: int = 2555  # 7 years
    ):
        """
        Initialize CloudWatch Logs Manager.
        
        Args:
            kms_key_id: KMS key ID for log encryption
            retention_days: Log retention period in days (default: 2555 = 7 years)
        """
        self.logs_client = boto3.client('logs')
        self.kms_key_id = kms_key_id or os.environ.get('KMS_KEY_ID')
        self.retention_days = retention_days
    
    def configure_log_group(
        self,
        log_group_name: str,
        retention_days: Optional[int] = None,
        kms_key_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Configure CloudWatch Log Group with encryption and retention.
        
        Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6
        
        Args:
            log_group_name: Name of the log group
            retention_days: Retention period (default: 2555 days = 7 years)
            kms_key_id: KMS key for encryption
            
        Returns:
            Configuration result with log group details
        """
        retention = retention_days or self.retention_days
        kms_key = kms_key_id or self.kms_key_id
        
        try:
            # Create log group if it doesn't exist
            try:
                self.logs_client.create_log_group(logGroupName=log_group_name)
                logger.info(f"Created log group: {log_group_name}")
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceAlreadyExistsException':
                    raise
                logger.info(f"Log group already exists: {log_group_name}")
            
            # Set retention policy (Requirement 18.5)
            self.logs_client.put_retention_policy(
                logGroupName=log_group_name,
                retentionInDays=retention
            )
            logger.info(f"Set retention to {retention} days for {log_group_name}")
            
            # Enable KMS encryption (Requirement 18.6)
            if kms_key:
                self.logs_client.associate_kms_key(
                    logGroupName=log_group_name,
                    kmsKeyId=kms_key
                )
                logger.info(f"Enabled KMS encryption for {log_group_name}")
            
            return {
                'log_group_name': log_group_name,
                'retention_days': retention,
                'kms_encrypted': bool(kms_key),
                'kms_key_id': kms_key,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            log_error(
                component='cloudwatch_logs_manager',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'log_group_name': log_group_name}
            )
            raise
    
    def configure_structured_logging(
        self,
        log_group_name: str,
        log_format: str = "json"
    ) -> Dict[str, Any]:
        """
        Configure structured JSON logging format.
        
        Requirement: 18.4
        
        Args:
            log_group_name: Name of the log group
            log_format: Log format (default: "json")
            
        Returns:
            Configuration result
        """
        # Note: Structured logging is primarily handled by Lambda PowerTools
        # This method documents the configuration
        logger.info(
            "Configured structured logging",
            extra={
                'log_group_name': log_group_name,
                'log_format': log_format,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'log_group_name': log_group_name,
            'log_format': log_format,
            'structured': True,
            'timestamp': datetime.utcnow().isoformat()
        }


class EventBridgeManager:
    """Manages EventBridge event bus and rules."""
    
    def __init__(self, event_bus_name: str = "default"):
        """
        Initialize EventBridge Manager.
        
        Args:
            event_bus_name: Name of the event bus (default: "default")
        """
        self.events_client = boto3.client('events')
        self.event_bus_name = event_bus_name
    
    def publish_event(
        self,
        source: str,
        detail_type: str,
        detail: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish event to EventBridge.
        
        Requirements: 17.9, 19.3, 24.6, 25.5
        
        Args:
            source: Event source (e.g., "rosetta-zero.certificate-generator")
            detail_type: Event type (e.g., "Certificate Generated")
            detail: Event details
            
        Returns:
            Event publication result
        """
        try:
            response = self.events_client.put_events(
                Entries=[
                    {
                        'Source': source,
                        'DetailType': detail_type,
                        'Detail': json.dumps(detail),
                        'EventBusName': self.event_bus_name,
                        'Time': datetime.utcnow()
                    }
                ]
            )
            
            logger.info(
                "Published event to EventBridge",
                extra={
                    'source': source,
                    'detail_type': detail_type,
                    'event_bus': self.event_bus_name,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'event_id': response['Entries'][0].get('EventId'),
                'source': source,
                'detail_type': detail_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            log_error(
                component='eventbridge_manager',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'source': source, 'detail_type': detail_type}
            )
            raise
    
    def publish_certificate_event(
        self,
        certificate_id: str,
        s3_location: str,
        total_tests: int,
        coverage_percent: float
    ) -> Dict[str, Any]:
        """
        Publish certificate generation event.
        
        Requirement: 17.9
        
        Args:
            certificate_id: Certificate identifier
            s3_location: S3 location of certificate
            total_tests: Total number of tests executed
            coverage_percent: Branch coverage percentage
            
        Returns:
            Event publication result
        """
        return self.publish_event(
            source='rosetta-zero.certificate-generator',
            detail_type='Certificate Generated',
            detail={
                'certificate_id': certificate_id,
                's3_location': s3_location,
                'total_tests': total_tests,
                'coverage_percent': coverage_percent,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    
    def publish_error_event(
        self,
        service: str,
        error_code: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish AWS 500-level error event.
        
        Requirement: 19.3
        
        Args:
            service: AWS service name
            error_code: Error code
            error_message: Error message
            context: Error context
            
        Returns:
            Event publication result
        """
        return self.publish_event(
            source=f'rosetta-zero.{service}',
            detail_type='AWS 500-Level Error',
            detail={
                'service': service,
                'error_code': error_code,
                'error_message': error_message,
                'context': context,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    
    def publish_discrepancy_event(
        self,
        test_vector_id: str,
        discrepancy_report_id: str,
        s3_location: str
    ) -> Dict[str, Any]:
        """
        Publish behavioral discrepancy event.
        
        Requirement: 24.6
        
        Args:
            test_vector_id: Test vector identifier
            discrepancy_report_id: Discrepancy report identifier
            s3_location: S3 location of discrepancy report
            
        Returns:
            Event publication result
        """
        return self.publish_event(
            source='rosetta-zero.verification-environment',
            detail_type='Behavioral Discrepancy Detected',
            detail={
                'test_vector_id': test_vector_id,
                'discrepancy_report_id': discrepancy_report_id,
                's3_location': s3_location,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
    
    def publish_phase_completion_event(
        self,
        workflow_id: str,
        phase_name: str,
        status: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish workflow phase completion event.
        
        Requirement: 24.6
        
        Args:
            workflow_id: Workflow identifier
            phase_name: Phase name (Discovery, Synthesis, Aggression, Validation, Trust)
            status: Completion status (SUCCESS, FAILED)
            details: Phase completion details
            
        Returns:
            Event publication result
        """
        return self.publish_event(
            source='rosetta-zero.workflow',
            detail_type='Workflow Phase Completed',
            detail={
                'workflow_id': workflow_id,
                'phase_name': phase_name,
                'status': status,
                'details': details,
                'timestamp': datetime.utcnow().isoformat()
            }
        )


class SNSNotificationManager:
    """Manages SNS notifications for operators."""
    
    def __init__(self, topic_arn: Optional[str] = None):
        """
        Initialize SNS Notification Manager.
        
        Args:
            topic_arn: SNS topic ARN for operator notifications
        """
        self.sns_client = boto3.client('sns')
        self.topic_arn = topic_arn or os.environ.get('SNS_TOPIC_ARN')
    
    def publish_operator_alert(
        self,
        subject: str,
        message: str,
        severity: str = "HIGH",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Publish operator alert to SNS topic.
        
        Requirements: 19.3, 19.4
        
        Args:
            subject: Alert subject
            message: Alert message
            severity: Alert severity (LOW, MEDIUM, HIGH, CRITICAL)
            context: Additional context
            
        Returns:
            Publication result
        """
        if not self.topic_arn:
            logger.warning("SNS topic ARN not configured, skipping notification")
            return {'skipped': True}
        
        try:
            alert_message = {
                'subject': subject,
                'message': message,
                'severity': severity,
                'context': context or {},
                'timestamp': datetime.utcnow().isoformat()
            }
            
            response = self.sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=f"[{severity}] Rosetta Zero Alert: {subject}",
                Message=json.dumps(alert_message, indent=2)
            )
            
            logger.info(
                "Published operator alert",
                extra={
                    'subject': subject,
                    'severity': severity,
                    'message_id': response['MessageId'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            return {
                'message_id': response['MessageId'],
                'subject': subject,
                'severity': severity,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except ClientError as e:
            log_error(
                component='sns_notification_manager',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={'subject': subject, 'severity': severity}
            )
            raise
    
    def publish_aws_500_error_alert(
        self,
        service: str,
        operation: str,
        error_code: str,
        error_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Publish AWS 500-level error alert.
        
        Requirements: 19.3, 19.4
        
        Args:
            service: AWS service name
            operation: Operation that failed
            error_code: Error code
            error_message: Error message
            context: Error context
            
        Returns:
            Publication result
        """
        return self.publish_operator_alert(
            subject=f"AWS 500-Level Error in {service}",
            message=f"Operation '{operation}' failed with error {error_code}: {error_message}",
            severity="CRITICAL",
            context={
                'service': service,
                'operation': operation,
                'error_code': error_code,
                'error_message': error_message,
                **context
            }
        )


class PerformanceMetricsPublisher:
    """Publishes performance metrics to CloudWatch."""
    
    def __init__(self, namespace: str = "RosettaZero"):
        """
        Initialize Performance Metrics Publisher.
        
        Args:
            namespace: CloudWatch metrics namespace
        """
        self.cloudwatch_client = boto3.client('cloudwatch')
        self.namespace = namespace
    
    def publish_test_execution_duration(
        self,
        test_id: str,
        duration_ms: int,
        implementation_type: str
    ):
        """
        Publish test execution duration metric.
        
        Requirement: 29.1
        
        Args:
            test_id: Test identifier
            duration_ms: Execution duration in milliseconds
            implementation_type: "legacy" or "modern"
        """
        self._publish_metric(
            metric_name='TestExecutionDuration',
            value=duration_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'ImplementationType', 'Value': implementation_type}
            ]
        )
        
        logger.info(
            "Published test execution duration metric",
            extra={
                'test_id': test_id,
                'duration_ms': duration_ms,
                'implementation_type': implementation_type
            }
        )
    
    def publish_test_throughput(
        self,
        tests_per_second: float,
        component: str
    ):
        """
        Publish test throughput metric.
        
        Requirement: 29.2
        
        Args:
            tests_per_second: Number of tests executed per second
            component: Component name
        """
        self._publish_metric(
            metric_name='TestThroughput',
            value=tests_per_second,
            unit='Count/Second',
            dimensions=[
                {'Name': 'Component', 'Value': component}
            ]
        )
        
        logger.info(
            "Published test throughput metric",
            extra={
                'tests_per_second': tests_per_second,
                'component': component
            }
        )
    
    def publish_api_latency(
        self,
        service: str,
        operation: str,
        latency_ms: int
    ):
        """
        Publish AWS service API latency metric.
        
        Requirement: 29.3
        
        Args:
            service: AWS service name
            operation: API operation
            latency_ms: Latency in milliseconds
        """
        self._publish_metric(
            metric_name='APILatency',
            value=latency_ms,
            unit='Milliseconds',
            dimensions=[
                {'Name': 'Service', 'Value': service},
                {'Name': 'Operation', 'Value': operation}
            ]
        )
        
        logger.info(
            "Published API latency metric",
            extra={
                'service': service,
                'operation': operation,
                'latency_ms': latency_ms
            }
        )
    
    def publish_resource_utilization(
        self,
        resource_type: str,
        utilization_percent: float,
        component: str
    ):
        """
        Publish resource utilization metric.
        
        Requirement: 29.4
        
        Args:
            resource_type: Type of resource (CPU, Memory, etc.)
            utilization_percent: Utilization percentage
            component: Component name
        """
        self._publish_metric(
            metric_name='ResourceUtilization',
            value=utilization_percent,
            unit='Percent',
            dimensions=[
                {'Name': 'ResourceType', 'Value': resource_type},
                {'Name': 'Component', 'Value': component}
            ]
        )
        
        logger.info(
            "Published resource utilization metric",
            extra={
                'resource_type': resource_type,
                'utilization_percent': utilization_percent,
                'component': component
            }
        )
    
    def _publish_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        dimensions: List[Dict[str, str]]
    ):
        """
        Publish metric to CloudWatch.
        
        Args:
            metric_name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Metric dimensions
        """
        try:
            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Value': value,
                        'Unit': unit,
                        'Timestamp': datetime.utcnow(),
                        'Dimensions': dimensions
                    }
                ]
            )
        except ClientError as e:
            log_error(
                component='performance_metrics_publisher',
                error_type=e.response['Error']['Code'],
                error_message=str(e),
                context={
                    'metric_name': metric_name,
                    'value': value,
                    'unit': unit
                }
            )
            # Don't raise - metrics publishing failures shouldn't break the workflow
