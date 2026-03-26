#!/usr/bin/env python3
"""
Master validation script that runs all security and compliance validations.

Runs:
1. Security best practices validation
2. IAM policy validation
3. PII data scrubbing validation
4. Cryptographic implementation validation
5. Security audit
"""

import sys
import argparse
from security_validation import SecurityValidator
from iam_policy_validation import IAMPolicyValidator
from pii_validation import PIIValidator
from crypto_validation import CryptoValidator
from security_audit import SecurityAuditor


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run all Rosetta Zero security and compliance validations'
    )
    parser.add_argument(
        '--stack-name',
        default='RosettaZeroStack-dev',
        help='CloudFormation stack name (default: RosettaZeroStack-dev)'
    )
    parser.add_argument(
        '--region',
        help='AWS region (default: current session region)'
    )
    parser.add_argument(
        '--skip-security',
        action='store_true',
        help='Skip security best practices validation'
    )
    parser.add_argument(
        '--skip-iam',
        action='store_true',
        help='Skip IAM policy validation'
    )
    parser.add_argument(
        '--skip-pii',
        action='store_true',
        help='Skip PII validation'
    )
    parser.add_argument(
        '--skip-crypto',
        action='store_true',
        help='Skip cryptographic validation'
    )
    parser.add_argument(
        '--skip-audit',
        action='store_true',
        help='Skip security audit'
    )
    
    args = parser.parse_args()
    
    results = {}
    
    # Run security best practices validation
    if not args.skip_security:
        print_header("1. SECURITY BEST PRACTICES VALIDATION")
        validator = SecurityValidator(stack_name=args.stack_name)
        results['security'] = validator.run_all_validations()
    
    # Run IAM policy validation
    if not args.skip_iam:
        print_header("2. IAM POLICY VALIDATION")
        validator = IAMPolicyValidator(stack_name=args.stack_name)
        results['iam'] = validator.run_all_validations()
    
    # Run PII validation
    if not args.skip_pii:
        print_header("3. PII DATA SCRUBBING VALIDATION")
        validator = PIIValidator(stack_name=args.stack_name)
        results['pii'] = validator.run_all_validations()
    
    # Run cryptographic validation
    if not args.skip_crypto:
        print_header("4. CRYPTOGRAPHIC IMPLEMENTATION VALIDATION")
        validator = CryptoValidator(stack_name=args.stack_name)
        results['crypto'] = validator.run_all_validations()
    
    # Run security audit
    if not args.skip_audit:
        print_header("5. SECURITY AUDIT")
        auditor = SecurityAuditor(stack_name=args.stack_name, region=args.region)
        results['audit'] = auditor.run_all_audits()
    
    # Print summary
    print_header("VALIDATION SUMMARY")
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name.upper()}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("  ✓ ALL VALIDATIONS PASSED")
    else:
        print("  ✗ SOME VALIDATIONS FAILED")
    print("="*80 + "\n")
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
