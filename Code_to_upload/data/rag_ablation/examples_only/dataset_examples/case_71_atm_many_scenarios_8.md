---
source_type: dataset_example
case_id: case_71_atm_many_scenarios_8
domain: Atm Many Scenarios Scenario 8
complexity: medium
split_role: rag_train
---

# Atm Many Scenarios Scenario 8 — Polished Requirement Specification

## Requirement

Atm Many Scenarios Scenario 8 — Polished Requirement Specification

Functional Requirements
1. The system shall keep the card if it is invalid, expired, or the PIN was entered incorrectly too many times.
2. The system shall return the card with a message if the user cancels the operation or the request is rejected.
3. The system shall print a receipt and dispense cash if needed before returning the card to the user after a successful transaction.
4. The system shall consider the session finished once the card is ejected.
5. The system shall move into a short ending phase before resetting itself after completing the transaction or cancellation process.
6. The system shall return to its normal waiting condition or shut down depending on the situation.

## Reference PlantUML

```plantuml
@startuml
title ATM Control - Terminating Transaction

state "Closed Down" as ClosedDown
ClosedDown : entry / Display System Down

state Idle
Idle : entry / Display Welcome

state "Processing Customer Input" as ProcessingCustomerInput
state "Processing Transaction" as ProcessingTransaction

state "Terminating Transaction" as TerminatingTransaction {

  state Terminating
  state Confiscating
  state Ejecting
  state Printing
  state Dispensing

  Confiscating --> Terminating : Card Confiscated /\nDisplay Confiscated
  Ejecting --> Terminating : Card Ejected /\nDisplay Ejected
  Printing --> Ejecting : Receipt Printed /\nEject
  Dispensing --> Printing : Cash Dispensed /\nPrint Receipt,\nDisplay Cash Dispensed,\nConfirm Cash Dispensed
}

ProcessingCustomerInput --> Confiscating : Stolen Card, Expired Card /\nConfiscate, Update Status
ProcessingCustomerInput --> Confiscating : Third Invalid PIN /\nConfiscate
ProcessingCustomerInput --> Ejecting : Cancel / Eject,\nDisplay Cancel

ProcessingTransaction --> Ejecting : Rejected / Eject,\nDisplay Apology
ProcessingTransaction --> Printing : Transfer Approved /\nPrint Receipt,\nUpdate Status
ProcessingTransaction --> Printing : Query Approved /\nPrint Receipt,\nUpdate Status
ProcessingTransaction --> Dispensing : Withdrawal Approved /\nDispense Cash,\nUpdate Status

Dispensing --> ClosedDown : Insufficient Cash /\nEject,\nAbort Cash Dispensed

Terminating --> Idle : After (Elapsed Time) [Closedown Not Requested]
Terminating --> ClosedDown : After (Elapsed Time) [Closedown Was Requested]

@enduml

```
