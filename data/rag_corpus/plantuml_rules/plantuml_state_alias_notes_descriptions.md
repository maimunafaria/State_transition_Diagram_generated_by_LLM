---
source_type: plantuml_rule
source_name: PlantUML Language Reference Guide
source_file: /Users/faria/Downloads/PlantUML_Language_Reference_Guide_en-232-256.pdf
chapter: State Diagram
topics: alias, long state name, notes, state description
priority: medium
---

# PlantUML State Aliases, Notes, and Descriptions

Use this document when state names are long or when the diagram needs annotations.

## Long state names with alias

Use aliases to keep transitions readable when state names are long.

```plantuml
state "Waiting for Payment Confirmation" as WaitingPayment
state "Order Completed Successfully" as OrderComplete

WaitingPayment --> OrderComplete : payment confirmed
```

Alternative alias form:

```plantuml
state WaitingPayment as "Waiting for Payment Confirmation"
```

## Notes attached to states

Use notes to add additional explanation without changing the state name.

```plantuml
note right of Processing : validates request details
```

Multi-line notes:

```plantuml
note left of Processing
The system checks the request,
then decides the next state.
end note
```

## Notes on transitions

Use `note on link` after a transition when the note describes the transition.

```plantuml
Idle --> Processing : submit request
note on link
Triggered when the user submits the form.
end note
```

## Floating notes

Floating notes can be declared with an alias.

```plantuml
note "Manual review may be required" as N1
```

## State descriptions

Add state descriptions with `StateName : description`.

```plantuml
Processing : entry / receive request
Processing : do / validate input
Processing : exit / store result
```
