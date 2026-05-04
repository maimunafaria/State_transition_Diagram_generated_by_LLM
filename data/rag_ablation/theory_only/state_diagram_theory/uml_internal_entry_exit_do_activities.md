---
source_type: state_diagram_theory
source_name: UML Distilled
source_file: /Users/faria/Downloads/UML Distilled-83-89.pdf
chapter: State Machine Diagrams
topics: internal activity, entry activity, exit activity, do activity, self-transition
priority: medium
---

# UML Internal, Entry, Exit, and Do Activities

Use this document when a state has behavior inside it, not only transitions to other states.

## Internal activity

A state can react to an event without changing to another state. This is useful when the system remains in the same condition but performs a small behavior.

PlantUML style:

```plantuml
Typing : character / add character
Typing : help / show help
```

## Entry activity

An entry activity runs when the system enters a state.

```plantuml
Processing : entry / initialize processing
```

## Exit activity

An exit activity runs when the system leaves a state.

```plantuml
Processing : exit / save progress
```

## Do activity

A do activity represents ongoing work while the system remains in the state.

```plantuml
Searching : do / search records
```

If an interrupting event occurs, the system can leave the state before the do activity completes.

Example:

```plantuml
Searching --> ResultsDisplayed : search complete
Searching --> Cancelled : cancel
```

## Internal activity vs self-transition

An internal activity does not leave and re-enter the state. A self-transition does leave and re-enter the same state.

Use internal activity when the behavior does not conceptually reset the state.

Use a self-transition when the event restarts or repeats the state behavior.
