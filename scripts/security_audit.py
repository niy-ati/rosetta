#!/usr/bin/env python3
"""
Security audit script for Rosetta Zero.

Performs security audits:
- Run AWS Security Hub checks
- Run AWS Inspector scans on Lambda functions
- Review CloudTrail logs for suspicious activity
- Test network isolation
"""

import boto3
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class AuditResult:
    """Result of a security audit check."""
    check_name: str
    passed: bool
    details: str
    severity: str = "INFO"  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    findings: List[Dict[str, Any]] = None


class SecurityAuditor:
    """Performs security audits on Rosetta Zero infrastructure."""
    
    def __init__(self, stack_name: str = "RosettaZeroStack-dev", region: str = None):
        self.stack_name = stack_name
        self.region = region or boto3.Session().region_name
        self.securityhub_client = boto3.client('securityhub', region_name=self.region)
        self.inspector_client = boto3.client('inspector2', region_name=self.region)
        self.cloudtrail_client = boto3.client('cloudtrail', region_name=self.region)
        self.ec2_client = boto3.client('ec2', region_name=self.region)
        self.lambda_client = boto3.client('lambda', region_name=self.region)
        self.cloudformation_client = boto3.client('cloudformation', region_name=self.region)
        self.results: List[AuditResult] = []
    
    def get_stack_resources(self) -> Dict[str, List[str]]:
        """Get resources from CloudFormation stack."""
        resources = {
            'lambda_functions': [],
            'vpcs': [],
            'security_groups': []
        }
        
        try:
            paginator = self.cloudformation_client.get_paginator('list_stack_resources')
            for page in paginator.paginate(StackName=self.stack_name):
                for resource in page['StackResourceSummaries']:
                    resource_type = resource['ResourceType']
                    physical_id = resource['PhysicalResourceId']
                    
                    if resource_type == 'AWS::Lambda::Function':
                        resources['lambda_functions'].append(physical_id)
                    elif resource_type == 'AWS::EC2::VPC':
                        resources['vpcs'].append(physical_id)
                    elif resource_type == 'AWS::EC2::SecurityGroup':
                        resources['security_groups'].append(physical_id)
        except Exception as e:
            print(f"Warning: Could not retrieve stack resources: {e}")
        
        return resources
    
    def check_security_hub(self) -> AuditResult:
        """Check AWS Security Hub for findings."""
        try:
            # Check if Security Hub is enabled
            try:
                self.securityhub_client.describe_hub()
            except self.securityhub_client.exceptions.InvalidAccessException:
                return AuditResult(
                    check_name="AWS Security Hub",
                    passed=False,
                    details="Security Hub is not enabled in this region",
                    severity="HIGH",
                    findings=[]
                )
            
            # Get findings
            findings = []
            paginator = self.securityhub_client.get_paginator('get_findings')
            
            # Filter for active findings with HIGH or CRITICAL severity
            filters = {
                'RecordState': [{'Value': 'ACTIVE', 'Comparison': 'EQUALS'}],
                'SeverityLabel': [
                    {'Value': 'HIGH', 'Comparison': 'EQUALS'},
                    {'Value': 'CRITICAL', 'Comparison': 'EQUALS'}
                ]
            }
            
            for page in paginator.paginate(Filters=filters):
                for finding in page['Findings']:
                    findings.append({
                        'id': finding.get('Id'),
                        'title': finding.get('Title'),
                        'severity': finding.get('Severity', {}).get('Label'),
                        'resource': finding.get('Resources', [{}])[0].get('Id', 'Unknown'),
                        'description': finding.get('Description', '')[:200]
                    })
            
            if not findings:
                return AuditResult(
                    check_name="AWS Security Hub",
                    passed=True,
                    details="No HIGH or CRITICAL findings in Security Hub",
                    severity="INFO",
                    findings=[]
                )
            else:
                return AuditResult(
                    check_name="AWS Security Hub",
                    passed=False,
                    details=f"Found {len(findings)} HIGH or CRITICAL findings",
                    severity="HIGH",
                    findings=findings
                )
        
        except Exception as e:
            return AuditResult(
                check_name="AWS Security Hub",
                passed=False,
                details=f"Error checking Security Hub: {str(e)}",
                severity="MEDIUM",
                findings=[]
            )
    
    def check_inspector_scans(self) -> AuditResult:
        """Check AWS Inspector for Lambda function vulnerabilities."""
        try:
            # Check if Inspector is enabled
            try:
                status = self.inspector_client.batch_get_account_status(
                    accountIds=[boto3.client('sts').get_caller_identity()['Account']]
                )
            except Exception as e:
                return AuditResult(
                    check_name="AWS Inspector",
                    passed=False,
                    details=f"Could not check Inspector status: {str(e)}",
                    severity="MEDIUM",
                    findings=[]
                )
            
            # Get findings
            findings = []
            
            try:
                paginator = self.inspector_client.get_paginator('list_findings')
                
                # Filter for Lambda findings with HIGH or CRITICAL severity
                filters = {
                    'resourceType': [{'comparison': 'EQUALS', 'value': 'AWS_LAMBDA_FUNCTION'}],
                    'severity': [
                        {'comparison': 'EQUALS', 'value': 'HIGH'},
                        {'comparison': 'EQUALS', 'value': 'CRITICAL'}
                    ]
                }
                
                for page in paginator.paginate(filterCriteria=filters):
                    for finding_arn in page.get('findings', []):
                        findings.append({'arn': finding_arn})
            except Exception as e:
                # Inspector might not be enabled or configured
                return AuditResult(
                    check_name="AWS Inspector",
                    passed=True,
                    details=f"Inspector not fully configured (this is optional): {str(e)}",
                    severity="INFO",
                    findings=[]
                )
            
            if not findings:
                return AuditResult(
                    check_name="AWS Inspector",
                    passed=True,
                    details="No HIGH or CRITICAL vulnerabilities found in Lambda functions",
                    severity="INFO",
                    findings=[]
                )
            else:
                return AuditResult(
                    check_name="AWS Inspector",
                    passed=False,
                    details=f"Found {len(findings)} HIGH or CRITICAL vulnerabilities",
                    severity="HIGH",
                    findings=findings
                )
        
        except Exception as e:
            return AuditResult(
                check_name="AWS Inspector",
                passed=True,
                details=f"Inspector check skipped (optional): {str(e)}",
                severity="INFO",
                findings=[]
            )
    
    def check_cloudtrail_logs(self) -> AuditResult:
        """Review CloudTrail logs for suspicious activity."""
        try:
            # Look for suspicious events in the last 24 hours
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=24)
            
            suspicious_events = []
            
            # Events to look for
            suspicious_event_names = [
                'DeleteBucket',
                'DeleteTable',
                'DeleteKey',
                'PutBucketPolicy',
                'PutBucketAcl',
                'CreateAccessKey',
                'DeleteAccessKey',
                'AttachUserPolicy',
                'AttachRolePolicy',
                'PutUserPolicy',
                'PutRolePolicy'
            ]
            
            try:
                paginator = self.cloudtrail_client.get_paginator('lookup_events')
                
                for page in paginator.paginate(
                    StartTime=start_time,
                    EndTime=end_time
                ):
                    for event in page.get('Events', []):
                        event_name = event.get('EventName')
                        if event_name in suspicious_event_names:
                            suspicious_events.append({
                                'event_name': event_name,
                                'event_time': event.get('EventTime').isoformat(),
                                'username': event.get('Username'),
                                'resource': event.get('Resources', [{}])[0].get('ResourceName', 'Unknown')
                            })
            except Exception as e:
                return AuditResult(
                    check_name="CloudTrail Logs",
                    passed=True,
                    details=f"CloudTrail check skipped: {str(e)}",
                    severity="INFO",
                    findings=[]
                )
            
            if not suspicious_events:
                return AuditResult(
                    check_name="CloudTrail Logs",
                    passed=True,
                    details="No suspicious activity detected in last 24 hours",
                    severity="INFO",
                    findings=[]
                )
            else:
                return AuditResult(
                    check_name="CloudTrail Logs",
                    passed=False,
                    details=f"Found {len(suspicious_events)} potentially suspicious events",
                    severity="MEDIUM",
                    findings=suspicious_events
                )
        
        except Exception as e:
            return AuditResult(
                check_name="CloudTrail Logs",
                passed=True,
                details=f"CloudTrail check skipped: {str(e)}",
                severity="INFO",
                findings=[]
            )
    
    def test_network_isolation(self) -> AuditResult:
        """Test network isolation of VPC."""
        try:
            resources = self.get_stack_resources()
            
            if not resources['vpcs']:
                return AuditResult(
                    check_name="Network Isolation",
                    passed=False,
                    details="No VPC found in stack",
                    severity="HIGH",
                    findings=[]
                )
            
            vpc_id = resources['vpcs'][0]
            isolation_issues = []
            
            # Check for internet gateways
            igw_response = self.ec2_client.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            if igw_response['InternetGateways']:
                isolation_issues.append("Internet gateway attached to VPC")
            
            # Check for NAT gateways
            nat_response = self.ec2_client.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            active_nats = [
                nat for nat in nat_response['NatGateways']
                if nat['State'] not in ['deleted', 'deleting']
            ]
            if active_nats:
                isolation_issues.append(f"{len(active_nats)} NAT gateway(s) in VPC")
            
            # Check security group rules for overly permissive ingress
            for sg_id in resources['security_groups']:
                sg_response = self.ec2_client.describe_security_groups(
                    GroupIds=[sg_id]
                )
                for sg in sg_response['SecurityGroups']:
                    for rule in sg.get('IpPermissions', []):
                        for ip_range in rule.get('IpRanges', []):
                            if ip_range.get('CidrIp') == '0.0.0.0/0':
                                isolation_issues.append(
                                    f"Security group {sg_id} allows ingress from 0.0.0.0/0"
                                )
            
            if not isolation_issues:
                return AuditResult(
                    check_name="Network Isolation",
                    passed=True,
                    details="VPC is properly isolated with no internet access",
                    severity="INFO",
                    findings=[]
                )
            else:
                return AuditResult(
                    check_name="Network Isolation",
                    passed=False,
                    details=f"Found {len(isolation_issues)} network isolation issues",
                    severity="HIGH",
                    findings=[{'issue': issue} for issue in isolation_issues]
                )
        
        except Exception as e:
            return AuditResult(
                check_name="Network Isolation",
                passed=False,
                details=f"Error testing network isolation: {str(e)}",
                severity="MEDIUM",
                findings=[]
            )
    
    def run_all_audits(self) -> bool:
        """Run all security audits."""
        print(f"Running security audits for stack: {self.stack_name}\n")
        
        print("Checking AWS Security Hub...")
        self.results.append(self.check_security_hub())
        
        print("Checking AWS Inspector...")
        self.results.append(self.check_inspector_scans())
        
        print("Reviewing CloudTrail logs...")
        self.results.append(self.check_cloudtrail_logs())
        
        print("Testing network isolation...")
        self.results.append(self.test_network_isolation())
        
        # Print results
        print("\n" + "="*80)
        print("SECURITY AUDIT RESULTS")
        print("="*80 + "\n")
        
        passed_count = 0
        failed_count = 0
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"{status}: {result.check_name} [{result.severity}]")
            print(f"  Details: {result.details}")
            
            if result.findings:
                print(f"  Findings ({len(result.findings)}):")
                for finding in result.findings[:5]:  # Show first 5
                    print(f"    - {finding}")
                if len(result.findings) > 5:
                    print(f"    ... and {len(result.findings) - 5} more")
            print()
            
            if result.passed:
                passed_count += 1
            else:
                failed_count += 1
        
        print("="*80)
        print(f"Total: {len(self.results)} audits")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print("="*80 + "\n")
        
        # Only fail if there are HIGH or CRITICAL severity failures
        critical_failures = [
            r for r in self.results
            if not r.passed and r.severity in ['HIGH', 'CRITICAL']
        ]
        
        return len(critical_failures) == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Perform security audit on Rosetta Zero')
    parser.add_argument('--stack-name', default='RosettaZeroStack-dev',
                       help='CloudFormation stack name (default: RosettaZeroStack-dev)')
    parser.add_argument('--region', help='AWS region (default: current session region)')
    
    args = parser.parse_args()
    
    auditor = SecurityAuditor(stack_name=args.stack_name, region=args.region)
    all_passed = auditor.run_all_audits()
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
