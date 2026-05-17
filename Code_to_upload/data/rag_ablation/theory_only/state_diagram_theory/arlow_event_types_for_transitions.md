---
source_type: state_diagram_theory
source_name: UML and the Unified Process
source_file: source_documents/UML and the unified process - practical object-oriented  -  Arlow, Jim; Neustadt, Ila  -  ( WeLib.org )-338-364.pdf
chapter: Basic Statecharts
topics: call event, signal event, change event, time event, transition triggers
---

# Event Types for State Transitions

Use this document to choose better transition labels from requirements.

## Event role

An event is a noteworthy occurrence that may trigger a transition. In generated PlantUML, events usually appear as transition labels.

```plantuml
Idle --> Authenticating : login submitted
Authenticating --> LoggedIn : credentials valid
Authenticating --> LoginFailed : credentials invalid
```

## Call events

A call event represents a request for an operation or service.

Requirement phrases that often indicate call events:

```text
user submits
admin approves
system validates
customer requests
doctor confirms
```

Example:

```plantuml
Waiting --> Processing : submit request
```

## Signal events

A signal event represents an asynchronous notification or message.

Requirement phrases:

```text
notification received
alert triggered
message arrives
sensor reports
external signal received
```

Example:

```plantuml
Monitoring --> Alerting : alert signal received
```

## Change events

A change event is triggered when a condition becomes true.

Requirement phrases:

```text
when balance is insufficient
when temperature exceeds limit
when stock becomes unavailable
when verification is complete
```

PlantUML pattern:

```plantuml
Monitoring --> Warning : when temperature exceeds limit
```

## Time events

A time event is triggered at a specific time or after a duration.

Requirement phrases:

```text
after timeout
after 3 failed attempts
when deadline passes
after payment window expires
```

PlantUML pattern:

```plantuml
WaitingForPayment --> Expired : after payment timeout
```

## Practical labeling rule

Prefer readable natural-language labels for thesis evaluation. Use guards when a decision condition is important.

```plantuml
CheckingPayment --> Paid : [payment valid]
CheckingPayment --> PaymentFailed : [payment invalid]
```
