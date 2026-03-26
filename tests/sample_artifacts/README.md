# Sample Legacy Artifacts for Testing

This directory contains sample legacy artifacts used for testing the Rosetta Zero system. Each artifact has known, deterministic behavior that can be verified during the equivalence testing process.

## Overview

The sample artifacts represent three common legacy system types:
1. **COBOL** - Business logic (payroll calculation)
2. **FORTRAN** - Scientific computation
3. **Mainframe Binary** - Batch processing system (simulated)

## Artifacts

### 1. COBOL Payroll Calculator (`payroll.cbl`)

**Purpose**: Demonstrates business logic with fixed-point arithmetic, conditional logic, and formatted output.

**Functionality**:
- Calculates employee gross pay with overtime rules
- Applies tax deductions
- Computes net pay
- Displays formatted payroll report

**Test Case - Default Values**:
```
Input:
  Employee ID: 123456
  Employee Name: JOHN DOE
  Hours Worked: 45.50
  Hourly Rate: $25.00
  Tax Rate: 20%
  Overtime Threshold: 40 hours
  Overtime Multiplier: 1.5x
```

**Expected Output**:
```
PAYROLL CALCULATION RESULTS
===========================
EMPLOYEE ID: 123456
EMPLOYEE NAME: JOHN DOE
HOURS WORKED: 045.50
HOURLY RATE: $025.00
GROSS PAY: $1206.25
TAX (20%): $241.25
NET PAY: $0965.00
```

**Calculation Details**:
- Regular hours: 40 × $25.00 = $1,000.00
- Overtime hours: 5.5 × $25.00 × 1.5 = $206.25
- Gross pay: $1,000.00 + $206.25 = $1,206.25
- Tax (20%): $1,206.25 × 0.20 = $241.25
- Net pay: $1,206.25 - $241.25 = $965.00

**Key Behavioral Properties**:
1. Overtime applies only to hours > 40
2. Overtime rate is 1.5× regular rate
3. Tax is calculated on gross pay
4. Fixed-point arithmetic with 2 decimal places
5. Output format is fixed-width with leading zeros

**Compilation** (if testing with actual COBOL compiler):
```bash
cobc -x -o payroll payroll.cbl
./payroll
```

---

### 2. FORTRAN Scientific Calculator (`scientific_calc.f90`)

**Purpose**: Demonstrates scientific computation with floating-point arithmetic, mathematical functions, and subroutines.

**Functionality**:
- Basic arithmetic operations (addition, multiplication, division)
- Mathematical functions (square root, exponentiation)
- Circle calculations using π
- Factorial calculation via subroutine

**Test Cases**:

**Test Case 1: Basic Arithmetic**
```
Input:
  X = 15.5
  Y = 3.2
  Z = 2.0
```

**Expected Output**:
```
TEST CASE 1: BASIC ARITHMETIC
------------------------------
 X =    15.5000
 Y =     3.2000
 Z =     2.0000
 X + Y =    18.7000
 X * Y =    49.6000
 X / Y =     4.8438
 SQRT(X) =     3.9370
 X ^ Z =   240.2500
```

**Test Case 2: Circle Calculations**
```
Input:
  Radius = 5.0
  PI = 3.14159265358979323846
```

**Expected Output**:
```
TEST CASE 2: CIRCLE CALCULATIONS
---------------------------------
 PI =   3.141593
 Radius = 5.0
 Area =    78.5398
 Circumference =    31.4159
```

**Test Case 3: Factorial**
```
Input:
  N = 5
```

**Expected Output**:
```
TEST CASE 3: FACTORIAL
----------------------
  5! =    120
```

**Calculation Details**:
- X + Y = 15.5 + 3.2 = 18.7
- X * Y = 15.5 × 3.2 = 49.6
- X / Y = 15.5 ÷ 3.2 = 4.84375
- SQRT(X) = √15.5 ≈ 3.937004
- X ^ Z = 15.5² = 240.25
- Circle Area = π × 5² ≈ 78.53982
- Circle Circumference = 2 × π × 5 ≈ 31.41593
- 5! = 5 × 4 × 3 × 2 × 1 = 120

**Key Behavioral Properties**:
1. Double precision floating-point (REAL(8))
2. PI constant with 20 decimal places
3. Formatted output with fixed decimal places
4. Subroutine call for factorial calculation
5. Iterative factorial algorithm (not recursive)

**Compilation** (if testing with actual FORTRAN compiler):
```bash
gfortran -o scientific_calc scientific_calc.f90
./scientific_calc
```

---

### 3. Mainframe Ledger System (`mainframe_ledger.py`)

**Purpose**: Simulates a mainframe binary executable for batch ledger processing. Demonstrates fixed-point arithmetic, business rules, and mainframe-style output formatting.

**Note**: This is a Python simulator representing mainframe binary behavior, as actual mainframe binaries cannot be easily created or executed in modern environments.

**Functionality**:
- Processes ledger transactions (debits and credits)
- Maintains account balance with fixed-point arithmetic
- Applies minimum balance fees
- Generates mainframe-style formatted reports
- Returns appropriate exit codes

**Test Case 1: Debit Transaction with Fee (Default)**
```
Input:
  Account ID: 123456
  Transaction Type: D (Debit)
  Amount: $9,500.00
  Initial Balance: $10,000.00
  Minimum Balance Threshold: $1,000.00
  Minimum Balance Fee: $25.00
```

**Expected Output**:
```
============================================================
MAINFRAME LEDGER SYSTEM - TRANSACTION REPORT
============================================================
ACCOUNT ID:       123456
TRANSACTION TYPE: D
AMOUNT:           $    9500.00
SERVICE FEE:      $      25.00
NEW BALANCE:      $     475.00
STATUS:           PROCESSED
============================================================
```

**Exit Code**: 0 (Success)

**Calculation Details**:
- Initial balance: $10,000.00
- Debit amount: -$9,500.00
- Balance after debit: $500.00
- Balance < $1,000.00 → Apply $25.00 fee
- Final balance: $500.00 - $25.00 = $475.00

**Test Case 2: Credit Transaction (No Fee)**
```bash
python3 mainframe_ledger.py 654321 C 500.00
```

```
Input:
  Account ID: 654321
  Transaction Type: C (Credit)
  Amount: $500.00
  Initial Balance: $10,000.00
```

**Expected Output**:
```
============================================================
MAINFRAME LEDGER SYSTEM - TRANSACTION REPORT
============================================================
ACCOUNT ID:       654321
TRANSACTION TYPE: C
AMOUNT:           $     500.00
SERVICE FEE:      $       0.00
NEW BALANCE:      $ 10500.00
STATUS:           PROCESSED
============================================================
```

**Exit Code**: 0 (Success)

**Test Case 3: Large Debit Causing Overdraft**
```bash
python3 mainframe_ledger.py 789012 D 10500.00
```

```
Input:
  Account ID: 789012
  Transaction Type: D (Debit)
  Amount: $10,500.00
  Initial Balance: $10,000.00
```

**Expected Output**:
```
============================================================
MAINFRAME LEDGER SYSTEM - TRANSACTION REPORT
============================================================
ACCOUNT ID:       789012
TRANSACTION TYPE: D
AMOUNT:           $  10500.00
SERVICE FEE:      $      25.00
NEW BALANCE:      $    -525.00
STATUS:           PROCESSED
============================================================
```

**Exit Code**: 2 (Overdraft condition)

**Key Behavioral Properties**:
1. Fixed-point arithmetic (cents-based to avoid floating-point errors)
2. Minimum balance fee applies when balance < $1,000.00
3. Fee is $25.00 flat rate
4. Initial balance is always $10,000.00
5. Exit code 0 for success, 2 for overdraft, 1 for errors
6. Fixed-width formatted output (60 characters wide)
7. Account ID must be exactly 6 digits
8. Transaction type must be 'D' or 'C'
9. Amount must be positive

**Execution**:
```bash
# Make executable
chmod +x mainframe_ledger.py

# Run with default values
python3 mainframe_ledger.py

# Run with custom values
python3 mainframe_ledger.py <account_id> <D|C> <amount>
```

---

## Testing Strategy

### Unit Testing
Each artifact should be tested individually to verify:
1. Correct output for known inputs
2. Proper handling of edge cases
3. Consistent arithmetic behavior
4. Correct exit codes (where applicable)

### Integration Testing
The artifacts should be used in end-to-end tests:
1. Ingest artifact into Rosetta Zero
2. Extract Logic Map
3. Generate modern implementation
4. Generate test vectors
5. Execute parallel verification
6. Verify equivalence certificate generation

### Expected Test Results
All three artifacts should:
- Successfully ingest without errors
- Generate valid Logic Maps
- Produce modern implementations that pass all test vectors
- Generate equivalence certificates
- Create complete audit trails

### Validation Criteria
For each artifact, verify:
1. **Arithmetic Precision**: Modern implementation matches legacy arithmetic exactly
2. **Output Format**: Modern implementation produces identical output format
3. **Side Effects**: All side effects (if any) are preserved
4. **Error Handling**: Error conditions produce identical behavior
5. **Exit Codes**: Return codes match legacy behavior

---

## Known Limitations

### COBOL Artifact
- Simplified payroll logic (no state tax, benefits, etc.)
- Single employee processing (no batch mode)
- No file I/O (all in-memory)

### FORTRAN Artifact
- Limited to basic mathematical operations
- No file I/O or external data
- Single execution path (no conditional branches based on input)

### Mainframe Binary Simulator
- Python simulation, not actual mainframe binary
- Simplified ledger logic (single transaction, no persistence)
- No EBCDIC encoding (uses ASCII)
- No actual binary format (interpreted Python)

---

## Future Enhancements

Potential additions for more comprehensive testing:
1. COBOL artifact with file I/O (reading/writing records)
2. FORTRAN artifact with array processing and matrix operations
3. More complex mainframe scenarios (multi-step batch processing)
4. Artifacts with deliberate edge cases (overflow, underflow, rounding)
5. Artifacts with timing-dependent behavior
6. Artifacts with external dependencies (database, network)

---

## References

- COBOL Standard: ISO/IEC 1989:2014
- FORTRAN Standard: ISO/IEC 1539-1:2018
- Mainframe Batch Processing: IBM z/OS documentation
- Fixed-Point Arithmetic: COBOL PICTURE clauses and COMPUTE statements
- Floating-Point Arithmetic: IEEE 754 double precision

---

**Last Updated**: 2024
**Maintained By**: Rosetta Zero Test Team
