---
source_type: dataset_example
case_id: case_35_art_gallery_mananement_system
domain: Art Gallery Mananement System
complexity: medium
split_role: rag_train
---

# Art Gallery Mananement System — Polished Requirement Specification

## Requirement

Art Gallery Mananement System — Polished Requirement Specification

Functional Requirements
1. The system shall verify login credentials upon submission.
2. The system shall display an error message and prevent further interaction if login details are incorrect.
3. The system shall allow users to view products or update their information after a successful login.
4. The system shall allow users to select items and place an order when viewing products.
5. The system shall add selected product items to the order and prepare billing details.
6. The system shall allow users to choose a payment method after adding products to their order.
7. The system shall process and deliver the order if the payment is successful.
8. The system shall end the process without further action if the payment fails.
9. The system shall allow users to save updated information after entering new details.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram


[*] --> Login

state Login
Login : entry / getInfo
Login : do / verifyData
Login : exit / verified

state LoginDecision <<choice>>
Login --> LoginDecision

state "Valid Login" as ValidLogin
ValidLogin : entry / contain Info
ValidLogin : do / allow Access to system
ValidLogin : exit / gallery Entry

state "Invalid Login" as InvalidLogin
InvalidLogin : entry / wrong Info
InvalidLogin : do / display Error message
InvalidLogin : exit / return To Start

LoginDecision --> ValidLogin
LoginDecision --> InvalidLogin

state NavChoice <<choice>>
ValidLogin --> NavChoice

state Gallery
Gallery : entry / show Products
Gallery : do / allow to select Products
Gallery : exit / save Products

state Update
Update : entry / contain Info
Update : do / take New Info
Update : exit / save new Info

NavChoice --> Gallery
NavChoice --> Update

Update --> [*]

state Order
Order : entry / select Items
Order : do / allowto order If products In Stock
Order : exit / verification

state Cart
Cart : entry / contain Selected Items
Cart : do / all billing Info
Cart : exit / payment Method

Gallery --> Order
Order --> Cart

state Payment
Payment : entry / get Payment Method
Payment : do / confirm Payment
Payment : exit / verify

Cart --> Payment

state PayDecision <<choice>>
Payment --> PayDecision

state "Valid Payment" as ValidPayment
ValidPayment : entry / payment Method
ValidPayment : do / get Cash
ValidPayment : exit / confirmation of product

state "Invalid Payment" as InvalidPayment
InvalidPayment : entry / wrong Entry
InvalidPayment : do / error Message
InvalidPayment : exit / return

PayDecision --> ValidPayment
PayDecision --> InvalidPayment


state Delivery
Delivery : entry / take out Order
Delivery : do / deliver Product
Delivery : exit / exit System

ValidPayment --> Delivery
Delivery --> [*]

InvalidPayment --> [*]

@enduml

```
