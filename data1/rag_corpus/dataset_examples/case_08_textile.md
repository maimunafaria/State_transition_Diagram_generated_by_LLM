---
source_type: dataset_example
case_id: case_08_textile
domain: Textile
complexity: medium
split_role: rag_train
---

# Textile — Polished Requirement Specification

## Requirement

Textile — Polished Requirement Specification

Functional Requirements
1. The system shall allow customers to create an account by filling in required details.
2. The system shall enable customers to place orders for garments once they are registered.
3. The system shall send out sample materials if a customer needs them after placing an order.
4. The system shall review the availability of raw materials for orders that require stock checking.
5. The system shall purchase raw materials if they are not available after stock checking.
6. The system shall process raw materials if they are already available.
7. The system shall begin garment production once raw materials are ready, either through purchasing or processing.
8. The system shall conduct a defect check on the produced garments.
9. The system shall deliver the finished garments to the customer if all checks pass.
10. The system shall complete billing and payment processes after delivering the garments.
11. The system shall generate a report along with feedback at the end of the process.

## Reference PlantUML

```plantuml
@startuml

[*] --> CustomerRegistration
state Choice1 <<choice>>
state Choice2 <<choice>>
CustomerRegistration : entry / Start state
CustomerRegistration : do / Fill in required details
CustomerRegistration : exit / Getting garment orders

CustomerRegistration --> GettingGarmentOrders : registration complete

GettingGarmentOrders : entry / Customer registration
GettingGarmentOrders : do / Place the orders
GettingGarmentOrders : exit / Sampling / Stock checking

GettingGarmentOrders --> Sampling : sampling required
GettingGarmentOrders --> StockChecking : check stock

Sampling : entry / Getting garment orders
Sampling : do / Send out sample materials while ordering
Sampling : exit / decision

Sampling --> Choice1 : proceed
StockChecking --> Choice1

StockChecking : entry / Getting garment orders
StockChecking : do / Check availability of raw material
StockChecking : exit / decision making

Choice1 --> PurchasingRawMaterials : not in stock
Choice1 --> ProcessingRawMaterials : in stock

PurchasingRawMaterials : entry / Stock checking
PurchasingRawMaterials : do / Buy raw materials
PurchasingRawMaterials : exit / Production of garments

ProcessingRawMaterials : entry / Stock checking
ProcessingRawMaterials : do / Processing
ProcessingRawMaterials : exit / Production of garments
ProcessingRawMaterials --> Choice2
PurchasingRawMaterials --> Choice2
Choice2 --> ProductionOfGarments

ProductionOfGarments : entry / Purchasing or processing of raw materials
ProductionOfGarments : do / Manufacturing
ProductionOfGarments : exit / Product checking

ProductionOfGarments --> ProductChecking

ProductChecking : entry / Production of garments
ProductChecking : do / Checking for defects and clearance
ProductChecking : exit / Receiving the ordered garments

ProductChecking --> ReceivingOrderedGarments

ReceivingOrderedGarments : entry / Product checking
ReceivingOrderedGarments : do / Garment delivered
ReceivingOrderedGarments : exit / Billing

ReceivingOrderedGarments --> Billing

Billing : entry / Receiving the ordered garments
Billing : do / Making payments
Billing : exit / Report generation

Billing --> ReportGeneration

ReportGeneration : entry / Billing
ReportGeneration : do / Giving feedback
ReportGeneration : exit / final state

ReportGeneration --> [*]

@enduml

```
