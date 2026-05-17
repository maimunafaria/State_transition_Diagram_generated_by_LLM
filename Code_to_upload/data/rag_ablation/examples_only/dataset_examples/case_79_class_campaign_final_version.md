---
source_type: dataset_example
case_id: case_79_class_campaign_final_version
domain: Class Campaign Final Version
complexity: medium
split_role: rag_train
---

# Class Campaign Final Version — Polished Requirement Specification

## Requirement

Class Campaign Final Version — Polished Requirement Specification

Functional Requirements
1. The system shall activate a campaign once a manager and staff are assigned, it is approved, and the contract is signed.
2. The system shall allow surveys to be carried out and evaluated during the campaign.
3. The system shall prepare, approve, schedule, and run adverts during the campaign.
4. The system shall allow adjustments to the campaign, such as extending its duration or changing the budget.
5. The system shall pause a campaign, stopping all adverts, and allow resuming to continue work.
6. The system shall calculate costs and prepare a final statement if the campaign is cancelled.
7. The system shall complete the campaign and prepare a final statement when all work is finished.
8. The system shall handle payment after completion; if the amount does not match what is due, it may make adjustments such as refunds.
9. The system shall mark a campaign as paid once the correct payment is settled.
10. The system shall archive the campaign and release all assigned staff and managers after completion.

## Reference PlantUML

```plantuml
@startuml
title Campaign State Machine (Final Version)

[*] --> Commissioned : /assignManager; assignStaff

state Commissioned
state Suspended
state Completed
state Paid

Commissioned --> Active : authorized(authorizationCode)\n[contract signed]\n/setCampaignActive
Commissioned --> Completed : campaignCancelled;\ncalculateCosts;\nprepareFinalStatement
state Active {

  state Monitoring {
    [*] --> Survey

    state Survey
    state Evaluation
    state H1 <<history>>

    Survey --> Evaluation : surveyComplete
    Evaluation --> Survey : runSurvey
  }

  --

  state Running {
    [*] --> AdvertPreparation

    state AdvertPreparation
    state Scheduling
    state "Running Adverts" as RunningAdverts
    state H2 <<history>>

    AdvertPreparation --> Scheduling : advertsApproved\n/authorize
    Scheduling --> RunningAdverts : confirmSchedule
    RunningAdverts --> AdvertPreparation : extendCampaign\n/modifyBudget
  }

}


Active --> Suspended : suspendCampaign\n/stopAdverts
Suspended --> Active : resumeCampaign


Active --> Completed : campaignCancelled\n/cancelSchedule;\ncalculateCosts;\nprepareFinalStatement
AdvertPreparation --> Completed : campaignCompleted\n/prepareFinalStatement


Completed --> Paid : paymentReceived(payment)\n[paymentDue - payment = 0]
Completed --> Completed : paymentReceived(payment)\n[paymentDue - payment > 0]
Completed --> Paid : paymentReceived(payment)\n[paymentDue - payment < 0]\n/generateRefund


Paid --> [*] : archiveCampaign\n/unassignStaff;\nunassignManager

@enduml

```
