---
source_type: state_diagram_theory
source_name: UML and the Unified Process
source_file: /Users/faria/Downloads/UML and the unified process - practical object-oriented  -  Arlow, Jim; Neustadt, Ila  -  ( WeLib.org )-338-364.pdf
chapter: Basic Statecharts
topics: reactive object, statechart scope, lifecycle, activity diagram difference
priority: high
---

# Reactive Objects and Statechart Scope

Use this document to decide whether a requirement is suitable for state-machine modeling and what lifecycle should be modeled.

## Statechart purpose

A statechart models the dynamic behavior of a reactive object. A reactive object can be a class, use case, subsystem, complete system, session, controller, or business process that responds to events.

For this project, the reactive object is usually the system or process described by the requirement.

## Reactive object characteristics

A good state-machine candidate usually has:

```text
1. External or internal events that affect behavior.
2. A clear lifecycle.
3. Behavior that depends on previous behavior or current condition.
4. Meaningful states and transitions.
```

Examples:

```text
ATM session
payment process
login mechanism
order lifecycle
device operation
alarm controller
booking request
approval workflow
```

## Statechart vs activity diagram

Activity diagrams usually model procedural workflow involving activities and process flow.

Statechart diagrams model the lifecycle of one reactive object and how it changes state in response to events.

When a requirement describes a sequence of steps only, avoid turning every step into a state. Choose states that represent meaningful conditions of the system.

## Scope rule

A generated state diagram should focus on one lifecycle. If a requirement mentions many actors or modules, model the central system/process lifecycle unless the task explicitly asks for separate diagrams.

Good central lifecycle examples:

```text
User session lifecycle
Order processing lifecycle
Payment lifecycle
Device controller lifecycle
Registration and verification lifecycle
```
