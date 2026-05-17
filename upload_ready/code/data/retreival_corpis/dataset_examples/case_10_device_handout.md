---
source_type: dataset_example
case_id: case_10_device_handout
domain: Device Handout
complexity: medium
split_role: rag_train
---

# Device Handout — Polished Requirement Specification

## Requirement

Device Handout — Polished Requirement Specification

Functional Requirements
1. The system shall collect personal details from a donor during registration.
2. The system shall check the entered personal details after registration.
3. The system shall collect contact information from a donor after verifying their personal details.
4. The system shall allow donors to share details about the device they want to donate.
5. The system shall review the shared device details.
6. The system shall support if a device meets the requirements, the system shall accept it.
7. The system shall assign an executive to handle the accepted device.
8. The system shall confirm the status of the accepted device by the executive.
9. The system shall support if a device does not meet the requirements, the system shall inform the donor that it cannot be accepted.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram

[*] --> DonorRegistration

state "donor registration" as DonorRegistration
DonorRegistration : entry / enter personal details
DonorRegistration : do / verify details
DonorRegistration : exit / request contact details

state "get contacts" as GetContacts
GetContacts : entry / registered donor
GetContacts : do / receive contact details
GetContacts : exit / donate a device

state "device details" as DeviceDetails
DeviceDetails : entry / gave contacts
DeviceDetails : do / receive details
DeviceDetails : exit / request approval

state "device verification" as DeviceVerification
DeviceVerification : entry / provided device details
DeviceVerification : do / check details
DeviceVerification : exit / acknowledge donor

state Decision <<choice>>

state approved
approved : entry / device verified
approved : do / choose an executive
approved : exit / send details to executive

state rejected
rejected : entry / fails verification
rejected : do / notify donor
rejected : exit / device not accepted

state "picked up" as PickedUp
PickedUp : entry / executive receives details
PickedUp : do / executive picks product
PickedUp : exit / acknowledges status of product

DonorRegistration --> GetContacts
GetContacts --> DeviceDetails
DeviceDetails --> DeviceVerification
DeviceVerification --> Decision

Decision --> approved : [passes verification]
Decision --> rejected : [fails verification]

approved --> PickedUp

PickedUp --> [*]
rejected --> [*]

@enduml

```
