---
source_type: state_diagram_theory
source_name: UML Distilled
chapter: State Machine Diagrams
topics: when to use state diagrams, modeling scope, observability, use cases
---

# UML State Diagram Usage Guidelines

Use this document to decide whether a requirement should be modeled as a state machine and how much detail to include.

## When state diagrams are useful

State diagrams are most useful when the same system or object behaves differently depending on its current state.

Good candidates:

```text
ATM sessions
login/authentication flows
order/payment lifecycles
device controllers
approval workflows
booking or registration workflows
alarm/notification systems
```

## Scope

A state diagram should focus on the lifecycle of one system, object, session, controller, or business process.

Avoid mixing unrelated lifecycles into one diagram unless the requirement clearly describes them as one process.

## Observability

Only model events and conditions that the system can observe or control.

For example, if the system cannot directly detect a user's hidden intention, do not model that intention as a transition trigger. Model the observable event instead, such as `cancel selected`, `form submitted`, or `payment failed`.

## Relationship with use cases

Use cases describe external actor-system interaction. State diagrams describe how the system changes state across those interactions.

When converting requirements:

```text
Use case step -> often transition event
System condition -> often state
Alternative path -> often guarded transition
End of scenario -> often final transition
```

## Practical generation checklist

Before writing PlantUML:

```text
1. Identify the lifecycle being modeled.
2. List stable system conditions as candidate states.
3. List actor/system events as transition labels.
4. Add guards for decision branches.
5. Add one initial transition.
6. Add at least one completion/end transition.
7. Keep the diagram readable; avoid modeling every tiny action as a separate state.
```
