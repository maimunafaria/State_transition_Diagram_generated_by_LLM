---
source_type: state_diagram_theory
source_name: UML Distilled
source_file: source_documents/UML Distilled-83-89.pdf
chapter: State Machine Diagrams
topics: state, transition, initial pseudostate, final state, object behavior
---

# UML State Machine Core Concepts

Use this document to decide what should become a state and what should become a transition.

## Purpose

A state machine diagram describes how a system, object, or controller behaves over time. It is useful when the object reacts differently depending on its current condition.

## State

A state is not just a variable value. In a state machine, a state means an abstract condition where the system reacts to events in a particular way.

Good state names usually describe stable conditions:

```text
Idle
Waiting for Payment
Verifying User
Order Confirmed
Session Active
```

Avoid making every action a state. Actions such as "click button" or "enter password" are often better as transition labels unless the system remains in that condition.

## Initial pseudostate

The initial pseudostate indicates where the state machine begins. It points to the first real state.

PlantUML pattern:

```plantuml
[*] --> Idle
```

## Final state

A final state means the modeled lifecycle is complete.

PlantUML pattern:

```plantuml
Completed --> [*]
```

## Transition

A transition shows movement from one state to another. It captures how the system changes when something happens.

PlantUML pattern:

```plantuml
SourceState --> TargetState : event [guard] / action
```

For requirement-to-diagram generation, use transitions to represent:

```text
user submits form
payment succeeds
verification fails
timeout occurs
admin approves request
session ends
```

## Modeling guidance

When reading a requirement, identify:

```text
1. Stable conditions of the system -> states
2. Events or decisions that move the system -> transition labels
3. Conditions that must be true -> guards
4. Work performed during a change -> actions
5. The first state and completion/end states
```
