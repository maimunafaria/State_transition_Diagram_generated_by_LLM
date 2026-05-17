---
source_type: dataset_example
case_id: case_22_crime_bureau
domain: Crime Bureau
complexity: medium
split_role: rag_train
---

# Crime Bureau — Polished Requirement Specification

## Requirement

Crime Bureau — Polished Requirement Specification

Functional Requirements
1. The system shall allow a user to log in by entering their username and password.
2. The system shall allow the user to try again if the login details are incorrect until successful login.
3. The system shall allow the user to choose between requesting an FIR, requesting a petition, or viewing the list of wanted and missing persons after login.
4. The system shall display the requested information once the user selects an option.
5. The system shall allow a police user to log in by entering their username and password.
6. The system shall allow the police user to try again if the login details are incorrect until successful login.
7. The system shall allow the police user to view the list of wanted and missing persons or perform major activities such as adding station details and crime records after login.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram


state "Login Verification" as LV
LV : entry / Enters username and password
LV : do / Verification of login credentials of users
LV : exit / Enters the website if login is correct

state "Requests FIR" as RF
RF : entry / Verified login
RF : do / FIR Request
RF : exit / Displays FIR

state "Requests Petition" as RP
RP : entry / Verified login
RP : do / Requests Petition
RP : exit / Displays Petition

state "Requests Wanted person and missing list" as RW
RW : entry / Verified login
RW : do / Requests Wanted persons
RW : do / Requests Missing list
RW : exit / Saving changes

state Choice1 <<choice>>

LV --> LV : Repeats until login credentials are correct
LV --> Choice1 : Chooses any one

Choice1 --> RF
Choice1 --> RP
Choice1 --> RW

RF --> [*]
RP --> [*]
RW --> [*]



state "Login Verification-Police" as LVP
LVP : entry / Enters username and password
LVP : do / Verification of login credentials
LVP : exit / Enters the website if login is correct

state "Requests Wanted person and missing list" as RWP
RWP : entry / Verified login
RWP : do / Requests Wanted persons
RWP : do / Requests Missing list
RWP : exit / Saving changes

state "Performs Major Activities" as PMA
PMA : entry / EntryAction1
PMA : do / Add station details
PMA : do / Add crimes
PMA : exit / Saving changes

state Choice2 <<choice>>

LVP --> LVP : Repeats until login credentials are correct
LVP --> Choice2 : Chooses any one

Choice2 --> RWP
Choice2 --> PMA

RWP --> [*]
PMA --> [*]

@enduml

```
