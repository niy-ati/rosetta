"""
Local development server for Rosetta Zero Dashboard API.

This provides a mock backend API for local development without AWS.
Run with: python backend-local/server.py
"""

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import json
import os
import uuid
from datetime import datetime, timedelta
import random
import hashlib

app = Flask(__name__)
CORS(app)  # Enable CORS for local development

# Mock data storage
workflows = {}
artifacts = {}
test_results = {}
certificates = {}

COMPANIES = ["Accenture Federal", "Lockheed Martin", "Northrop Grumman", "Raytheon Technologies", "Boeing Defense"]
PROJECTS = ["COBOL Banking System", "FORTRAN Weather Simulation", "Legacy Payroll System", "Mainframe Transaction Processor", "Defense Logistics Platform"]

def generate_realistic_hash():
    """Generate realistic SHA-256 hash"""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

def generate_certificate_id():
    """Generate realistic certificate ID"""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"RZ-CERT-{timestamp}-{uuid.uuid4().hex[:8].upper()}"

def generate_workflow_id():
    """Generate realistic workflow ID"""
    return f"WF-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:12].upper()}"

def generate_artifact_id():
    """Generate realistic artifact ID"""
    return f"ART-{datetime.now().year}-{uuid.uuid4().hex[:10].upper()}"

# Initialize with some mock data
def init_mock_data():
    # Create sample artifacts with realistic data
    artifact_types = ["COBOL", "FORTRAN", "BINARY"]
    for i in range(5):
        artifact_id = generate_artifact_id()
        project_name = PROJECTS[i % len(PROJECTS)]
        company = COMPANIES[i % len(COMPANIES)]
        
        artifacts[artifact_id] = {
            "artifactId": artifact_id,
            "name": f"{project_name.lower().replace(' ', '-')}-v{random.randint(1,5)}.{random.randint(0,9)}.cob",
            "type": artifact_types[i % len(artifact_types)],
            "size": random.randint(50000, 500000),
            "uploadedAt": (datetime.now() - timedelta(days=random.randint(5, 45))).isoformat() + "Z",
            "uploadedBy": f"{company.lower().replace(' ', '.')}@enterprise.com",
            "status": random.choice(["processing", "completed", "completed", "completed"]),
            "s3Key": f"legacy-artifacts/{artifact_id}/{project_name.lower().replace(' ', '-')}",
            "hash": generate_realistic_hash(),
            "workflowId": f"WF-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:12].upper()}",
            "metadata": {
                "company": company,
                "project": project_name,
                "linesOfCode": random.randint(10000, 100000),
                "complexity": random.choice(["High", "Very High", "Critical"])
            }
        }

    phases = ["Discovery", "Synthesis", "Aggression", "Validation", "Trust"]
    for i, (artifact_id, artifact) in enumerate(artifacts.items()):
        workflow_id = artifact["workflowId"]
        current_phase_idx = random.randint(2, 4)  # Most are in later stages
        
        workflows[workflow_id] = {
            "workflowId": workflow_id,
            "artifactId": artifact_id,
            "artifactName": artifact["name"],
            "status": "completed" if current_phase_idx == 4 else "processing",
            "currentPhase": phases[current_phase_idx],
            "phases": [
                {
                    "name": phase,
                    "status": "completed" if idx < current_phase_idx else ("in-progress" if idx == current_phase_idx else "pending"),
                    "startedAt": (datetime.now() - timedelta(hours=48-idx*8)).isoformat() + "Z" if idx <= current_phase_idx else None,
                    "completedAt": (datetime.now() - timedelta(hours=40-idx*8)).isoformat() + "Z" if idx < current_phase_idx else None,
                    "progress": 100 if idx < current_phase_idx else (random.randint(65, 95) if idx == current_phase_idx else 0)
                }
                for idx, phase in enumerate(phases)
            ],
            "createdAt": (datetime.now() - timedelta(days=random.randint(10, 60))).isoformat() + "Z",
            "updatedAt": datetime.now().isoformat() + "Z",
            "completedAt": (datetime.now() - timedelta(days=random.randint(1, 5))).isoformat() + "Z" if current_phase_idx == 4 else None,
            "metadata": artifact["metadata"]
        }

    completed_workflows = [wf for wf in workflows.values() if wf["status"] == "completed"]
    for i, workflow in enumerate(completed_workflows[:3]):
        cert_id = generate_certificate_id()
        test_count = random.randint(500000, 2500000)  # Realistic large-scale testing
        
        certificates[cert_id] = {
            "certificateId": cert_id,
            "workflowId": workflow["workflowId"],
            "artifactId": workflow["artifactId"],
            "testCount": test_count,
            "testResultsHash": generate_realistic_hash(),
            "coveragePercentage": round(random.uniform(97.5, 99.9), 2),
            "generatedAt": (datetime.now() - timedelta(days=random.randint(1, 15))).isoformat() + "Z",
            "signature": generate_realistic_hash(),
            "signingKeyId": f"arn:aws:kms:us-east-1:123456789012:key/{uuid.uuid4()}",
            "signingAlgorithm": "RSASSA-PSS-SHA-256",
            "legacyArtifactMetadata": {
                "identifier": workflow["artifactId"],
                "version": f"{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,20)}",
                "hash": generate_realistic_hash(),
                "s3Location": f"s3://rosetta-zero-legacy-artifacts-prod/{workflow['artifactId']}"
            },
            "modernImplementationMetadata": {
                "identifier": f"MOD-{workflow['artifactId'][-10:]}",
                "version": "1.0.0",
                "hash": generate_realistic_hash(),
                "s3Location": f"s3://rosetta-zero-modern-impl-prod/MOD-{workflow['artifactId'][-10:]}"
            },
            "complianceMetadata": {
                "standard": "ISO/IEC 25010:2011",
                "auditor": "Ernst & Young LLP",
                "certificationDate": datetime.now().isoformat() + "Z",
                "validUntil": (datetime.now() + timedelta(days=365)).isoformat() + "Z"
            }
        }

init_mock_data()

@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    active_workflows = len([w for w in workflows.values() if w['status'] == 'processing'])
    total_tests = sum(random.randint(10000, 100000) for _ in workflows)
    
    return jsonify({
        "success": True,
        "data": {
            "totalArtifacts": len(artifacts),
            "totalTests": total_tests,
            "totalCertificates": len(certificates),
            "activeWorkflows": active_workflows,
            "recentCertificates": list(certificates.values())[:5],
            "systemHealth": {
                "lambdaMetrics": {
                    "errorRate": 0.001,
                    "invocations": 1000,
                    "duration": 250,
                    "throttles": 0
                },
                "stepFunctionsMetrics": {
                    "executionsStarted": 50,
                    "executionsSucceeded": 48,
                    "executionsFailed": 2,
                    "executionsTimedOut": 0
                },
                "s3Metrics": {
                    "totalBuckets": 9,
                    "totalObjects": len(artifacts) + len(certificates),
                    "totalSize": 104857600,
                    "bucketUtilization": []
                },
                "dynamoDBMetrics": {
                    "readCapacityUtilization": 25.5,
                    "writeCapacityUtilization": 15.2,
                    "itemCount": total_tests
                },
                "timestamp": datetime.now().isoformat() + "Z"
            }
        }
    })

@app.route('/api/artifacts', methods=['GET'])
def get_artifacts():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 50))
    status = request.args.get('status', None)
    
    filtered_artifacts = list(artifacts.values())
    if status:
        filtered_artifacts = [a for a in filtered_artifacts if a['status'] == status]
    
    return jsonify({
        "success": True,
        "data": {
            "items": filtered_artifacts,
            "total": len(filtered_artifacts),
            "page": page,
            "pageSize": page_size,
            "totalPages": (len(filtered_artifacts) + page_size - 1) // page_size
        }
    })

@app.route('/api/artifacts/<artifact_id>', methods=['GET'])
def get_artifact(artifact_id):
    artifact = artifacts.get(artifact_id)
    if not artifact:
        return jsonify({"success": False, "error": "Artifact not found"}), 404
    
    return jsonify({"success": True, "data": artifact})

@app.route('/api/artifacts/upload', methods=['POST'])
def upload_artifact():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['file']
    artifact_id = f"artifact-{len(artifacts) + 1}"
    workflow_id = f"workflow-{len(workflows) + 1}"
    
    # Create new artifact
    artifacts[artifact_id] = {
        "artifactId": artifact_id,
        "name": file.filename,
        "type": "COBOL" if file.filename.endswith('.cob') else "FORTRAN" if file.filename.endswith('.f') else "BINARY",
        "size": len(file.read()),
        "uploadedAt": datetime.now().isoformat() + "Z",
        "uploadedBy": "admin@example.com",
        "status": "processing",
        "s3Key": f"artifacts/{artifact_id}",
        "hash": f"hash-{uuid.uuid4().hex[:16]}",
        "workflowId": workflow_id
    }
    
    # Create new workflow
    workflows[workflow_id] = {
        "workflowId": workflow_id,
        "artifactId": artifact_id,
        "artifactName": file.filename,
        "status": "processing",
        "currentPhase": "Discovery",
        "phases": [
            {"name": "Discovery", "status": "in-progress", "startedAt": datetime.now().isoformat() + "Z", "progress": 10},
            {"name": "Synthesis", "status": "pending"},
            {"name": "Aggression", "status": "pending"},
            {"name": "Validation", "status": "pending"},
            {"name": "Trust", "status": "pending"}
        ],
        "createdAt": datetime.now().isoformat() + "Z",
        "updatedAt": datetime.now().isoformat() + "Z"
    }
    
    return jsonify({
        "success": True,
        "data": {
            "artifactId": artifact_id,
            "workflowId": workflow_id
        },
        "message": "Upload successful"
    })

@app.route('/api/artifacts/<artifact_id>/download', methods=['GET'])
def download_artifact(artifact_id):
    return jsonify({
        "success": True,
        "data": {
            "presignedUrl": f"http://localhost:5000/api/download/{artifact_id}"
        }
    })

@app.route('/api/workflows', methods=['GET'])
def get_workflows():
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('pageSize', 50))
    status = request.args.get('status', None)
    
    filtered_workflows = list(workflows.values())
    if status:
        filtered_workflows = [w for w in filtered_workflows if w['status'] == status]
    
    return jsonify({
        "success": True,
        "data": {
            "items": filtered_workflows,
            "total": len(filtered_workflows),
            "page": page,
            "pageSize": page_size,
            "totalPages": (len(filtered_workflows) + page_size - 1) // page_size
        }
    })

@app.route('/api/workflows/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    workflow = workflows.get(workflow_id)
    if not workflow:
        return jsonify({"success": False, "error": "Workflow not found"}), 404
    
    return jsonify({"success": True, "data": workflow})

@app.route('/api/workflows/search', methods=['GET'])
def search_workflows():
    query = request.args.get('q', '').lower()
    results = [w for w in workflows.values() if query in w['workflowId'].lower() or query in w['artifactName'].lower()]
    return jsonify({"success": True, "data": results})

@app.route('/api/workflows/<workflow_id>/tests', methods=['GET'])
def get_test_results(workflow_id):
    # Generate mock test results
    test_count = random.randint(50, 200)
    tests = [
        {
            "testId": f"test-{i}",
            "workflowId": workflow_id,
            "vectorId": f"vector-{i}",
            "status": "pass" if random.random() > 0.05 else "fail",
            "executionTimestamp": (datetime.now() - timedelta(minutes=i)).isoformat() + "Z",
            "legacyOutputHash": f"hash-{uuid.uuid4().hex[:16]}",
            "modernOutputHash": f"hash-{uuid.uuid4().hex[:16]}"
        }
        for i in range(test_count)
    ]
    
    return jsonify({
        "success": True,
        "data": {
            "items": tests,
            "total": len(tests),
            "page": 1,
            "pageSize": 100,
            "totalPages": (len(tests) + 99) // 100
        }
    })

@app.route('/api/workflows/<workflow_id>/tests/summary', methods=['GET'])
def get_test_summary(workflow_id):
    total = random.randint(100000, 1000000)
    passed = int(total * random.uniform(0.95, 0.99))
    
    return jsonify({
        "success": True,
        "data": {
            "totalTests": total,
            "passedTests": passed,
            "failedTests": total - passed,
            "passRate": (passed / total) * 100,
            "executionTime": random.randint(3600, 7200)
        }
    })

# Certificates endpoints
@app.route('/api/certificates', methods=['GET'])
def get_certificates():
    return jsonify({
        "success": True,
        "data": {
            "items": list(certificates.values()),
            "total": len(certificates),
            "page": 1,
            "pageSize": 50,
            "totalPages": 1
        }
    })

@app.route('/api/certificates/<cert_id>', methods=['GET'])
def get_certificate(cert_id):
    cert = certificates.get(cert_id)
    if not cert:
        return jsonify({"success": False, "error": "Certificate not found"}), 404
    
    return jsonify({"success": True, "data": cert})

@app.route('/api/certificates/<cert_id>/verify', methods=['POST'])
def verify_certificate(cert_id):
    return jsonify({
        "success": True,
        "data": {
            "valid": True,
            "keyId": "key-123"
        }
    })

@app.route('/api/system/health', methods=['GET'])
def get_system_health():
    return jsonify({
        "success": True,
        "data": {
            "lambdaMetrics": {
                "errorRate": random.uniform(0.001, 0.01),
                "invocations": random.randint(900, 1100),
                "duration": random.randint(200, 300),
                "throttles": 0
            },
            "stepFunctionsMetrics": {
                "executionsStarted": random.randint(45, 55),
                "executionsSucceeded": random.randint(43, 50),
                "executionsFailed": random.randint(0, 3),
                "executionsTimedOut": 0
            },
            "s3Metrics": {
                "totalBuckets": 9,
                "totalObjects": len(artifacts) + len(certificates),
                "totalSize": random.randint(90000000, 110000000),
                "bucketUtilization": []
            },
            "dynamoDBMetrics": {
                "readCapacityUtilization": random.uniform(20, 30),
                "writeCapacityUtilization": random.uniform(10, 20),
                "itemCount": random.randint(900, 1100)
            },
            "timestamp": datetime.now().isoformat() + "Z"
        }
    })

@app.route('/api/system/notifications', methods=['GET'])
def get_notifications():
    return jsonify({
        "success": True,
        "data": []
    })

# Compliance endpoints
@app.route('/api/compliance/reports', methods=['GET'])
def get_compliance_reports():
    return jsonify({
        "success": True,
        "data": {
            "items": [],
            "total": 0,
            "page": 1,
            "pageSize": 50,
            "totalPages": 0
        }
    })

@app.route('/api/compliance/reports', methods=['POST'])
def generate_compliance_report():
    report_id = f"report-{uuid.uuid4().hex[:8]}"
    return jsonify({
        "success": True,
        "data": {
            "reportId": report_id
        }
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify({
        "success": True,
        "data": {
            "logs": []
        }
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Rosetta Zero Dashboard - Local Development Server")
    print("=" * 60)
    print("\n📡 Backend API running at: http://localhost:5000")
    print("🌐 Frontend should run at: http://localhost:3000")
    print("\n💡 Mock data initialized:")
    print(f"   - {len(artifacts)} artifacts")
    print(f"   - {len(workflows)} workflows")
    print(f"   - {len(certificates)} certificates")
    print("\n⚠️  Note: This is a mock server for local development")
    print("   No AWS services are required\n")
    print("=" * 60)
    print("\nPress Ctrl+C to stop the server\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
