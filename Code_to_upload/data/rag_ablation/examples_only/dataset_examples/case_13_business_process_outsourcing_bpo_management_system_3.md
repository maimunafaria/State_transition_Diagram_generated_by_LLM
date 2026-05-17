---
source_type: dataset_example
case_id: case_13_business_process_outsourcing_bpo_management_system_3
domain: Business Process Outsourcing Bpo Management System Scenario 3
complexity: complex
split_role: rag_train
---

# Business Process Outsourcing Bpo Management System Scenario 3 — Polished Requirement Specification

## Requirement

Business Process Outsourcing Bpo Management System Scenario 3 — Polished Requirement Specification

Functional Requirements
1. The system shall allow a user to upload a new request.
2. The system shall enable a BPO organization to save the details of a project.
3. The system shall allow a client to search for a suitable project category.
4. The system shall enable an BPO organization to accept or decline a request from a client.
5. The system shall allow a client to decide whether to proceed with an accepted project or reject it.
6. The system shall update the project status after acceptance by both parties.
7. The system shall allow a client to track the progress of a project.
8. The system shall enable an BPO organization to update the progress of a project.
9. The system shall upload a final project once work is completed.
10. The system shall perform a quality check on the final project.
11. The system shall restart the process if a client is unsatisfied with the final project.
12. The system shall make payment if the client is satisfied with the final project.
13. The system shall deliver the project after payment.
14. The system shall allow a client to provide a rating for the completed project.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram (Upload or Accept Request)

state "Upload or Accept request" as UAR {

    [*] --> ChoiceUser


    UAR : entry / Regarding request details
    UAR : do / Project dealings
    UAR : exit / After finishing rating


    state ChoiceUser <<choice>>

    ChoiceUser --> EnterDetails : [user = BPO organization]
    ChoiceUser --> SearchCategory : [user = client]


    state "Enter project details" as EnterDetails
    state "Update database" as UpdateDB

    EnterDetails --> UpdateDB
    UpdateDB --> [*]


    state "Search project category" as SearchCategory
    state ChoiceBPO <<choice>>
    state ChoiceClient <<choice>>

    SearchCategory --> ChoiceBPO

    ChoiceBPO --> EndDecline : [BPO org declines]
    ChoiceBPO --> ChoiceClient : [BPO org accepts]

    ChoiceClient --> EndReject : [client rejects]
    ChoiceClient --> UpdateStatus : [client accepts]

    state EndDecline <<choice>>
    EndDecline --> [*]

    state EndReject <<choice>>
    EndReject --> [*]

    state "Update status of project" as UpdateStatus

    state ChoiceTracking <<choice>>

    UpdateStatus --> ChoiceTracking

    ChoiceTracking --> DisplayProgress : [client wishes to track]
    ChoiceTracking --> UpdateProgress : [user = BPO org]

    state "Display progress" as DisplayProgress
    DisplayProgress --> [*]

    state "Update progress" as UpdateProgress


    UpdateProgress --> UploadFinal : [End of project]

    state "Upload final project" as UploadFinal

    state QualityCheck <<choice>>

    UploadFinal --> QualityCheck : [Quality check]

    QualityCheck --> Payment : [satisfied]
    QualityCheck --> ChoiceTracking : [Not satisfied]

    state Payment
    state Shipment
    state Rating

    Payment --> Shipment
    Shipment --> Rating

    Rating --> [*]
}

@enduml

```
