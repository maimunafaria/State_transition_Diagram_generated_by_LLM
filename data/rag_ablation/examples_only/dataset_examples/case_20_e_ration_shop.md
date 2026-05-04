---
source_type: dataset_example
case_id: case_20_e_ration_shop
domain: E Ration Shop
complexity: medium
split_role: rag_train
---

# E Ration Shop — Polished Requirement Specification

## Requirement

E Ration Shop — Polished Requirement Specification

Functional Requirements
1. The system shall allow users to raise a complaint directly.
2. The system shall end the process after a user raises a complaint.
3. The system shall allow users to authenticate their identity using an OTP.
4. The system shall allow multiple attempts for OTP authentication if the initial attempt fails.
5. The system shall enable users to view items based on different categories once they are successfully authenticated.
6. The system shall allow users to select items for purchase after viewing them.
7. The system shall provide users with the option to pay either through an online method or by cash on delivery.
8. The system shall deliver the product after the payment is completed.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram


[*] --> C1

state C1 <<choice>>
C1 --> Auth : [possibilities to start]
C1 --> Complaints


state "Authentication of aadhar card by OTP" as Auth
Auth : entry / card holder
Auth : do / Generates OTP
Auth : do / OTP should match
Auth : exit / authentication completed

state Complaints
Complaints : entry / fill
Complaints : do / raise a complaint
Complaints : exit / complaint send

Complaints --> [*]

Auth --> Auth 
Auth --> ViewItems

state "View items" as ViewItems
ViewItems : entry / from Authentication
ViewItems : do / items shown based on category
ViewItems : do / select items required
ViewItems : exit / after selecting

ViewItems --> Purchase

state "make purchase" as Purchase
Purchase : entry / from view items
Purchase : do / payment
Purchase : exit / chose the mode of payment


state C2 <<choice>>
Purchase --> C2 : [possibilities for payment]

state PAYTM
PAYTM : entry / make purchase
PAYTM : do / making payment
PAYTM : exit / payment done

state COD
COD : entry / make purchase
COD : do / making payment
COD : exit / payment done

C2 --> PAYTM
C2 --> COD


state C3 <<choice>>
PAYTM --> C3
COD --> C3

C3 --> Delivery : [payment completed]


state Delivery
Delivery : entry / COD
Delivery : entry / PAYTM
Delivery : do / product delivered

Delivery --> [*]

@enduml

```
