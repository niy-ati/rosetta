"""
Dashboard API Lambda handler.

Provides REST API endpoints for the Rosetta Zero Web Dashboard.
"""

import json
import os
import boto3
from typing import Dict, Any
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import NotFoundError, BadRequestError

logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()

# AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
cloudwatch = boto3.client('cloudwatch')

# Environment variables
STACK_NAME = os.environ.get('STACK_NAME', 'RosettaZeroStack-dev')


@app.get("/dashboard/stats")
@tracer.capture_method
def get_dashboard_stats():
    """Get dashboard overview statistics."""
    try:
        # Get workflow phases table
        workflow_table = dynamodb.Table(f"{STACK_NAME}-workflow-phases")
        
        # Count active workflows
        response = workflow_table.scan(
            FilterExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'in-progress'}
        )
        active_workflows = len(response.get('Items', []))
        
        # Get test results table
        test_results_table = dynamodb.Table(f"{STACK_NAME}-test-results")
        test_response = test_results_table.scan()
        total_tests = len(test_response.get('Items', []))
        
        # Count artifacts from S3
        artifacts_bucket = f"{STACK_NAME}-legacy-artifacts"
        try:
            artifacts_response = s3_client.list_objects_v2(Bucket=artifacts_bucket)
            total_artifacts = artifacts_response.get('KeyCount', 0)
        except:
            total_artifacts = 0
        
        # Count certificates from S3
        certificates_bucket = f"{STACK_NAME}-certificates"
        try:
            certs_response = s3_client.list_objects_v2(Bucket=certificates_bucket)
            total_certificates = certs_response.get('KeyCount', 0)
        except:
            total_certificates = 0
        
        # Get recent certificates (mock data for now)
        recent_certificates = []
        
        # Get system health metrics
        system_health = {
            'lambdaMetrics': {
                'errorRate': 0.001,
                'invocations': 1000,
                'duration': 250,
                'throttles': 0
            },
            'stepFunctionsMetrics': {
                'executionsStarted': 50,
                'executionsSucceeded': 48,
                'executionsFailed': 2,
                'executionsTimedOut': 0
            },
            's3Metrics': {
                'totalBuckets': 9,
                'totalObjects': total_artifacts + total_certificates,
                'totalSize': 1024 * 1024 * 100,  # 100 MB
                'bucketUtilization': []
            },
            'dynamoDBMetrics': {
                'readCapacityUtilization': 25.5,
                'writeCapacityUtilization': 15.2,
                'itemCount': total_tests
            },
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        return {
            'success': True,
            'data': {
                'totalArtifacts': total_artifacts,
                'totalTests': total_tests,
                'totalCertificates': total_certificates,
                'activeWorkflows': active_workflows,
                'recentCertificates': recent_certificates,
                'systemHealth': system_health
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/artifacts")
@tracer.capture_method
def get_artifacts():
    """Get list of artifacts."""
    page = int(app.current_event.get_query_string_value('page', '1'))
    page_size = int(app.current_event.get_query_string_value('pageSize', '50'))
    status = app.current_event.get_query_string_value('status', None)
    
    try:
        # Mock data for now - in production, query from DynamoDB or S3
        artifacts = []
        
        return {
            'success': True,
            'data': {
                'items': artifacts,
                'total': len(artifacts),
                'page': page,
                'pageSize': page_size,
                'totalPages': 1
            }
        }
    except Exception as e:
        logger.error(f"Error getting artifacts: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/artifacts/<artifact_id>")
@tracer.capture_method
def get_artifact(artifact_id: str):
    """Get artifact details."""
    try:
        # Mock data for now
        artifact = {
            'artifactId': artifact_id,
            'name': 'sample.cob',
            'type': 'COBOL',
            'size': 1024 * 50,
            'uploadedAt': '2024-01-01T00:00:00Z',
            'uploadedBy': 'user@example.com',
            'status': 'completed',
            's3Key': f'artifacts/{artifact_id}',
            'hash': 'abc123'
        }
        
        return {
            'success': True,
            'data': artifact
        }
    except Exception as e:
        logger.error(f"Error getting artifact: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.post("/artifacts/upload")
@tracer.capture_method
def upload_artifact():
    """Handle artifact upload."""
    try:
        # In production, this would handle multipart upload to S3
        # and trigger the ingestion workflow
        
        return {
            'success': True,
            'data': {
                'artifactId': 'artifact-123',
                'workflowId': 'workflow-123'
            },
            'message': 'Upload successful'
        }
    except Exception as e:
        logger.error(f"Error uploading artifact: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/workflows")
@tracer.capture_method
def get_workflows():
    """Get list of workflows."""
    try:
        workflow_table = dynamodb.Table(f"{STACK_NAME}-workflow-phases")
        response = workflow_table.scan()
        
        workflows = response.get('Items', [])
        
        return {
            'success': True,
            'data': {
                'items': workflows,
                'total': len(workflows),
                'page': 1,
                'pageSize': 50,
                'totalPages': 1
            }
        }
    except Exception as e:
        logger.error(f"Error getting workflows: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/workflows/<workflow_id>")
@tracer.capture_method
def get_workflow(workflow_id: str):
    """Get workflow details."""
    try:
        workflow_table = dynamodb.Table(f"{STACK_NAME}-workflow-phases")
        response = workflow_table.get_item(Key={'workflow_id': workflow_id})
        
        workflow = response.get('Item')
        if not workflow:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        
        return {
            'success': True,
            'data': workflow
        }
    except Exception as e:
        logger.error(f"Error getting workflow: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@app.get("/system/health")
@tracer.capture_method
def get_system_health():
    """Get system health metrics."""
    try:
        # In production, query CloudWatch metrics
        health = {
            'lambdaMetrics': {
                'errorRate': 0.001,
                'invocations': 1000,
                'duration': 250,
                'throttles': 0
            },
            'stepFunctionsMetrics': {
                'executionsStarted': 50,
                'executionsSucceeded': 48,
                'executionsFailed': 2,
                'executionsTimedOut': 0
            },
            's3Metrics': {
                'totalBuckets': 9,
                'totalObjects': 100,
                'totalSize': 1024 * 1024 * 100,
                'bucketUtilization': []
            },
            'dynamoDBMetrics': {
                'readCapacityUtilization': 25.5,
                'writeCapacityUtilization': 15.2,
                'itemCount': 1000
            },
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        return {
            'success': True,
            'data': health
        }
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for Dashboard API."""
    return app.resolve(event, context)
