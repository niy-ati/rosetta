#!/usr/bin/env python3
"""
IAM policy validation script for Rosetta Zero.

Validates IAM policies follow least-privilege principle:
- Review all IAM roles and policies
- Verify no wildcard permissions except where required
- Verify no overly broad resource access
- Run IAM Access Analyzer
"""

import boto3
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class PolicyViolation:
    """Represents an IAM policy violation."""
    role_name: str
    policy_name: str
    violation_type: str
    details: str
    severity: str  # HIGH, MEDIUM, LOW


class IAMPolicyValidator:
    """Validates IAM policies for least-privilege compliance."""
    
    # Actions that are acceptable with wildcards in specific contexts
    ACCEPTABLE_WILDCARD_ACTIONS = {
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
        'kms:Decrypt',
        'kms:Encrypt',
        'kms:GenerateDataKey',
        'kms:DescribeKey',
        'ec2:CreateNetworkInterface',
        'ec2:DescribeNetworkInterfaces',
        'ec2:DeleteNetworkInterface',
        'ec2:AssignPrivateIpAddresses',
        'ec2:UnassignPrivateIpAddresses'
    }
    
    def __init__(self, stack_name: str = "RosettaZeroStack-dev"):
        self.stack_name = stack_name
        self.iam_client = boto3.client('iam')
        self.cloudformation_client = boto3.client('cloudformation')
        self.accessanalyzer_client = boto3.client('accessanalyzer')
        self.violations: List[PolicyViolation] = []
    
    def get_stack_roles(self) -> List[str]:
        """Get IAM roles from CloudFormation stack."""
        roles = []
        
        try:
            paginator = self.cloudformation_client.get_paginator('list_stack_resources')
            for page in paginator.paginate(StackName=self.stack_name):
                for resource in page['StackResourceSummaries']:
                    if resource['ResourceType'] == 'AWS::IAM::Role':
                        roles.append(resource['PhysicalResourceId'])
        except Exception as e:
            print(f"Warning: Could not retrieve stack resources: {e}")
        
        return roles
    
    def get_role_policies(self, role_name: str) -> Dict[str, Any]:
        """Get all policies attached to a role."""
        policies = {
            'inline': [],
            'managed': []
        }
        
        try:
            # Get inline policies
            inline_response = self.iam_client.list_role_policies(RoleName=role_name)
            for policy_name in inline_response.get('PolicyNames', []):
                policy_doc = self.iam_client.get_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name
                )
                policies['inline'].append({
                    'name': policy_name,
                    'document': policy_doc['PolicyDocument']
                })
            
            # Get managed policies
            managed_response = self.iam_client.list_attached_role_policies(RoleName=role_name)
            for policy in managed_response.get('AttachedPolicies', []):
                policy_arn = policy['PolicyArn']
                policy_version = self.iam_client.get_policy(PolicyArn=policy_arn)
                version_id = policy_version['Policy']['DefaultVersionId']
                policy_doc = self.iam_client.get_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=version_id
                )
                policies['managed'].append({
                    'name': policy['PolicyName'],
                    'arn': policy_arn,
                    'document': policy_doc['PolicyVersion']['Document']
                })
        except Exception as e:
            print(f"Error getting policies for role {role_name}: {e}")
        
        return policies
    
    def check_wildcard_actions(self, role_name: str, policy_name: str, 
                               statement: Dict[str, Any]) -> List[PolicyViolation]:
        """Check for wildcard actions in policy statements."""
        violations = []
        
        actions = statement.get('Action', [])
        if isinstance(actions, str):
            actions = [actions]
        
        resources = statement.get('Resource', [])
        if isinstance(resources, str):
            resources = [resources]
        
        for action in actions:
            if '*' in action:
                # Check if this is an acceptable wildcard
                if action not in self.ACCEPTABLE_WILDCARD_ACTIONS:
                    # Check if it's a service-level wildcard (e.g., "s3:*")
                    if action.endswith(':*'):
                        violations.append(PolicyViolation(
                            role_name=role_name,
                            policy_name=policy_name,
                            violation_type="Service-level wildcard action",
                            details=f"Action '{action}' grants all permissions for a service",
                            severity="HIGH"
                        ))
                    # Check if it's a complete wildcard
                    elif action == '*':
                        violations.append(PolicyViolation(
                            role_name=role_name,
                            policy_name=policy_name,
                            violation_type="Complete wildcard action",
                            details="Action '*' grants all permissions",
                            severity="HIGH"
                        ))
        
        return violations
    
    def check_wildcard_resources(self, role_name: str, policy_name: str,
                                 statement: Dict[str, Any]) -> List[PolicyViolation]:
        """Check for overly broad resource specifications."""
        violations = []
        
        resources = statement.get('Resource', [])
        if isinstance(resources, str):
            resources = [resources]
        
        actions = statement.get('Action', [])
        if isinstance(actions, str):
            actions = [actions]
        
        for resource in resources:
            if resource == '*':
                # Complete wildcard resource - check if actions justify it
                non_acceptable_actions = [
                    a for a in actions 
                    if a not in self.ACCEPTABLE_WILDCARD_ACTIONS
                ]
                
                if non_acceptable_actions:
                    violations.append(PolicyViolation(
                        role_name=role_name,
                        policy_name=policy_name,
                        violation_type="Wildcard resource with non-standard actions",
                        details=f"Resource '*' used with actions: {', '.join(non_acceptable_actions)}",
                        severity="HIGH"
                    ))
        
        return violations
    
    def check_overly_permissive_principals(self, role_name: str, policy_name: str,
                                           statement: Dict[str, Any]) -> List[PolicyViolation]:
        """Check for overly permissive principal specifications."""
        violations = []
        
        principal = statement.get('Principal', {})
        
        if principal == '*':
            violations.append(PolicyViolation(
                role_name=role_name,
                policy_name=policy_name,
                violation_type="Wildcard principal",
                details="Principal '*' allows any AWS account or user",
                severity="HIGH"
            ))
        elif isinstance(principal, dict):
            for principal_type, principal_values in principal.items():
                if principal_values == '*':
                    violations.append(PolicyViolation(
                        role_name=role_name,
                        policy_name=policy_name,
                        violation_type=f"Wildcard {principal_type} principal",
                        details=f"{principal_type} principal set to '*'",
                        severity="MEDIUM"
                    ))
        
        return violations
    
    def validate_policy_document(self, role_name: str, policy_name: str,
                                 policy_doc: Dict[str, Any]) -> List[PolicyViolation]:
        """Validate a policy document for least-privilege violations."""
        violations = []
        
        statements = policy_doc.get('Statement', [])
        if isinstance(statements, dict):
            statements = [statements]
        
        for statement in statements:
            # Only check Allow statements
            if statement.get('Effect') == 'Allow':
                violations.extend(self.check_wildcard_actions(role_name, policy_name, statement))
                violations.extend(self.check_wildcard_resources(role_name, policy_name, statement))
                violations.extend(self.check_overly_permissive_principals(role_name, policy_name, statement))
        
        return violations
    
    def validate_role(self, role_name: str) -> List[PolicyViolation]:
        """Validate all policies for a role."""
        violations = []
        
        print(f"Validating role: {role_name}")
        
        policies = self.get_role_policies(role_name)
        
        # Check inline policies
        for policy in policies['inline']:
            violations.extend(
                self.validate_policy_document(role_name, policy['name'], policy['document'])
            )
        
        # Check managed policies (only custom managed policies, not AWS managed)
        for policy in policies['managed']:
            if not policy['arn'].startswith('arn:aws:iam::aws:policy/'):
                violations.extend(
                    self.validate_policy_document(role_name, policy['name'], policy['document'])
                )
        
        return violations
    
    def run_access_analyzer(self) -> List[Dict[str, Any]]:
        """Run IAM Access Analyzer to find external access."""
        findings = []
        
        try:
            # List analyzers
            analyzers = self.accessanalyzer_client.list_analyzers()
            
            if not analyzers.get('analyzers'):
                print("Warning: No IAM Access Analyzer found. Creating one...")
                try:
                    analyzer_response = self.accessanalyzer_client.create_analyzer(
                        analyzerName='rosetta-zero-analyzer',
                        type='ACCOUNT'
                    )
                    analyzer_arn = analyzer_response['arn']
                    print(f"Created analyzer: {analyzer_arn}")
                except Exception as e:
                    print(f"Could not create analyzer: {e}")
                    return findings
            else:
                analyzer_arn = analyzers['analyzers'][0]['arn']
            
            # List findings
            paginator = self.accessanalyzer_client.get_paginator('list_findings')
            for page in paginator.paginate(analyzerArn=analyzer_arn):
                for finding in page.get('findings', []):
                    if finding['status'] == 'ACTIVE':
                        findings.append({
                            'id': finding['id'],
                            'resource_type': finding['resourceType'],
                            'resource': finding['resource'],
                            'principal': finding.get('principal', {}),
                            'condition': finding.get('condition', {}),
                            'action': finding.get('action', [])
                        })
        except Exception as e:
            print(f"Error running Access Analyzer: {e}")
        
        return findings
    
    def run_all_validations(self) -> bool:
        """Run all IAM policy validations."""
        print(f"Running IAM policy validations for stack: {self.stack_name}\n")
        
        # Get stack roles
        roles = self.get_stack_roles()
        print(f"Found {len(roles)} IAM roles in stack\n")
        
        # Validate each role
        for role in roles:
            role_violations = self.validate_role(role)
            self.violations.extend(role_violations)
        
        # Run Access Analyzer
        print("\nRunning IAM Access Analyzer...")
        access_findings = self.run_access_analyzer()
        
        # Print results
        print("\n" + "="*80)
        print("IAM POLICY VALIDATION RESULTS")
        print("="*80 + "\n")
        
        if not self.violations and not access_findings:
            print("✓ No IAM policy violations found\n")
            return True
        
        # Print violations by severity
        high_violations = [v for v in self.violations if v.severity == "HIGH"]
        medium_violations = [v for v in self.violations if v.severity == "MEDIUM"]
        low_violations = [v for v in self.violations if v.severity == "LOW"]
        
        if high_violations:
            print("HIGH SEVERITY VIOLATIONS:")
            print("-" * 80)
            for v in high_violations:
                print(f"Role: {v.role_name}")
                print(f"Policy: {v.policy_name}")
                print(f"Type: {v.violation_type}")
                print(f"Details: {v.details}\n")
        
        if medium_violations:
            print("MEDIUM SEVERITY VIOLATIONS:")
            print("-" * 80)
            for v in medium_violations:
                print(f"Role: {v.role_name}")
                print(f"Policy: {v.policy_name}")
                print(f"Type: {v.violation_type}")
                print(f"Details: {v.details}\n")
        
        if low_violations:
            print("LOW SEVERITY VIOLATIONS:")
            print("-" * 80)
            for v in low_violations:
                print(f"Role: {v.role_name}")
                print(f"Policy: {v.policy_name}")
                print(f"Type: {v.violation_type}")
                print(f"Details: {v.details}\n")
        
        if access_findings:
            print("IAM ACCESS ANALYZER FINDINGS:")
            print("-" * 80)
            for finding in access_findings:
                print(f"Finding ID: {finding['id']}")
                print(f"Resource Type: {finding['resource_type']}")
                print(f"Resource: {finding['resource']}")
                print(f"Principal: {finding.get('principal', 'N/A')}")
                print(f"Actions: {', '.join(finding.get('action', []))}\n")
        
        print("="*80)
        print(f"Total violations: {len(self.violations)}")
        print(f"  High: {len(high_violations)}")
        print(f"  Medium: {len(medium_violations)}")
        print(f"  Low: {len(low_violations)}")
        print(f"Access Analyzer findings: {len(access_findings)}")
        print("="*80 + "\n")
        
        # Fail if there are high severity violations
        return len(high_violations) == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Rosetta Zero IAM policies')
    parser.add_argument('--stack-name', default='RosettaZeroStack-dev',
                       help='CloudFormation stack name (default: RosettaZeroStack-dev)')
    
    args = parser.parse_args()
    
    validator = IAMPolicyValidator(stack_name=args.stack_name)
    all_passed = validator.run_all_validations()
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
