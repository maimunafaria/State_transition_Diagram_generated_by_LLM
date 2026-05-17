---
source_type: state_diagram_theory
source_name: UML and the Unified Process
source_file: source_documents/UML and the unified process - practical object-oriented  -  Arlow, Jim; Neustadt, Ila  -  ( WeLib.org )-338-364.pdf
chapter: Basic Statecharts
topics: transition semantics, guard condition, action, event-triggered transition
---

# Transition Semantics and Guards

Use this document when building logically clear transitions.

## Basic transition meaning

A transition says that when the reactive object is in a source state and a trigger occurs, it may move to a target state.

PlantUML pattern:

```plantuml
Source --> Target : event [guard] / action
```

Readable interpretation:

```text
While in Source, if event occurs and guard is true, perform action and enter Target.
```

## Guard conditions

Use guards to represent decision outcomes.

Good examples:

```plantuml
Verifying --> Approved : [valid]
Verifying --> Rejected : [invalid]
```

```plantuml
PaymentCheck --> PaymentCompleted : [payment accepted]
PaymentCheck --> PaymentFailed : [payment declined]
```

## Actions on transitions

Use transition actions for behavior performed during the change.

```plantuml
OrderPaid --> ReceiptSent : payment confirmed / send receipt
```

## Event-driven behavior

The same event may lead to different outcomes when guards distinguish the conditions.

```plantuml
LoginCheck --> LoggedIn : submit [credentials valid]
LoginCheck --> RetryLogin : submit [credentials invalid]
```

Avoid ambiguous duplicate transitions without clear guards.

## Ignored events

If an event is not relevant to the current state, it does not need to appear in the diagram. A state diagram should show important lifecycle-changing events, not every possible event.
