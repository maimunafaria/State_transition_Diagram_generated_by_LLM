---
source_type: dataset_example
case_id: case_11_business_process_outsourcing_bpo_management_system_1
domain: Business Process Outsourcing Bpo Management System Scenario 1
complexity: medium
split_role: rag_train
---

# Business Process Outsourcing Bpo Management System Scenario 1 — Polished Requirement Specification

## Requirement

Business Process Outsourcing Bpo Management System Scenario 1 — Polished Requirement Specification

Functional Requirements
1. The system shall prompt the user to choose whether they are a new user or an already registered user.
2. The system shall require new users to enter their details for registration and end the process if the details are invalid.
3. The system shall save the user's information after a successful registration and allow them to log in.
4. The system shall allow registered users to directly log in by entering their username and password and continue if the login is successful.
5. The system shall allow users to manage their profile after logging in, which includes editing details, uploading or accepting requests, searching for other users, or viewing current deals.
6. The system shall require users to log out after they complete any action.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram (User System)

[*] --> UserType

state UserType <<choice>>
UserType --> Registration : [New user]
UserType --> Login : [Registered user]

state "Registration" as Registration {
    [*] --> GettingDetails

    state GettingDetails
    state ChoiceReg <<choice>>
    state "Update Database" as UpdateDB
    state EndInvalid <<choice>>

    GettingDetails --> ChoiceReg : [Registration verification]
    ChoiceReg --> UpdateDB : [valid]
    ChoiceReg --> EndInvalid : [invalid]

    EndInvalid --> [*]
}

Registration : entry / New user
Registration : do / Registration
Registration : exit / After updation

UpdateDB --> Login : [verified]

state Login
Login : do / Enter username and password
Login : exit / After verification

Login --> Profile : [valid uname & pwd]

state "Profile" as Profile {
    [*] --> ChoiceProfile

    state ChoiceProfile <<choice>>
    state "View or Edit profile" as EditProfile
    state "Upload or Accept request" as UploadReq
    state "Search users" as SearchUsers
    state "View current deals" as ViewDeals

    ChoiceProfile --> EditProfile : [edit profile data]
    ChoiceProfile --> UploadReq : [new project]
    ChoiceProfile --> SearchUsers : [search user]
    ChoiceProfile --> ViewDeals : [current deals]

    
}

Profile : entry / View or Edit profile
Profile : do / Upload or Accept request
Profile : do / Search users
Profile : do / View current deals
Profile : exit / Logout

    EditProfile --> [*] : [Logout]
    UploadReq --> [*] : [Logout]
    SearchUsers --> [*] : [Logout]
    ViewDeals --> [*] : [Logout]

@enduml

```
