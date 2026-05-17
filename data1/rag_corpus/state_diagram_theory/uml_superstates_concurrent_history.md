---
source_type: state_diagram_theory
source_name: UML Distilled
chapter: State Machine Diagrams
topics: superstate, composite state, nested state, concurrent state, history pseudostate
---

# UML Superstates, Concurrent States, and History

Use this document when the requirement has shared behavior, nested workflows, or parallel behavior.

## Superstate / composite state

When several states share the same transition or internal behavior, group them under a composite state.

Example:

```plantuml
state "Entering Details" as EnteringDetails {
  [*] --> NameEntry
  NameEntry --> AddressEntry : next
  AddressEntry --> Confirmation : next
}

EnteringDetails --> Cancelled : cancel
```

This avoids repeating the same `cancel` transition on every nested state.

## Nested states

Nested states are useful when one larger state contains a smaller lifecycle.

Example:

```plantuml
state SessionActive {
  [*] --> Browsing
  Browsing --> Checkout : buy
  Checkout --> Browsing : continue shopping
}
```

## Concurrent states

Use concurrent regions when two independent parts of behavior happen at the same time.

Example:

```plantuml
state Active {
  [*] --> MusicOff
  MusicOff --> MusicOn : play

--

  [*] --> AlarmOff
  AlarmOff --> AlarmOn : enable alarm
}
```

Only use concurrency when the requirement clearly has independent parallel behavior.

## History pseudostate

A history pseudostate means the system can return to the most recent substate when re-entering a composite state.

PlantUML examples:

```plantuml
CompositeState --> CompositeState[H] : resume
CompositeState --> CompositeState[H*] : deep resume
```

Use history when the requirement says the system resumes from where it left off.
