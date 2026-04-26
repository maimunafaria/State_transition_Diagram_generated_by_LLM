---
source_type: dataset_example
case_id: case_72_atm_many_scenarios_9
domain: Atm Many Scenarios Scenario 9
complexity: medium
split_role: rag_train
---

# Atm Many Scenarios Scenario 9 — Polished Requirement Specification

## Requirement

Atm Many Scenarios Scenario 9 — Polished Requirement Specification

Functional Requirements
1. The system shall allow the user to choose to transfer money after entering the correct PIN.
2. The system shall process the transfer request if it is approved.
3. The system shall print a receipt for approved transfers and queries.
4. The system shall allow the user to choose to check information after entering the correct PIN.
5. The system shall print a receipt for transfers and queries.
6. The system shall process the query request if it is approved.
7. The system shall allow the user to choose to withdraw cash after entering the correct PIN.
8. The system shall process the withdrawal request and dispense cash if it is approved.
9. The system shall cancel the operation, show a message, and return the card if the request is rejected.

## Reference PlantUML

```plantuml
@startuml
title ATM Control - Processing Transaction

state "Waiting for Customer Choice" as WaitingForChoice

state "Processing Transaction" as ProcessingTransaction {
  state "Processing Transfer" as ProcessingTransfer
  state "Processing Query" as ProcessingQuery
  state "Processing Withdrawal" as ProcessingWithdrawal
}

state Ejecting
state Printing
state Dispensing

WaitingForChoice --> ProcessingTransfer : Transfer Selected /\nRequest Transfer,\nDisplay Wait
WaitingForChoice --> ProcessingQuery : Query Selected /\nRequest Query,\nDisplay Wait
WaitingForChoice --> ProcessingWithdrawal : Withdrawal Selected /\nRequest Withdrawal,\nDisplay Wait

ProcessingTransaction --> Ejecting : Rejected /\nEject,\nDisplay Apology
ProcessingTransfer --> Printing : Transfer Approved /\nPrint Receipt,\nUpdate Status
ProcessingQuery --> Printing : Query Approved /\nPrint Receipt,\nUpdate Status
ProcessingWithdrawal --> Dispensing : Withdrawal Approved /\nDispense Cash,\nUpdate Status

@enduml

```
