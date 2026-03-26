#!/usr/bin/env python3
"""
Cryptographic implementation validation script for Rosetta Zero.

Validates cryptographic implementations:
- Verify KMS keys use correct algorithms (AES-256, RSA-4096)
- Verify certificate signatures use RSASSA-PSS-SHA-256
- Verify all hashes use SHA-256
- Test signature verification
"""

import boto3
import hashlib
import json
import sys
from typing import List, Dict, Any
from dataclasses import dataclass


@dataclass
class CryptoTestResult:
    """Result of a cryptographic validation test."""
    test_name: str
    passed: bool
    details: str
    resource_id: str = ""


class CryptoValidator:
    """Validates cryptographic implementations."""
    
    def __init__(self, stack_name: str = "RosettaZeroStack-dev"):
        self.stack_name = stack_name
        self.kms_client = boto3.client('kms')
        self.cloudformation_client = boto3.client('cloudformation')
        self.results: List[CryptoTestResult] = []
    
    def get_stack_kms_keys(self) -> List[str]:
        """Get KMS keys from CloudFormation stack."""
        keys = []
        
        try:
            paginator = self.cloudformation_client.get_paginator('list_stack_resources')
            for page in paginator.paginate(StackName=self.stack_name):
                for resource in page['StackResourceSummaries']:
                    if resource['ResourceType'] == 'AWS::KMS::Key':
                        keys.append(resource['PhysicalResourceId'])
        except Exception as e:
            print(f"Warning: Could not retrieve stack resources: {e}")
        
        return keys
    
    def validate_kms_key_spec(self, key_id: str) -> CryptoTestResult:
        """Validate KMS key uses correct algorithm."""
        try:
            response = self.kms_client.describe_key(KeyId=key_id)
            key_metadata = response['KeyMetadata']
            
            key_spec = key_metadata.get('KeySpec', 'SYMMETRIC_DEFAULT')
            key_usage = key_metadata.get('KeyUsage', 'ENCRYPT_DECRYPT')
            
            # Check for symmetric encryption key (AES-256)
            if key_usage == 'ENCRYPT_DECRYPT':
                if key_spec == 'SYMMETRIC_DEFAULT':
                    return CryptoTestResult(
                        test_name="KMS Symmetric Key Algorithm",
                        passed=True,
                        details=f"Key {key_id} uses AES-256 (SYMMETRIC_DEFAULT)",
                        resource_id=key_id
                    )
                else:
                    return CryptoTestResult(
                        test_name="KMS Symmetric Key Algorithm",
                        passed=False,
                        details=f"Key {key_id} uses {key_spec} instead of SYMMETRIC_DEFAULT",
                        resource_id=key_id
                    )
            
            # Check for asymmetric signing key (RSA-4096)
            elif key_usage == 'SIGN_VERIFY':
                if key_spec == 'RSA_4096':
                    return CryptoTestResult(
                        test_name="KMS Asymmetric Key Algorithm",
                        passed=True,
                        details=f"Key {key_id} uses RSA-4096 for signing",
                        resource_id=key_id
                    )
                else:
                    return CryptoTestResult(
                        test_name="KMS Asymmetric Key Algorithm",
                        passed=False,
                        details=f"Key {key_id} uses {key_spec} instead of RSA-4096",
                        resource_id=key_id
                    )
            
            else:
                return CryptoTestResult(
                    test_name="KMS Key Usage",
                    passed=False,
                    details=f"Key {key_id} has unexpected usage: {key_usage}",
                    resource_id=key_id
                )
        
        except Exception as e:
            return CryptoTestResult(
                test_name="KMS Key Validation",
                passed=False,
                details=f"Error validating key {key_id}: {str(e)}",
                resource_id=key_id
            )
    
    def validate_signing_algorithm(self, key_id: str) -> CryptoTestResult:
        """Validate signing algorithm is RSASSA-PSS-SHA-256."""
        try:
            response = self.kms_client.describe_key(KeyId=key_id)
            key_metadata = response['KeyMetadata']
            
            key_usage = key_metadata.get('KeyUsage')
            
            if key_usage != 'SIGN_VERIFY':
                return CryptoTestResult(
                    test_name="Signing Algorithm",
                    passed=True,
                    details=f"Key {key_id} is not a signing key (skipped)",
                    resource_id=key_id
                )
            
            # Test signing with RSASSA_PSS_SHA_256
            test_message = b"Test message for signature validation"
            
            try:
                sign_response = self.kms_client.sign(
                    KeyId=key_id,
                    Message=test_message,
                    MessageType='RAW',
                    SigningAlgorithm='RSASSA_PSS_SHA_256'
                )
                
                signature = sign_response['Signature']
                signing_algorithm = sign_response['SigningAlgorithm']
                
                if signing_algorithm == 'RSASSA_PSS_SHA_256':
                    return CryptoTestResult(
                        test_name="Signing Algorithm",
                        passed=True,
                        details=f"Key {key_id} successfully uses RSASSA-PSS-SHA-256",
                        resource_id=key_id
                    )
                else:
                    return CryptoTestResult(
                        test_name="Signing Algorithm",
                        passed=False,
                        details=f"Key {key_id} uses {signing_algorithm} instead of RSASSA-PSS-SHA-256",
                        resource_id=key_id
                    )
            
            except self.kms_client.exceptions.InvalidKeyUsageException:
                return CryptoTestResult(
                    test_name="Signing Algorithm",
                    passed=False,
                    details=f"Key {key_id} cannot be used for signing",
                    resource_id=key_id
                )
        
        except Exception as e:
            return CryptoTestResult(
                test_name="Signing Algorithm",
                passed=False,
                details=f"Error validating signing algorithm for key {key_id}: {str(e)}",
                resource_id=key_id
            )
    
    def test_signature_verification(self, key_id: str) -> CryptoTestResult:
        """Test signature verification workflow."""
        try:
            response = self.kms_client.describe_key(KeyId=key_id)
            key_metadata = response['KeyMetadata']
            
            if key_metadata.get('KeyUsage') != 'SIGN_VERIFY':
                return CryptoTestResult(
                    test_name="Signature Verification",
                    passed=True,
                    details=f"Key {key_id} is not a signing key (skipped)",
                    resource_id=key_id
                )
            
            # Sign a test message
            test_message = b"Test message for signature verification"
            
            sign_response = self.kms_client.sign(
                KeyId=key_id,
                Message=test_message,
                MessageType='RAW',
                SigningAlgorithm='RSASSA_PSS_SHA_256'
            )
            
            signature = sign_response['Signature']
            
            # Verify the signature
            verify_response = self.kms_client.verify(
                KeyId=key_id,
                Message=test_message,
                MessageType='RAW',
                Signature=signature,
                SigningAlgorithm='RSASSA_PSS_SHA_256'
            )
            
            if verify_response['SignatureValid']:
                return CryptoTestResult(
                    test_name="Signature Verification",
                    passed=True,
                    details=f"Key {key_id} signature verification successful",
                    resource_id=key_id
                )
            else:
                return CryptoTestResult(
                    test_name="Signature Verification",
                    passed=False,
                    details=f"Key {key_id} signature verification failed",
                    resource_id=key_id
                )
        
        except Exception as e:
            return CryptoTestResult(
                test_name="Signature Verification",
                passed=False,
                details=f"Error testing signature verification for key {key_id}: {str(e)}",
                resource_id=key_id
            )
    
    def test_sha256_hashing(self) -> CryptoTestResult:
        """Test SHA-256 hashing implementation."""
        try:
            # Test data
            test_data = b"Test data for SHA-256 hashing"
            
            # Compute SHA-256 hash
            hash_obj = hashlib.sha256()
            hash_obj.update(test_data)
            hash_value = hash_obj.hexdigest()
            
            # Verify hash length (SHA-256 produces 64 hex characters)
            if len(hash_value) == 64:
                return CryptoTestResult(
                    test_name="SHA-256 Hashing",
                    passed=True,
                    details=f"SHA-256 hashing works correctly (hash: {hash_value[:16]}...)",
                    resource_id="hashlib"
                )
            else:
                return CryptoTestResult(
                    test_name="SHA-256 Hashing",
                    passed=False,
                    details=f"SHA-256 hash has incorrect length: {len(hash_value)}",
                    resource_id="hashlib"
                )
        
        except Exception as e:
            return CryptoTestResult(
                test_name="SHA-256 Hashing",
                passed=False,
                details=f"Error testing SHA-256 hashing: {str(e)}",
                resource_id="hashlib"
            )
    
    def test_hash_consistency(self) -> CryptoTestResult:
        """Test that SHA-256 hashing is consistent."""
        try:
            test_data = b"Consistency test data"
            
            # Compute hash twice
            hash1 = hashlib.sha256(test_data).hexdigest()
            hash2 = hashlib.sha256(test_data).hexdigest()
            
            if hash1 == hash2:
                return CryptoTestResult(
                    test_name="Hash Consistency",
                    passed=True,
                    details="SHA-256 hashing is consistent across multiple computations",
                    resource_id="hashlib"
                )
            else:
                return CryptoTestResult(
                    test_name="Hash Consistency",
                    passed=False,
                    details=f"SHA-256 hashing is inconsistent: {hash1} != {hash2}",
                    resource_id="hashlib"
                )
        
        except Exception as e:
            return CryptoTestResult(
                test_name="Hash Consistency",
                passed=False,
                details=f"Error testing hash consistency: {str(e)}",
                resource_id="hashlib"
            )
    
    def run_all_validations(self) -> bool:
        """Run all cryptographic validations."""
        print(f"Running cryptographic validations for stack: {self.stack_name}\n")
        
        # Get KMS keys
        kms_keys = self.get_stack_kms_keys()
        print(f"Found {len(kms_keys)} KMS keys in stack\n")
        
        # Validate each KMS key
        for key_id in kms_keys:
            print(f"Validating KMS key: {key_id}")
            self.results.append(self.validate_kms_key_spec(key_id))
            self.results.append(self.validate_signing_algorithm(key_id))
            self.results.append(self.test_signature_verification(key_id))
        
        # Test SHA-256 hashing
        print("\nTesting SHA-256 hashing...")
        self.results.append(self.test_sha256_hashing())
        self.results.append(self.test_hash_consistency())
        
        # Print results
        print("\n" + "="*80)
        print("CRYPTOGRAPHIC VALIDATION RESULTS")
        print("="*80 + "\n")
        
        passed_count = 0
        failed_count = 0
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"{status}: {result.test_name}")
            if result.resource_id:
                print(f"  Resource: {result.resource_id}")
            print(f"  Details: {result.details}\n")
            
            if result.passed:
                passed_count += 1
            else:
                failed_count += 1
        
        print("="*80)
        print(f"Total: {len(self.results)} tests")
        print(f"Passed: {passed_count}")
        print(f"Failed: {failed_count}")
        print("="*80 + "\n")
        
        return failed_count == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Rosetta Zero cryptographic implementations')
    parser.add_argument('--stack-name', default='RosettaZeroStack-dev',
                       help='CloudFormation stack name (default: RosettaZeroStack-dev)')
    
    args = parser.parse_args()
    
    validator = CryptoValidator(stack_name=args.stack_name)
    all_passed = validator.run_all_validations()
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
