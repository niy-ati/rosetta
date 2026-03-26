       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-CALCULATOR.
       AUTHOR. ROSETTA-ZERO-TEST.
       
       ENVIRONMENT DIVISION.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 EMPLOYEE-RECORD.
          05 EMP-ID           PIC 9(6).
          05 EMP-NAME         PIC X(30).
          05 HOURS-WORKED     PIC 9(3)V99.
          05 HOURLY-RATE      PIC 9(3)V99.
          05 GROSS-PAY        PIC 9(7)V99.
          05 TAX-RATE         PIC V999 VALUE 0.200.
          05 TAX-AMOUNT       PIC 9(7)V99.
          05 NET-PAY          PIC 9(7)V99.
       
       01 CONSTANTS.
          05 OVERTIME-THRESHOLD PIC 9(3) VALUE 40.
          05 OVERTIME-MULTIPLIER PIC V99 VALUE 1.5.
       
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           MOVE 123456 TO EMP-ID.
           MOVE "JOHN DOE" TO EMP-NAME.
           MOVE 45.50 TO HOURS-WORKED.
           MOVE 25.00 TO HOURLY-RATE.
           
           PERFORM CALCULATE-GROSS-PAY.
           PERFORM CALCULATE-TAX.
           PERFORM CALCULATE-NET-PAY.
           PERFORM DISPLAY-RESULTS.
           
           STOP RUN.
       
       CALCULATE-GROSS-PAY.
           IF HOURS-WORKED > OVERTIME-THRESHOLD
               COMPUTE GROSS-PAY = 
                   (OVERTIME-THRESHOLD * HOURLY-RATE) +
                   ((HOURS-WORKED - OVERTIME-THRESHOLD) * 
                    HOURLY-RATE * OVERTIME-MULTIPLIER)
           ELSE
               COMPUTE GROSS-PAY = HOURS-WORKED * HOURLY-RATE
           END-IF.
       
       CALCULATE-TAX.
           COMPUTE TAX-AMOUNT = GROSS-PAY * TAX-RATE.
       
       CALCULATE-NET-PAY.
           COMPUTE NET-PAY = GROSS-PAY - TAX-AMOUNT.
       
       DISPLAY-RESULTS.
           DISPLAY "PAYROLL CALCULATION RESULTS".
           DISPLAY "===========================".
           DISPLAY "EMPLOYEE ID: " EMP-ID.
           DISPLAY "EMPLOYEE NAME: " EMP-NAME.
           DISPLAY "HOURS WORKED: " HOURS-WORKED.
           DISPLAY "HOURLY RATE: $" HOURLY-RATE.
           DISPLAY "GROSS PAY: $" GROSS-PAY.
           DISPLAY "TAX (20%): $" TAX-AMOUNT.
           DISPLAY "NET PAY: $" NET-PAY.
