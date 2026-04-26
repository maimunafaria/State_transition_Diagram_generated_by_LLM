---
source_type: state_diagram_theory
source_name: UML and the Unified Process
source_file: /Users/faria/Downloads/UML and the unified process - practical object-oriented  -  Arlow, Jim; Neustadt, Ila  -  ( WeLib.org )-338-364.pdf
chapter: Basic Statecharts
topics: state syntax, actions, activities, entry action, exit action, internal transition
priority: high
---

# State Syntax, Actions, and Activities

Use this document when deciding whether something belongs inside a state or on a transition.

## State meaning

A state represents a condition during the lifecycle of the reactive object. In that condition, the object may wait for events, perform behavior, or react in a specific way.

Good states:

```text
WaitingForInput
Authenticating
PaymentPending
ProcessingOrder
AlarmActive
```

## Actions

An action is short, atomic behavior. In modeling, actions are often attached to transitions or to state entry/exit behavior.

Transition action pattern:

```plantuml
Pending --> Approved : approve / notify user
```

## Activities

An activity can take time and may be interrupted by an event. In PlantUML, ongoing behavior inside a state can be shown with `do /`.

```plantuml
Searching : do / search matching records
Searching --> Cancelled : cancel
Searching --> ResultsShown : search complete
```

## Entry and exit actions

Use `entry /` for behavior performed when entering a state.

```plantuml
Processing : entry / initialize request
```

Use `exit /` for behavior performed when leaving a state.

```plantuml
Processing : exit / save result
```

## Internal transitions

An internal transition handles an event without leaving the state.

```plantuml
EnteringPassword : keypress / mask character
EnteringPassword : clear / erase input
```

Use internal transitions when the event matters but does not create a new lifecycle state.
