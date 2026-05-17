---
source_type: dataset_example
case_id: case_61_atm_3
domain: Atm Scenario 3
complexity: medium
split_role: rag_train
---

# Atm Scenario 3 — Polished Requirement Specification

## Requirement

Atm Scenario 3 — Polished Requirement Specification

Functional Requirements
1. The system shall check if the inserted card is valid.
2. The system shall prompt the user to select an amount to withdraw if the card is valid.
3. The system shall verify the transaction after the user selects an amount.
4. The system shall return the card to the user once the transaction is completed.
5. The system shall go out of service and not allow any operation if the machine is not working.

## Reference PlantUML

```plantuml
@startuml
title ATM State Machine

[*] --> VerifyCard

state "VerifyCard <<final>>" as VerifyCard

state ReadAmount {
  [*] --> SelectAmount
  state SelectAmount
  SelectAmount --> [*] : amount
}

state OutOfService
state "VerifyTransaction <<final>>" as VerifyTransaction
state ReleaseCard

VerifyCard --> ReadAmount : acceptCard
ReadAmount --> OutOfService : outOfService
ReadAmount --> VerifyTransaction
VerifyTransaction --> ReleaseCard : releaseCard / <<final>>

@enduml

```
