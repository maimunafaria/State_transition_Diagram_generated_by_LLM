---
source_type: dataset_example
case_id: case_14_business_process_outsourcing_bpo_management_system_4
domain: Business Process Outsourcing Bpo Management System Scenario 4
complexity: medium
split_role: rag_train
---

# Business Process Outsourcing Bpo Management System Scenario 4 — Polished Requirement Specification

## Requirement

Business Process Outsourcing Bpo Management System Scenario 4 — Polished Requirement Specification

Functional Requirements
1. The system shall allow the user to change their password by entering their old password and a new one.
2. The system shall allow the user to update their profile details by entering new information.
3. The system shall validate the entered information after a password change or profile update.
4. The system shall save the changes if the validation passes.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram (View or Edit profile)

state "View or Edit profile" as ViewEditProfile {

    [*] --> Choice1

    ViewEditProfile : entry / To Edit
    ViewEditProfile : do / Edit profile
    ViewEditProfile : exit / After updation

    state Choice1 <<choice>>

    Choice1 --> ChangePassword : [change pwd]
    Choice1 --> EnterProfileDetails : [edit profile]

    state "Change password" as ChangePassword
    state "Enter old password" as EnterOldPassword
    state "Enter new password" as EnterNewPassword
    state "Enter profile details" as EnterProfileDetails
    state "Enter new details" as EnterNewDetails
    state Choice2 <<choice>>
    state "Update Database" as UpdateDatabase
    state InvalidEnd <<choice>>

    ChangePassword --> EnterOldPassword
    EnterOldPassword --> EnterNewPassword
    EnterNewPassword --> Choice2

    EnterProfileDetails --> EnterNewDetails
    EnterNewDetails --> Choice2

    Choice2 --> InvalidEnd : [invalid]
    Choice2 --> UpdateDatabase : [valid]

    InvalidEnd --> [*]
    UpdateDatabase --> [*]
}

@enduml

```
