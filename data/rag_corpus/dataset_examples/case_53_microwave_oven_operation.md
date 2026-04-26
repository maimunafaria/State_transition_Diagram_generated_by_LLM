---
source_type: dataset_example
case_id: case_53_microwave_oven_operation
domain: Microwave Oven Operation
complexity: medium
split_role: rag_train
---

# Microwave Oven Operation — Polished Requirement Specification

## Requirement

Microwave Oven Operation — Polished Requirement Specification

Functional Requirements
1. The system shall check for proper functioning before starting.
2. The system shall alert the user and stop operation if an issue is detected.
3. The system shall start cooking and run for the set time if no issues are detected.
4. The system shall emit a sound to notify the user upon completion of cooking.
5. The system shall stop operation and deactivate if the door is opened.
6. The system shall return to a waiting state if the user cancels the operation.

## Reference PlantUML

```plantuml
@startuml
title Microwave Oven Operation

state Operation {

  state Checking
  Checking : do / Check Status

  state Cook
  Cook : do / Run Generator

  state Alarm
  Alarm : do / Display Event

  state Done
  Done : do / Buzzer On for 5 Secs.

  [*] --> Checking

  Checking --> Cook : OK
  Checking --> Alarm : Turntable Fault
  Checking --> Alarm : Emitter Fault

  Cook --> Done : Timeout
  Cook --> Cook : Time
}

state Disabled
state Waiting

Operation --> Disabled : Door Open
Operation --> Waiting : Cancel

Alarm --> Disabled
Done --> Waiting

@enduml

```
