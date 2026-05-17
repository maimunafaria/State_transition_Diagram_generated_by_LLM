---
source_type: dataset_example
case_id: case_48_controlpanel_class
domain: Controlpanel Class
complexity: simple
split_role: rag_train
---

# Controlpanel Class — Polished Requirement Specification

## Requirement

Controlpanel Class — Polished Requirement Specification

Functional Requirements
1. The system shall check the entered password.
2. The system shall allow the user to continue making selections if the password is correct.
3. The system shall limit the number of incorrect password attempts a user can make.
4. The system shall lock and not allow further access for a certain period after too many incorrect attempts.
5. The system shall allow users to try accessing again after the lockout period has passed.

## Reference PlantUML

```plantuml
@startuml
title State Diagram - Control Panel

[*] --> Reading : Key hit

state Reading
state Comparing
state Locked
state Selecting


Comparing : do / validatePassword


Reading --> Comparing : Password entered


Comparing --> Comparing : Password incorrect\nnumberOfTries < maxTries


Comparing --> Locked : numberOfTries > maxTries


Comparing --> Selecting : Password correct


Locked --> Locked : Timer <= lockedTime


Locked --> Reading : Timer > lockedTime


Selecting --> Reading : Activation successful

@enduml

```
