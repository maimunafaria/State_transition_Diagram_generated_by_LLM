---
source_type: dataset_example
case_id: case_55_petrol_gas_pump
domain: Petrol Gas Pump
complexity: medium
split_role: rag_train
---

# Petrol Gas Pump — Polished Requirement Specification

## Requirement

Petrol Gas Pump — Polished Requirement Specification

Functional Requirements
1. The system shall display a welcome message when not in use.
2. The system shall read the card details upon card insertion.
3. The system shall prepare the pump for use if the card is valid.
4. The system shall show an error message and reset if the card is invalid.
5. The system shall start fuel delivery when the nozzle is lifted during fueling.
6. The system shall stop fuel delivery when the nozzle is released.
7. The system shall process payment and deduct the amount from the account after fueling.
8. The system shall return to its initial state after completing a transaction.
9. The system shall automatically reset if there is inactivity for too long.

## Reference PlantUML

```plantuml
@startuml
title State machine model of a petrol (gas) pump

[*] --> Waiting

state Waiting
Waiting : do / display welcome

state Reading
Reading : do / get CC details

state Validating
Validating : do / validate credit card

state Initializing
Initializing : do / initialize display

state Ready

state Delivering
Delivering : do / deliver fuel
Delivering : do / update display

state Stopped

state Paying
Paying : do / debit CC account

state Resetting
Resetting : do / display CC error

Waiting --> Reading : Card Inserted into Reader
Reading --> Validating : Card Removed

Validating --> Initializing : Card OK
Validating --> Resetting : Invalid Card

Resetting --> Waiting : Timeout
Paying --> Waiting : Payment ack.
Initializing --> Waiting : Timeout

Initializing --> Ready : Hose Out of Holster
Ready --> Initializing : Hose in Holster

Ready --> Delivering : Nozzle Trigger On
Delivering --> Stopped : Nozzle Trigger Off
Stopped --> Delivering : Nozzle Trigger On

Stopped --> Paying : Hose in Holster

@enduml

```
