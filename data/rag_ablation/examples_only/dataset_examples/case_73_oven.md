---
source_type: dataset_example
case_id: case_73_oven
domain: Oven
complexity: medium
split_role: rag_train
---

# Oven — Polished Requirement Specification

## Requirement

Oven — Polished Requirement Specification

Functional Requirements
1. The system shall allow the user to open the door whenever it is closed.
2. The system shall allow the user to place food inside or remove it from the microwave when the door is open.
3. The system shall require the user to close the door after placing food inside.
4. The system shall require the user to enter cooking time after the door is closed.
5. The system shall start cooking the food when the user initiates the microwave and continue until the set time is completed.
6. The system shall stop immediately if the door is opened during cooking for safety reasons.
7. The system shall stop when the cooking time ends and allow the user to open the door to remove the food.

## Reference PlantUML

```plantuml
@startuml
title Microwave Oven Control - State Diagram

[*] --> DoorShut

state "Door Shut" as DoorShut
state "Door Open" as DoorOpen
state "Door Open With Item" as DoorOpenItem
state "Door Shut With Item" as DoorShutItem
state "Ready To Cook" as ReadyToCook
state Cooking

DoorShut --> DoorOpen : Door Opened
DoorOpen --> DoorShut : Door Closed

DoorOpen --> DoorOpenItem : Item Placed
DoorOpenItem --> DoorOpen : Item Removed

DoorOpenItem --> DoorShutItem : Door Closed
DoorShutItem --> DoorOpenItem : Door Opened

DoorShutItem --> ReadyToCook : Cooking Time Entered
ReadyToCook --> ReadyToCook : Cooking Time Entered

ReadyToCook --> Cooking : Start

Cooking --> DoorOpenItem : Door Opened
Cooking --> DoorShutItem : Timer Expired

@enduml

```
