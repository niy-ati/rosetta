"""
Cryptographic certificate signing with AWS KMS.

This module implements cryptographic signing of equivalence certificates using
AWS KMS asymmetric signing keys (RSA-4096, RSASSA-PSS-SHA-256).

Requirements: 17.7, 16.3, 16.4
"""

import hashlib
from datetime import datetime
from aws_lambda_powertools import Logger

from rosetta_zero.models import EquivalenceCertificate, SignedCertificate

logger = Logger(child=True)


def sign_certificate(
    certificate: EquivalenceCertificate,
    kms_client,
    kms_key_id: str
) -> SignedCertificate:
    """
    Sign equivalence certificate using AWS KMS.
    
    This function:
    1. Serializes certificate to canonical JSON
    2. Computes SHA-256 hash of certificate
    3. Signs hash using KMS asymmetric signing key (RSA-4096, RSASSA-PSS-SHA-256)
    4. Creates SignedCertificate with signature, key ID, algorithm, timestamp
    
    Args:
        certificate: EquivalenceCertificate to sign
        kms_client: Boto3 KMS client
        kms_key_id: KMS key ID or ARN for signing
        
    Returns:
        SignedCertificate with cryptographic signature
        
    Raises:
        Exception: If KMS signing fails
        
    Requirements: 17.7, 16.3, 16.4
    """
    
    logger.info("Starting certificate signing", extra={
        'certificate_id': certificate.certificate_id,
        'kms_key_id': kms_key_id
    })
    
    # Step 1: Serialize certificate to canonical JSON
    logger.info("Serializing certificate to canonical JSON")
    certificate_json = certificate.to_json()
    certificate_bytes = certificate_json.encode('utf-8')
    
    # Step 2: Compute SHA-256 hash of certificate
    logger.info("Computing SHA-256 hash of certificate")
    certificate_hash = hashlib.sha256(certificate_bytes).digest()
    
    logger.info("Certificate hash computed", extra={
        'hash': certificate_hash.hex()
    })
    
    # Step 3: Sign hash using KMS asymmetric key
    logger.info("Signing certificate hash with KMS")
    
    try:
        sign_response = kms_client.sign(
            KeyId=kms_key_id,
            Message=certificate_hash,
            MessageType='DIGEST',
            SigningAlgorithm='RSASSA_PSS_SHA_256'
        )
        
        signature = sign_response['Signature']
        
        logger.info("Certificate signed successfully", extra={
            'certificate_id': certificate.certificate_id,
            'signature_length': len(signature)
        })
        
    except Exception as e:
        logger.error("KMS signing failed", extra={
            'error': str(e),
            'certificate_id': certificate.certificate_id,
            'kms_key_id': kms_key_id
        })
        raise
    
    # Step 4: Create SignedCertificate
    signing_timestamp = datetime.utcnow().isoformat() + 'Z'
    
    signed_certificate = SignedCertificate(
        certificate=certificate,
        signature=signature,
        signing_key_id=kms_key_id,
        signature_algorithm='RSASSA_PSS_SHA_256',
        signing_timestamp=signing_timestamp
    )
    
    logger.info("SignedCertificate created", extra={
        'certificate_id': certificate.certificate_id,
        'signing_timestamp': signing_timestamp
    })
    
    return signed_certificate


def verify_certificate_signature(
    signed_certificate: SignedCertificate,
    kms_client
) -> bool:
    """
    Verify certificate signature using AWS KMS.
    
    This function:
    1. Recomputes certificate hash
    2. Verifies signature using KMS
    3. Returns signature validity status
    
    Args:
        signed_certificate: SignedCertificate to verify
        kms_client: Boto3 KMS client
        
    Returns:
        True if signature is valid, False otherwise
        
    Requirements: 17.7
    """
    
    logger.info("Starting certificate signature verification", extra={
        'certificate_id': signed_certificate.certificate.certificate_id
    })
    
    # Step 1: Recompute certificate hash
    certificate_json = signed_certificate.certificate.to_json()
    certificate_bytes = certificate_json.encode('utf-8')
    certificate_hash = hashlib.sha256(certificate_bytes).digest()
    
    logger.info("Certificate hash recomputed for verification", extra={
        'hash': certificate_hash.hex()
    })
    
    # Step 2: Verify signature with KMS
    try:
        verify_response = kms_client.verify(
            KeyId=signed_certificate.signing_key_id,
            Message=certificate_hash,
            MessageType='DIGEST',
            Signature=signed_certificate.signature,
            SigningAlgorithm=signed_certificate.signature_algorithm
        )
        
        signature_valid = verify_response.get('SignatureValid', False)
        
        logger.info("Signature verification completed", extra={
            'certificate_id': signed_certificate.certificate.certificate_id,
            'signature_valid': signature_valid
        })
        
        return signature_valid
        
    except Exception as e:
        logger.error("Signature verification failed", extra={
            'error': str(e),
            'certificate_id': signed_certificate.certificate.certificate_id
        })
        return False
