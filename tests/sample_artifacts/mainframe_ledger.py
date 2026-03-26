#!/usr/bin/env python3
"""
Mainframe Binary Simulator - Ledger System
Simulates a mainframe binary executable for testing purposes.
This represents a typical mainframe batch processing system.

Author: ROSETTA-ZERO-TEST
Purpose: Test artifact for behavioral equivalence verification
"""

import sys
import struct


def process_ledger_entry(account_id: int, transaction_type: str, amount: float) -> dict:
    """
    Process a ledger entry with mainframe-style fixed-point arithmetic.
    
    Args:
        account_id: 6-digit account identifier
        transaction_type: 'D' for debit, 'C' for credit
        amount: Transaction amount in dollars
    
    Returns:
        Dictionary with processed transaction details
    """
    # Mainframe-style fixed-point arithmetic (2 decimal places)
    # Convert to cents to avoid floating-point errors
    amount_cents = int(round(amount * 100))
    
    # Apply transaction type
    if transaction_type == 'D':
        signed_amount = -amount_cents
    elif transaction_type == 'C':
        signed_amount = amount_cents
    else:
        raise ValueError(f"Invalid transaction type: {transaction_type}")
    
    # Calculate running balance (starting from 10000.00)
    initial_balance_cents = 1000000  # $10,000.00
    new_balance_cents = initial_balance_cents + signed_amount
    
    # Apply minimum balance fee if below threshold
    minimum_balance_cents = 100000  # $1,000.00
    fee_cents = 0
    if new_balance_cents < minimum_balance_cents:
        fee_cents = 2500  # $25.00 fee
        new_balance_cents -= fee_cents
    
    # Convert back to dollars for display
    new_balance = new_balance_cents / 100.0
    fee = fee_cents / 100.0
    
    return {
        'account_id': account_id,
        'transaction_type': transaction_type,
        'amount': amount,
        'fee': fee,
        'new_balance': new_balance,
        'status': 'PROCESSED'
    }


def format_mainframe_output(result: dict) -> str:
    """
    Format output in mainframe-style fixed-width format.
    Mimics EBCDIC-style output formatting.
    """
    output = []
    output.append("=" * 60)
    output.append("MAINFRAME LEDGER SYSTEM - TRANSACTION REPORT")
    output.append("=" * 60)
    output.append(f"ACCOUNT ID:       {result['account_id']:06d}")
    output.append(f"TRANSACTION TYPE: {result['transaction_type']}")
    output.append(f"AMOUNT:           ${result['amount']:>12.2f}")
    output.append(f"SERVICE FEE:      ${result['fee']:>12.2f}")
    output.append(f"NEW BALANCE:      ${result['new_balance']:>12.2f}")
    output.append(f"STATUS:           {result['status']}")
    output.append("=" * 60)
    return "\n".join(output)


def main():
    """
    Main entry point - simulates mainframe batch processing.
    Reads transaction from command line arguments.
    """
    # Default test case
    account_id = 123456
    transaction_type = 'D'  # Debit
    amount = 9500.00
    
    # Parse command line arguments if provided
    if len(sys.argv) >= 4:
        try:
            account_id = int(sys.argv[1])
            transaction_type = sys.argv[2].upper()
            amount = float(sys.argv[3])
        except (ValueError, IndexError) as e:
            print(f"ERROR: Invalid arguments - {e}", file=sys.stderr)
            sys.exit(1)
    
    # Validate inputs
    if not (100000 <= account_id <= 999999):
        print("ERROR: Account ID must be 6 digits", file=sys.stderr)
        sys.exit(1)
    
    if transaction_type not in ['D', 'C']:
        print(f"ERROR: Transaction type must be D or C", file=sys.stderr)
        sys.exit(1)
    
    if amount < 0:
        print("ERROR: Amount must be positive", file=sys.stderr)
        sys.exit(1)
    
    # Process transaction
    try:
        result = process_ledger_entry(account_id, transaction_type, amount)
        output = format_mainframe_output(result)
        print(output)
        
        # Return exit code based on balance status
        if result['new_balance'] < 0:
            sys.exit(2)  # Overdraft
        else:
            sys.exit(0)  # Success
            
    except Exception as e:
        print(f"ERROR: Transaction processing failed - {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
