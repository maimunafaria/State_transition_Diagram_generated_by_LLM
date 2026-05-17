---
source_type: dataset_example
case_id: case_42_cash_register
domain: Cash Register
complexity: simple
split_role: rag_train
---

# Cash Register — Polished Requirement Specification

## Requirement

Cash Register — Polished Requirement Specification

Functional Requirements
1. The system shall wait for a customer.
2. The system shall add items one by one when a customer begins a purchase.
3. The system shall wait for payment after all items are added.
4. The system shall go back to waiting for the next customer after the payment is made.

## Reference PlantUML

```plantuml
@startuml
title State diagram of the system operations of "Process sale"

[*] --> WaitingCustomer

state "Waiting for customer" as WaitingCustomer
state "Record items" as RecordItems
state "Waiting for payment" as WaitingPayment

WaitingCustomer --> RecordItems : enter item
RecordItems --> RecordItems : enter item
RecordItems --> WaitingPayment : end of sale
WaitingPayment --> WaitingCustomer : enter payment

@enduml

```
