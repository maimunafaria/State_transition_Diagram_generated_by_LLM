---
source_type: state_diagram_theory
source_name: UML Distilled
chapter: State Machine Diagrams
topics: transition label, event, guard, action, mutually exclusive guards
---

# UML Transitions, Events, Guards, and Actions

Use this document when labeling transitions in a state diagram.

## Transition label structure

A UML transition label can contain three conceptual parts:

```text
event [guard] / action
```

In PlantUML this can be written after a colon:

```plantuml
Waiting --> Approved : submit [valid] / approve request
```

## Event

An event is something that may trigger a change of state.

Examples:

```text
login submitted
payment received
card inserted
order cancelled
verification completed
timer expires
```

## Guard

A guard is a Boolean condition that must be true for the transition to happen.

Examples:

```plantuml
Checking --> Approved : [credentials valid]
Checking --> Rejected : [credentials invalid]
```

Guards are useful for decision points such as success/failure, yes/no, valid/invalid, accepted/rejected, paid/unpaid.

## Action

An action is behavior performed during the transition.

Example:

```plantuml
PaymentPending --> OrderConfirmed : payment successful / send receipt
```

## Missing parts

A transition may omit some parts:

```plantuml
Idle --> Active : start
Checking --> Approved : [valid]
Processing --> Completed
```

For generated diagrams, prefer clear transition labels when the requirement contains obvious events or conditions.

## Multiple outgoing transitions

If multiple transitions leave the same state for the same event, their guards should represent different, non-overlapping conditions.

Good pattern:

```plantuml
Verifying --> LoggedIn : submit [valid credentials]
Verifying --> LoginFailed : submit [invalid credentials]
```

This avoids ambiguity and makes the state diagram easier to evaluate manually.
