---
source_type: dataset_example
case_id: case_31_student_counselling_management_system
domain: Student Counselling Management System
complexity: complex
split_role: rag_train
---

# Student Counselling Management System — Polished Requirement Specification

## Requirement

Student Counselling Management System — Polished Requirement Specification

Functional Requirements
1. The system shall allow a student to log in.
2. The system shall prompt the student to try again if login details are incorrect.
3. The system shall proceed with registration and payment upon a successful login.
4. The system shall end there if the registration payment is not completed.
5. The system shall register the student and declare ranks if the registration payment is completed.
6. The system shall allow the student to pay enrollment fees after rank declaration.
7. The system shall end there if the payment for enrollment fees is not successful.
8. The system shall allow the student to fill in their choices if the payment for enrollment fees is successful.
9. The system shall lock the choices and allocate seats based on rank if they are correct.
10. The system shall generate an admit letter once a seat is allotted.
11. The system shall allow the student to accept or decline the admit letter.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram

[*] --> StartMerge

state StartMerge <<choice>>
state Login
state LoginDecision <<choice>>
state "Invalid Login" as InvalidLogin
state "Valid Login" as ValidLogin
state RegistrationDecision <<choice>>
state "Failed Registration" as FailedRegistration
state "Rank Declaration" as RankDeclaration
state "Enrollment Fees" as EnrollmentFees
state PaymentDecision <<choice>>
state "Invalid Payment" as InvalidPayment
state "Valid Payment" as ValidPayment
state "Choice Filing" as ChoiceFiling
state ChoiceDecision <<choice>>
state "Failed choice filing" as FailedChoiceFiling
state "Seat Allotment" as SeatAllotment
state "Admit Letter Generation" as AdmitLetterGeneration
state "Accept/Decline" as AcceptDecline

Login : entry / To Action
Login : do / Log in to the system
Login : exit / Username and password entered

InvalidLogin : entry / Trying to log in
InvalidLogin : do / Invalid username and password
InvalidLogin : exit / Back to login page

ValidLogin : entry / Student logged in
ValidLogin : do / Registration form submission with payment
ValidLogin : exit / Student Registered

FailedRegistration : entry / Payment not made
FailedRegistration : do / Throw an error
FailedRegistration : exit / Abnormal termination

RankDeclaration : entry / Student registered
RankDeclaration : do / Declare ranks for all the students
RankDeclaration : exit / Rank published

EnrollmentFees : entry / Rank declared
EnrollmentFees : do / Pay enrollment fees
EnrollmentFees : exit / Payment done

InvalidPayment : entry / Payment not made
InvalidPayment : do / Show the errors
InvalidPayment : exit / Abnormal Termination

ValidPayment : entry / Payment made
ValidPayment : do / Allow to fill choices
ValidPayment : exit / log out from payment portal

ChoiceFiling : entry / Valid payment
ChoiceFiling : do / Fill choices
ChoiceFiling : exit / Lock choices

FailedChoiceFiling : entry / Invalid choices
FailedChoiceFiling : do / Show the errors
FailedChoiceFiling : exit / Abnormal Termination

SeatAllotment : entry / Choices must be locked
SeatAllotment : do / Allot seats based on rank
SeatAllotment : exit / Publish alloted results

AdmitLetterGeneration : entry / Seat alotted
AdmitLetterGeneration : do / Generate admit letter
AdmitLetterGeneration : exit / Publish admit letters to students and colleges

AcceptDecline : entry / Received admit letter
AcceptDecline : do / Accept/Decline
AcceptDecline : exit / After decision is made

StartMerge --> Login
Login --> LoginDecision
LoginDecision --> InvalidLogin
LoginDecision --> ValidLogin
InvalidLogin --> StartMerge

ValidLogin --> RegistrationDecision
RegistrationDecision --> FailedRegistration
RegistrationDecision --> RankDeclaration

RankDeclaration --> EnrollmentFees
EnrollmentFees --> PaymentDecision
PaymentDecision --> InvalidPayment
PaymentDecision --> ValidPayment

ValidPayment --> ChoiceFiling
ChoiceFiling --> ChoiceDecision
ChoiceDecision --> FailedChoiceFiling
ChoiceDecision --> SeatAllotment

SeatAllotment --> AdmitLetterGeneration
AdmitLetterGeneration --> AcceptDecline
AcceptDecline --> [*]

FailedRegistration --> [*]
InvalidPayment --> [*]
FailedChoiceFiling --> [*]

@enduml

```
