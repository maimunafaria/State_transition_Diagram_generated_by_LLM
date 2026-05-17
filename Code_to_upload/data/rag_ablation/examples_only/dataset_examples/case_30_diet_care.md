---
source_type: dataset_example
case_id: case_30_diet_care
domain: Diet Care
complexity: medium
split_role: rag_train
---

# Diet Care — Polished Requirement Specification

## Requirement

Diet Care — Polished Requirement Specification

Functional Requirements
1. The system shall allow users to choose between entering their information or consulting a professional nutritionist.
2. The system shall enable users who choose consultation to speak with a nutritionist and rate the experience afterward.
3. The system shall analyze the information entered by the user.
4. The system shall identify if the user has an unhealthy diet, a disease or deficiency, or follows a healthy diet based on the analyzed information.
5. The system shall provide suitable food suggestions if the analysis indicates an unhealthy diet.
6. The system shall provide food suggestions to help with the identified disease or deficiency if found during the analysis.
7. The system shall appreciate users for following a healthy diet if their diet is already healthy.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram



state StartChoice <<choice>>

state Input
Input : entry / validate user
Input : do / provide data to model
Input : exit / processing of data

state Consult
Consult : entry / user's choice of consultation
Consult : do / consult professional nutritionist
Consult : exit / rate professional nutritionist

state Analysis
Analysis : entry / input data for processing
Analysis : do / analyse data
Analysis : exit / detect unhealthy diet or deficiencies

state "Unhealthy diet" as UnhealthyDiet
UnhealthyDiet : entry / detection of unhealthy diet
UnhealthyDiet : do / find healthy diet
UnhealthyDiet : exit / suggest to users

state "Disease or deficiencies" as DiseaseDef
DiseaseDef : entry / presence of disease or deficiencies
DiseaseDef : do / find food that fights that disease
DiseaseDef : exit / suggest to users

state "Healthy diet" as HealthyDiet
HealthyDiet : do / presence of healthy diet
HealthyDiet : do / appreciate user's diet
HealthyDiet : exit / terminate

state Suggestion
Suggestion : entry / presence of disease or deficiency or unhealthy diet
Suggestion : do / search for nutrient food
Suggestion : exit / suggest to users

state AnalysisChoice <<choice>>
state MergeSuggest <<choice>>

[*] --> StartChoice
StartChoice --> Input
StartChoice --> Consult

Input --> Analysis
Analysis --> AnalysisChoice
Analysis --> Analysis
AnalysisChoice --> UnhealthyDiet
AnalysisChoice --> DiseaseDef
AnalysisChoice --> HealthyDiet

UnhealthyDiet --> MergeSuggest
DiseaseDef --> MergeSuggest

MergeSuggest --> Suggestion

Consult --> [*]
HealthyDiet --> [*]
Suggestion --> [*]

@enduml

```
