---
source_type: dataset_example
case_id: case_77_class_campaign
domain: Class Campaign
complexity: simple
split_role: rag_train
---

# Class Campaign — Polished Requirement Specification

## Requirement

Class Campaign — Polished Requirement Specification

Functional Requirements
1. The system shall begin a campaign once a manager and staff are assigned.
2. The system shall activate and start running a campaign upon approval and signing of the contract.
3. The system shall prepare a final statement when the campaign is finished and move the process toward completion.
4. The system shall handle payment after the final statement is prepared.
5. The system shall generate a refund if the payment is less than what is due.
6. The system shall wait for the correct amount to be settled if the payment exceeds the due amount.
7. The system shall mark the campaign as fully paid when the payment matches exactly.
8. The system shall archive the campaign and release the assigned staff and manager after everything is settled.

## Reference PlantUML

```plantuml
@startuml
title State machine for Campaign

state Commissioned
state Active
state Completed
state Paid

[*] --> Commissioned : /assignManager;\nassignStaff

Commissioned --> Active : Authorized(authorizationCode)\n[contract signed]\n/setCampaignActive

Active --> Completed : campaignCompleted\n/prepareFinalStatement

Completed --> Paid : paymentReceived(payment)\n[paymentDue - payment = zero]
Completed --> Completed : paymentReceived(payment)\n[paymentDue - payment > zero]
Completed --> Paid : paymentReceived(payment)\n[paymentDue - payment < zero]\n/generateRefund

Paid --> [*] : archiveCampaign\n/unassignStaff;\nunassignManager

@enduml

```
