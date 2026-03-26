! FORTRAN 90 Scientific Calculator
! Demonstrates numerical computation with known behavior
! Author: ROSETTA-ZERO-TEST

PROGRAM SCIENTIFIC_CALCULATOR
    IMPLICIT NONE
    
    ! Variable declarations
    REAL(8) :: x, y, z
    REAL(8) :: sum_result, product_result, quotient_result
    REAL(8) :: sqrt_result, power_result
    REAL(8) :: pi, circle_area, circle_circumference
    INTEGER :: factorial_input, factorial_result
    
    ! Constants
    PARAMETER (pi = 3.14159265358979323846d0)
    
    ! Test Case 1: Basic arithmetic operations
    PRINT *, '========================================='
    PRINT *, 'SCIENTIFIC CALCULATOR TEST SUITE'
    PRINT *, '========================================='
    PRINT *, ''
    
    ! Initialize test values
    x = 15.5d0
    y = 3.2d0
    z = 2.0d0
    
    ! Perform calculations
    sum_result = x + y
    product_result = x * y
    quotient_result = x / y
    sqrt_result = SQRT(x)
    power_result = x ** z
    
    ! Test Case 2: Circle calculations
    circle_area = pi * (5.0d0 ** 2)
    circle_circumference = 2.0d0 * pi * 5.0d0
    
    ! Test Case 3: Factorial calculation
    factorial_input = 5
    CALL CALCULATE_FACTORIAL(factorial_input, factorial_result)
    
    ! Display results
    PRINT *, 'TEST CASE 1: BASIC ARITHMETIC'
    PRINT *, '------------------------------'
    PRINT '(A,F10.4)', ' X = ', x
    PRINT '(A,F10.4)', ' Y = ', y
    PRINT '(A,F10.4)', ' Z = ', z
    PRINT '(A,F10.4)', ' X + Y = ', sum_result
    PRINT '(A,F10.4)', ' X * Y = ', product_result
    PRINT '(A,F10.4)', ' X / Y = ', quotient_result
    PRINT '(A,F10.4)', ' SQRT(X) = ', sqrt_result
    PRINT '(A,F10.4)', ' X ^ Z = ', power_result
    PRINT *, ''
    
    PRINT *, 'TEST CASE 2: CIRCLE CALCULATIONS'
    PRINT *, '---------------------------------'
    PRINT '(A,F10.6)', ' PI = ', pi
    PRINT '(A,F10.4)', ' Radius = 5.0'
    PRINT '(A,F10.4)', ' Area = ', circle_area
    PRINT '(A,F10.4)', ' Circumference = ', circle_circumference
    PRINT *, ''
    
    PRINT *, 'TEST CASE 3: FACTORIAL'
    PRINT *, '----------------------'
    PRINT '(A,I2,A,I6)', ' ', factorial_input, '! = ', factorial_result
    PRINT *, ''
    
    PRINT *, '========================================='
    PRINT *, 'ALL TESTS COMPLETED'
    PRINT *, '========================================='
    
END PROGRAM SCIENTIFIC_CALCULATOR

! Subroutine to calculate factorial
SUBROUTINE CALCULATE_FACTORIAL(n, result)
    IMPLICIT NONE
    INTEGER, INTENT(IN) :: n
    INTEGER, INTENT(OUT) :: result
    INTEGER :: i
    
    result = 1
    DO i = 2, n
        result = result * i
    END DO
    
END SUBROUTINE CALCULATE_FACTORIAL
