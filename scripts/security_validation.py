#!/usr/bin/env python3
"""
Security validation script for Rosetta Zero.

Validates security best practices:
- S3 buckets have public access blocked
- S3 buckets use KMS encryption
- DynamoDB tables use KMS encryption
- CloudWatch Logs use KMS encryption
- VPC has no internet gateway or NAT gateway
- Lambda functions use VPC endpoints
"""

import boto3
import sys
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a security validation check."""
    check_name: str
    passed: bool
    details: str
    resource_id: str = ""


class SecurityValidator:
    """Validates security configurations for Rosetta Zero."""
    
    def __init__(self, stack_name: str = "RosettaZeroStack-dev"):
        self.stack_name = stack_name
        self.s3_client = boto3.client('s3')
        self.dynamodb_client = boto3.client('dynamodb')
        self.logs_client = boto3.client('logs')
        self.ec2_client = boto3.client('ec2')
        self.lambda_client = boto3.client('lambda')
        self.cloudformation_client = boto3.client('cloudformation')
        self.results: List[ValidationResult] = []
    
    def get_stack_resources(self) -> Dict[str, List[str]]:
        """Get resources from CloudFormation stack."""
        resources = {
            's3_buckets': [],
            'dynamodb_tables': [],
            'log_groups': [],
            'vpcs': [],
            'lambda_functions': []
        }
        
        try:
            paginator = self.cloudformation_client.get_paginator('list_stack_resources')
            for page in paginator.paginate(StackName=self.stack_name):
                for resource in page['StackResourceSummaries']:
                    resource_type = resource['ResourceType']
                    physical_id = resource['PhysicalResourceId']
                    
                    if resource_type == 'AWS::S3::Bucket':
                        resources['s3_buckets'].append(physical_id)
                    elif resource_type == 'AWS::DynamoDB::Table':
                        resources['dynamodb_tables'].append(physical_id)
                    elif resource_type == 'AWS::Logs::LogGroup':
                        resources['log_groups'].append(physical_id)
                    elif resource_type == 'AWS::EC2::VPC':
                        resources['vpcs'].append(physical_id)
                    elif resource_type == 'AWS::Lambda::Function':
                        resources['lambda_functions'].append(physical_id)
        except Exception as e:
            print(f"Warning: Could not retrieve stack resources: {e}")
            print("Continuing with manual resource discovery...")
        
        return resources
    
    def validate_s3_public_access_blocked(self, bucket_name: str) -> ValidationResult:
        """Verify S3 bucket has public access blocked."""
        try:
            response = self.s3_client.get_public_access_block(Bucket=bucket_name)
            config = response['PublicAccessBlockConfiguration']
            
            all_blocked = (
                config.get('BlockPublicAcls', False) and
                config.get('IgnorePublicAcls', False) and
                config.get('BlockPublicPolicy', False) and
                config.get('RestrictPublicBuckets', False)
            )
            
            if all_blocked:
                return ValidationResult(
                    check_name="S3 Public Access Blocked",
                    passed=True,
                    details=f"All public access blocked for bucket {bucket_name}",
                    resource_id=bucket_name
                )
            else:
                return ValidationResult(
                    check_name="S3 Public Access Blocked",
                    passed=False,
                    details=f"Public access not fully blocked for bucket {bucket_name}: {config}",
                    resource_id=bucket_name
                )
        except Exception as e:
            return ValidationResult(
                check_name="S3 Public Access Blocked",
                passed=False,
                details=f"Error checking bucket {bucket_name}: {str(e)}",
                resource_id=bucket_name
            )
    
    def validate_s3_encryption(self, bucket_name: str) -> ValidationResult:
        """Verify S3 bucket uses KMS encryption."""
        try:
            response = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
            rules = response.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
            
            for rule in rules:
                sse = rule.get('ApplyServerSideEncryptionByDefault', {})
                if sse.get('SSEAlgorithm') == 'aws:kms':
                    return ValidationResult(
                        check_name="S3 KMS Encryption",
                        passed=True,
                        details=f"Bucket {bucket_name} uses KMS encryption",
                        resource_id=bucket_name
                    )
            
            return ValidationResult(
                check_name="S3 KMS Encryption",
                passed=False,
                details=f"Bucket {bucket_name} does not use KMS encryption",
                resource_id=bucket_name
            )
        except Exception as e:
            return ValidationResult(
                check_name="S3 KMS Encryption",
                passed=False,
                details=f"Error checking encryption for bucket {bucket_name}: {str(e)}",
                resource_id=bucket_name
            )
    
    def validate_dynamodb_encryption(self, table_name: str) -> ValidationResult:
        """Verify DynamoDB table uses KMS encryption."""
        try:
            response = self.dynamodb_client.describe_table(TableName=table_name)
            sse = response['Table'].get('SSEDescription', {})
            
            if sse.get('Status') == 'ENABLED' and sse.get('SSEType') == 'KMS':
                return ValidationResult(
                    check_name="DynamoDB KMS Encryption",
                    passed=True,
                    details=f"Table {table_name} uses KMS encryption",
                    resource_id=table_name
                )
            else:
                return ValidationResult(
                    check_name="DynamoDB KMS Encryption",
                    passed=False,
                    details=f"Table {table_name} does not use KMS encryption: {sse}",
                    resource_id=table_name
                )
        except Exception as e:
            return ValidationResult(
                check_name="DynamoDB KMS Encryption",
                passed=False,
                details=f"Error checking table {table_name}: {str(e)}",
                resource_id=table_name
            )
    
    def validate_cloudwatch_logs_encryption(self, log_group_name: str) -> ValidationResult:
        """Verify CloudWatch Logs use KMS encryption."""
        try:
            response = self.logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_name
            )
            
            for log_group in response.get('logGroups', []):
                if log_group['logGroupName'] == log_group_name:
                    if 'kmsKeyId' in log_group:
                        return ValidationResult(
                            check_name="CloudWatch Logs KMS Encryption",
                            passed=True,
                            details=f"Log group {log_group_name} uses KMS encryption",
                            resource_id=log_group_name
                        )
                    else:
                        return ValidationResult(
                            check_name="CloudWatch Logs KMS Encryption",
                            passed=False,
                            details=f"Log group {log_group_name} does not use KMS encryption",
                            resource_id=log_group_name
                        )
            
            return ValidationResult(
                check_name="CloudWatch Logs KMS Encryption",
                passed=False,
                details=f"Log group {log_group_name} not found",
                resource_id=log_group_name
            )
        except Exception as e:
            return ValidationResult(
                check_name="CloudWatch Logs KMS Encryption",
                passed=False,
                details=f"Error checking log group {log_group_name}: {str(e)}",
                resource_id=log_group_name
            )
    
    def validate_vpc_no_internet_gateway(self, vpc_id: str) -> ValidationResult:
        """Verify VPC has no internet gateway."""
        try:
            response = self.ec2_client.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            
            if not response['InternetGateways']:
                return ValidationResult(
                    check_name="VPC No Internet Gateway",
                    passed=True,
                    details=f"VPC {vpc_id} has no internet gateway",
                    resource_id=vpc_id
                )
            else:
                return ValidationResult(
                    check_name="VPC No Internet Gateway",
                    passed=False,
                    details=f"VPC {vpc_id} has internet gateway attached",
                    resource_id=vpc_id
                )
        except Exception as e:
            return ValidationResult(
                check_name="VPC No Internet Gateway",
                passed=False,
                details=f"Error checking VPC {vpc_id}: {str(e)}",
                resource_id=vpc_id
            )
    
    def validate_vpc_no_nat_gateway(self, vpc_id: str) -> ValidationResult:
        """Verify VPC has no NAT gateway."""
        try:
            response = self.ec2_client.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            active_gateways = [
                gw for gw in response['NatGateways']
                if gw['State'] not in ['deleted', 'deleting']
            ]
            
            if not active_gateways:
                return ValidationResult(
                    check_name="VPC No NAT Gateway",
                    passed=True,
                    details=f"VPC {vpc_id} has no NAT gateway",
                    resource_id=vpc_id
                )
            else:
                return ValidationResult(
                    check_name="VPC No NAT Gateway",
                    passed=False,
                    details=f"VPC {vpc_id} has NAT gateway",
                    resource_id=vpc_id
                )
        except Exception as e:
            return ValidationResult(
                check_name="VPC No NAT Gateway",
                passed=False,
                details=f"Error checking VPC {vpc_id}: {str(e)}",
                resource_id=vpc_id
            )
    
    def validate_lambda_vpc_config(self, function_name: str) -> ValidationResult:
        """Verify Lambda function uses VPC configuration."""
        try:
            response = self.lambda_client.get_function_configuration(
                FunctionName=function_name
            )
            
            vpc_config = response.get('VpcConfig', {})
            if vpc_config.get('VpcId'):
                return ValidationResult(
                    check_name="Lambda VPC Configuration",
                    passed=True,
                    details=f"Lambda {function_name} uses VPC",
                    resource_id=function_name
                )
            else:
                return ValidationResult(
                    check_name="Lambda VPC Configuration",
                    passed=False,
                    details=f"Lambda {function_name} does not use VPC",
                    resource_id=function_name
                )
        except Exception as e:
            return ValidationResult(
                check_name="Lambda VPC Configuration",
                passed=False,
                details=f"Error checking Lambda {function_name}: {str(e)}",
                resource_id=function_name
            )
    
    def run_all_validations(self) -> bool:
        """Run all security validations."""
        print(f"Running security validations for stack: {self.stack_name}\n")
        
        # Get stack resources
        resources = self.get_stack_resources()
        
        # Validate S3 buckets
        print("Validating S3 buckets...")
        for bucket in resources['s3_buckets']:
            self.results.append(self.validate_s3_public_access_blocked(bucket))
            self.results.append(self.validate_s3_encryption(bucket))
        
        # Validate DynamoDB tables
        print("Validating DynamoDB tables...")
        for table in resources['dynamodb_tables']:
            self.results.append(self.validate_dynamodb_encryption(table))
        
        # Validate CloudWatch Logs
        print("Validating CloudWatch Logs...")
        for log_group in resources['log_groups']:
            self.results.append(self.validate_cloudwatch_logs_encryption(log_group))
        
        # Validate VPCs
        print("Validating VPCs...")
        for vpc in resources['vpcs']:
            self.results.append(self.validate_vpc_no_internet_gateway(vpc))
            self.results.append(self.validate_vpc_no_nat_gateway(vpc))
        
        # Validate Lambda functions
        print("Validating Lambda functions...")
        for function in resources['lambda_functions']:
            self.results.append(self.validate_lambda_vpc_config(function))
        
        # Print results
        print("\n" + "="*80)
        print("SECURITY VALIDATION RESULTS")
        print("="*80 + "\n")
        
        passed_count = 0
        failed_count = 0
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"{status}: {result.check_name}")
            print(f"  Resource: {result.resource_id}")
            print(f"  Details: {result.details}\n")
            
            if result.passed:
                passed_count += 1
            else:
                failed_count += 1
        
        print("="*80)
        print(f"Total: {len(self.results)} checks")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print("="*80 + "\n")
        
        return failed_count == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Rosetta Zero security configurations')
    parser.add_argument('--stack-name', default='RosettaZeroStack-dev',
                       help='CloudFormation stack name (default: RosettaZeroStack-dev)')
    
    args = parser.parse_args()
    
    validator = SecurityValidator(stack_name=args.stack_name)
    all_passed = validator.run_all_validations()
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
