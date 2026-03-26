"""
Event publishing for certificate completion.

This module implements publishing of certificate generation events to EventBridge
and SNS notifications to operators.

Requirements: 17.9
"""

import json
from datetime import datetime
from typing import Optional
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def publish_completion_event(
    eventbridge_client,
    sns_client,
    event_bus_name: str,
    sns_topic_arn: Optional[str],
    certificate_id: str,
    s3_location: str,
    workflow_id: Optional[str] = None
) -> None:
    """
    Publish certificate generation completion event.
    
    This function:
    1. Publishes certificate generation event to EventBridge
    2. Includes certificate ID and S3 location in event
    3. Triggers SNS notification to operators
    
    Args:
        eventbridge_client: Boto3 EventBridge client
        sns_client: Boto3 SNS client
        event_bus_name: EventBridge event bus name
        sns_topic_arn: SNS topic ARN for operator notifications
        certificate_id: Generated certificate ID
        s3_location: S3 location of signed certificate
        workflow_id: Optional workflow ID for tracking
        
    Requirements: 17.9
    """
    
    logger.info("Publishing certificate completion event", extra={
        'certificate_id': certificate_id,
        's3_location': s3_location,
        'workflow_id': workflow_id
    })
    
    # Step 1: Publish to EventBridge
    event_detail = {
        'certificate_id': certificate_id,
        's3_location': s3_location,
        'workflow_id': workflow_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'phase': 'Trust',
        'status': 'COMPLETED'
    }
    
    try:
        eventbridge_response = eventbridge_client.put_events(
            Entries=[
                {
                    'Source': 'rosetta-zero.certificate-generator',
                    'DetailType': 'Certificate Generation Completed',
                    'Detail': json.dumps(event_detail),
                    'EventBusName': event_bus_name
                }
            ]
        )
        
        logger.info("EventBridge event published", extra={
            'certificate_id': certificate_id,
            'event_id': eventbridge_response.get('Entries', [{}])[0].get('EventId')
        })
        
    except Exception as e:
        logger.error("Failed to publish EventBridge event", extra={
            'error': str(e),
            'certificate_id': certificate_id
        })
        raise
    
    # Step 2: Send SNS notification to operators
    if sns_topic_arn:
        try:
            notification_message = {
                'subject': 'Rosetta Zero: Equivalence Certificate Generated',
                'certificate_id': certificate_id,
                's3_location': s3_location,
                'workflow_id': workflow_id,
                'timestamp': event_detail['timestamp'],
                'message': (
                    f"Equivalence certificate {certificate_id} has been successfully generated "
                    f"and cryptographically signed. The certificate is available at: {s3_location}"
                )
            }
            
            sns_response = sns_client.publish(
                TopicArn=sns_topic_arn,
                Subject='Rosetta Zero: Equivalence Certificate Generated',
                Message=json.dumps(notification_message, indent=2)
            )
            
            logger.info("SNS notification sent to operators", extra={
                'certificate_id': certificate_id,
                'message_id': sns_response.get('MessageId')
            })
            
        except Exception as e:
            logger.error("Failed to send SNS notification", extra={
                'error': str(e),
                'certificate_id': certificate_id
            })
            # Don't raise - SNS notification failure shouldn't fail the entire operation
    
    logger.info("Certificate completion event published successfully", extra={
        'certificate_id': certificate_id
    })
