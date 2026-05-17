---
source_type: dataset_example
case_id: case_19_car_care
domain: Car Care
complexity: complex
split_role: rag_train
---

# Car Care — Polished Requirement Specification

## Requirement

Car Care — Polished Requirement Specification

Functional Requirements
1. The system shall allow users to choose whether they are using the service center side or the car owner side.
2. The system shall allow service center users to register or log in if already registered.
3. The system shall allow service center users to enter damaged parts, update parts information, or send expiry-related notifications after logging in.
4. The system shall allow service center users to log out after finishing any of the above activities.
5. The system shall allow car owner users to register or log in.
6. The system shall allow car owners to view parts information, request or respond to services, or report a service center after logging in.
7. The system shall allow car owners to select required parts and make a payment when choosing a service.
8. The system shall allow car owners to log out after completing their activities.

## Reference PlantUML

```plantuml
@startuml
title UML state machine diagram

state PortalChoice1 <<choice>>
state PortalChoice2 <<choice>>
state PortalChoice3 <<choice>>
state ServiceJoin <<choice>>
state OwnerJoin <<choice>>


[*] --> PortalChoice1

PortalChoice1 --> PortalChoice2 : [Service Center Portal]
PortalChoice1 --> PortalChoice3 : [Car Owner Portal]

PortalChoice2 --> ServiceCenterRegistration : [New Service Center]
PortalChoice2 --> ServiceJoin : [Registered Service center]
PortalChoice3 --> CarOwnerRegistration : [New Car Owner]
PortalChoice3 --> OwnerJoin : [Registered Car Owner]

state "Service Center Registration" as ServiceCenterRegistration
ServiceCenterRegistration : entry / Unregistered service center
ServiceCenterRegistration : do / Enter Valid Credentials
ServiceCenterRegistration : exit / Account registered

state "Service Center Verification" as ServiceCenterVerification
ServiceCenterVerification : entry / Service Center account registered
ServiceCenterVerification : do / Verify Service center
ServiceCenterVerification : exit / Login Service center

state "Service Center Login" as ServiceCenterLogin
ServiceCenterLogin : entry / Verified Service Center
ServiceCenterLogin : entry / Service Center not logged in
ServiceCenterLogin : do / Authenticate Service Center
ServiceCenterLogin : exit / Logged In Successfully

state "Service center Home" as ServiceCenterHome
ServiceCenterHome : entry / Logged in Service Center
ServiceCenterHome : do / Display home page
ServiceCenterHome : exit / Enter Damaged parts list
ServiceCenterHome : exit / Expiry Notification page
ServiceCenterHome : exit / Updating Information list

state "Expiry Notification page" as ExpiryNotification
ExpiryNotification : entry / To view expiry notification
ExpiryNotification : do / Send service request to Car owner
ExpiryNotification : exit / Return to Service center home page

state "Entering Damaged parts list" as DamagedParts
DamagedParts : entry / To enter Damaged parts list
DamagedParts : do / Preparing and entering damaged parts list
DamagedParts : exit / Return to service center home page

state "Updating parts Information" as UpdatingParts
UpdatingParts : entry / To update changed parts information
UpdatingParts : do / Update Information
UpdatingParts : exit / Return to Service center home page

state "Logout" as Logout
Logout : entry / To Logout
Logout : do / Logout
Logout : exit / Logged out Successfully

state "Car Owner Registration" as CarOwnerRegistration
CarOwnerRegistration : entry / Unregistered Car Owner
CarOwnerRegistration : do / Enter valid Credentials
CarOwnerRegistration : exit / Account registered

state "Car owner Verification" as CarOwnerVerification
CarOwnerVerification : entry / Car owner account registered
CarOwnerVerification : do / Verify Car owner
CarOwnerVerification : exit / Login Car Owner

state "Car Owner Login" as CarOwnerLogin
CarOwnerLogin : entry / Verified Car Owner
CarOwnerLogin : entry / Car owner not logged in
CarOwnerLogin : do / Authenticate Car Owner
CarOwnerLogin : exit / Logged In Successfully

state "Car Owner Home" as CarOwnerHome
CarOwnerHome : entry / Logged in Car Owner
CarOwnerHome : do / Display home page
CarOwnerHome : exit / View parts information
CarOwnerHome : exit / Service
CarOwnerHome : exit / Report

state "Report" as Report
Report : entry / To Report Service center
Report : do / Enter the report
Report : exit / Return to car owner home page

state "View Parts Information" as ViewPartsInformation
ViewPartsInformation : entry / To view parts information
ViewPartsInformation : do / View car parts Information
ViewPartsInformation : exit / Return to Car owner home page

state "Service" as Service
Service : entry / Service request from service center
Service : do / Accept or deny request
Service : exit / Return to Car Owner home page

state "Choose parts" as ChooseParts
ChooseParts : entry / To choose selected parts
ChooseParts : do / Choose the part to be serviced
ChooseParts : exit / Return to service page

state "Make Payment" as MakePayment
MakePayment : entry / To make payments
MakePayment : do / Make payments
MakePayment : exit / Return to Service page


state ServiceHomeChoice <<choice>>
state ServiceLoginChoice <<choice>>
state OwnerHomeChoice <<choice>>
state OwnerLoginChoice <<choice>>
state FinalJoin <<choice>>


ServiceCenterRegistration --> ServiceCenterVerification
ServiceCenterVerification --> ServiceJoin
ServiceJoin --> ServiceCenterLogin
ServiceCenterLogin --> ServiceLoginChoice
ServiceLoginChoice --> ServiceCenterHome
ExpiryNotification --> ServiceLoginChoice 
UpdatingParts --> ServiceLoginChoice 
DamagedParts --> ServiceLoginChoice 

ServiceCenterHome --> ServiceHomeChoice : [Possible Activities]
ServiceHomeChoice --> ExpiryNotification
ServiceHomeChoice --> DamagedParts
ServiceHomeChoice --> UpdatingParts
ServiceHomeChoice --> FinalJoin

FinalJoin --> Logout
Logout --> [*]



CarOwnerRegistration --> CarOwnerVerification
CarOwnerVerification --> OwnerJoin
OwnerJoin --> CarOwnerLogin

CarOwnerLogin --> OwnerLoginChoice
OwnerLoginChoice --> CarOwnerHome
CarOwnerHome --> OwnerHomeChoice : [Possible Activities]
ViewPartsInformation --> OwnerLoginChoice
Report --> OwnerLoginChoice
Service --> OwnerLoginChoice

OwnerHomeChoice --> Report
OwnerHomeChoice --> ViewPartsInformation
OwnerHomeChoice --> Service
OwnerHomeChoice --> FinalJoin

Service --> ChooseParts
ChooseParts --> MakePayment
MakePayment --> Service

@enduml

```
