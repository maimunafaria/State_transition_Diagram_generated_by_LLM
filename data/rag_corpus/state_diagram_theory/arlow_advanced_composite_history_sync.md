---
source_type: state_diagram_theory
source_name: UML and the Unified Process
source_file: /Users/faria/Downloads/UML and the unified process - practical object-oriented  -  Arlow, Jim; Neustadt, Ila  -  ( WeLib.org )-338-364.pdf
chapter: Basic Statecharts
topics: superstate, inherited transition, composite state, history, synchronization
priority: medium
---

# Advanced Statechart Concepts: Composite States, History, and Synchronization

Use this document only when the requirement contains nested behavior, return/resume behavior, or coordinated parallel work.

## Composite states and superstates

A composite state groups substates under a larger state. Shared transitions can be attached to the composite state instead of repeated on every substate.

```plantuml
state Connected {
  [*] --> Browsing
  Browsing --> Downloading : download
  Downloading --> Browsing : complete
}

Connected --> Disconnected : disconnect
```

Here, `disconnect` applies to the whole connected lifecycle.

## Inherited transitions

Substates can conceptually inherit transitions from their parent composite state. This is useful for cancel, logout, timeout, or disconnect events.

Common inherited transition examples:

```text
cancel
logout
timeout
disconnect
abort
```

## History behavior

History is useful when a system exits a composite state and later resumes from the remembered substate.

PlantUML pattern:

```plantuml
Active --> Paused : pause
Paused --> Active[H] : resume
```

Use deep history `[H*]` when nested substates should also be remembered.

## Synchronization / coordination

Some workflows require two independent parts to finish before continuing. In simple generated diagrams, this can often be represented with a join state.

```plantuml
state join1 <<join>>

PaymentDone --> join1
OrderAssembled --> join1
join1 --> ReadyForDelivery
```

Use synchronization only if the requirement clearly says multiple branches must complete before the next state.
