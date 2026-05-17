---
source_type: dataset_example
case_id: case_25_online_pharmacy_management_system_2
domain: Online Pharmacy Management System Scenario 2
complexity: simple
split_role: rag_train
---

# Online Pharmacy Management System Scenario 2 — Polished Requirement Specification

## Requirement

Online Pharmacy Management System Scenario 2 — Polished Requirement Specification

Functional Requirements
1. The system shall allow admins to update medicine details.
2. The system shall allow admins to manage customer orders.
3. The system shall allow admins to view delivery addresses related to customer orders.
4. The system shall allow admins to update attendance records.
5. The system shall allow admins to update salary details.

## Reference PlantUML

```plantuml
@startuml
title UML State Machine Diagram - Admin

[*] --> UpdateMedicine

state "Update medicine" as UpdateMedicine
state "Manage orders" as ManageOrders
state "View delivery address" as ViewDeliveryAddress
state "Update attendance" as UpdateAttendance
state "Update salary" as UpdateSalary

UpdateMedicine --> ManageOrders
ManageOrders --> ViewDeliveryAddress
ViewDeliveryAddress --> UpdateAttendance
UpdateAttendance --> UpdateSalary
UpdateSalary --> [*]

@enduml

```
