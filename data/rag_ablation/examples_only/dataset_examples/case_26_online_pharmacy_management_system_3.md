---
source_type: dataset_example
case_id: case_26_online_pharmacy_management_system_3
domain: Online Pharmacy Management System Scenario 3
complexity: simple
split_role: rag_train
---

# Online Pharmacy Management System Scenario 3 — Polished Requirement Specification

## Requirement

Online Pharmacy Management System Scenario 3 — Polished Requirement Specification

Functional Requirements
1. The system shall display a list of available orders to the delivery person.
2. The system shall allow the delivery person to contact the delivery address for coordination.
3. The system shall enable the delivery person to update their profile as needed.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram - Delivery Man

[*] --> ViewOrders

state "View orders" as ViewOrders
state "Contact delivery address" as ContactDeliveryAddress
state "Update profile" as UpdateProfile

ViewOrders --> ContactDeliveryAddress
ContactDeliveryAddress --> UpdateProfile
UpdateProfile --> [*]

@enduml

```
