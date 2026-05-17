---
source_type: dataset_example
case_id: case_69_atm_many_scenarios_6
domain: Atm Many Scenarios Scenario 6
complexity: medium
split_role: rag_train
---

# Atm Many Scenarios Scenario 6 — Polished Requirement Specification

## Requirement

Atm Many Scenarios Scenario 6 — Polished Requirement Specification

Functional Requirements
1. The system shall check if the entered PIN is correct.
2. The system shall ask for the PIN again if it is incorrect.
3. The system shall keep the card for security reasons if the user keeps entering an incorrect PIN or if the card is invalid.
4. The system shall return the card if the user cancels the process at any moment during this stage.
5. The system shall display options for the user to choose from if the PIN is correct.
6. The system shall process the withdrawal request and check if it can approve the transaction.
7. The system shall cancel everything and return the card if the withdrawal request is rejected.
8. The system shall dispense cash, print a receipt, and return the card if the withdrawal request is approved.
9. The system shall stop the operation if it runs out of cash during the process.
10. The system shall reset itself to be ready for the next user after completing or ending the session.

## Reference PlantUML

```plantuml
@startuml
title ATM Control - Validate PIN and Withdraw Funds

[*] --> Idle

state Idle
state WaitingForPIN
state ValidatingPIN
state WaitingForCustomerChoice
state ProcessingWithdrawal
state Dispensing
state Printing
state Ejecting
state Confiscating
state Terminating
state ClosedDown

Idle : entry / Display Welcome
ClosedDown : entry / Display System Down

Idle --> WaitingForPIN : Card Inserted / Get PIN


WaitingForPIN --> ValidatingPIN : PIN Entered / Validate PIN
WaitingForPIN --> Confiscating : Card Confiscated / display Confiscated
ValidatingPIN --> WaitingForPIN : Invalid PIN / Invalid PIN Prompt

ValidatingPIN --> Confiscating : Card Stolen, Card Expired /\nConfiscate, Update Status
ValidatingPIN --> Confiscating : Third Invalid PIN /\nConfiscate

ValidatingPIN --> WaitingForCustomerChoice : Valid PIN / Display Menu

WaitingForPIN --> Ejecting : Cancel / Eject
WaitingForCustomerChoice --> Ejecting : Cancel / Eject
ValidatingPIN --> Ejecting : Cancel / Eject

WaitingForCustomerChoice --> ProcessingWithdrawal : Withdrawal Selected /\nRequest Withdrawal, Display Wait

ProcessingWithdrawal --> Dispensing : Withdrawal Approved /\nDispense Cash, Update Status
ProcessingWithdrawal --> Ejecting : Rejected / Eject

Dispensing --> Printing : Cash Dispensed /\nPrint Receipt,\nDisplay Cash Dispensed,\nConfirm Cash Dispensed
Dispensing --> ClosedDown : Insufficient Cash / Eject

Printing --> Ejecting : Receipt Printed / Eject

Ejecting --> Terminating : Card Ejected / Display Ejected
Confiscating --> Terminating : Card Confiscated / Display Confiscated

Terminating --> Idle : After (Elapsed Time)\n[Closedown Not Requested]


@enduml

```
