---
source_type: dataset_example
case_id: case_06_my_helper
domain: My Helper
complexity: medium
split_role: rag_train
---

# My Helper — Polished Requirement Specification

## Requirement

My Helper — Polished Requirement Specification

Functional Requirements
1. The system shall allow new users or users who have forgotten their password to create a new password.
2. The system shall enable the user to continue using the app after setting a correct password.
3. The system shall allow users to send messages from another mobile phone if they cannot use their own phone.
4. The system shall read incoming messages to understand the user's needs.
5. The system shall check the user’s password for correctness and inform the user if it is wrong.
6. The system shall ensure that if the user's password is correct, the system shall check the user’s request.
7. The system shall support for valid requests, the system shall complete them and send back required details to the user.
8. The system shall support for invalid requests, the system shall inform the user that the request cannot be accepted.

## Reference PlantUML

```plantuml
@startuml

[*] --> LoginSignup

LoginSignup : entry / Download app
LoginSignup : do / Enables the user to use app
LoginSignup : exit / Verifies details

LoginSignup --> SetPassword : signup / forgot password
SetPassword : entry / Signup
SetPassword : do / Set password
SetPassword : exit / Validate password

SetPassword --> LoginSignup : password set

LoginSignup --> SendSMS : forgot phone
SendSMS : entry / Forgot phone
SendSMS : do / Send SMS from any other mobile
SendSMS : exit / NIL

SendSMS --> ReadsSMS : SMS sent
ReadsSMS : entry / SMS received
ReadsSMS : do / Scans SMS
ReadsSMS : exit / Performs required action

ReadsSMS --> VerifyPassword : verify request
VerifyPassword : entry / Read SMS
VerifyPassword : do / Check whether password is correct
VerifyPassword : exit / Password is correct

VerifyPassword --> ChecksRequirement : password correct
VerifyPassword --> PasswordError : incorrect password

PasswordError : entry / Incorrect password
PasswordError : do / Send SMS stating incorrect password
PasswordError : exit / SMS sent
PasswordError --> [*]

ChecksRequirement : entry / Password is correct
ChecksRequirement : do / Check for requirement
ChecksRequirement : exit / Requirement is valid

ChecksRequirement --> FulfilRequirements : requirement valid
ChecksRequirement --> RequirementError : invalid requirement

FulfilRequirements : entry / Requirement is valid
FulfilRequirements : do / Fulfils requirement
FulfilRequirements : exit / NIL

FulfilRequirements --> SendRequestedDetails : fulfil completed
SendRequestedDetails : entry / Requirement is fulfilled
SendRequestedDetails : do / Send requested details back in form of SMS
SendRequestedDetails : exit / SMS has been sent
SendRequestedDetails --> [*]

RequirementError : entry / Invalid requirement
RequirementError : do / Send SMS stating invalid requirement
RequirementError : exit / SMS sent
RequirementError --> [*]

@enduml

```
