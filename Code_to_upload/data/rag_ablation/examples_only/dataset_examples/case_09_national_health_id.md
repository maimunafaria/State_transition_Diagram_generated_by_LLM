---
source_type: dataset_example
case_id: case_09_national_health_id
domain: National Health Id
complexity: medium
split_role: rag_train
---

# National Health Id — Polished Requirement Specification

## Requirement

National Health Id — Polished Requirement Specification

Functional Requirements
1. The system shall check if a person is an Indian citizen.
2. The system shall verify the details of an Indian citizen.
3. The system shall generate a unique health ID for registered Indian citizens.
4. The system shall activate an account upon successful login.
5. The system shall support after activation, the system shall allow users to either add old files or set permissions.
6. The system shall store added old files.
7. The system shall provide access to relevant authorities based on set permissions.
8. The system shall allow adding new files when permission is granted.
9. The system shall store all the information provided by users.
10. The system shall allow the government to access stored data to view details and prepare reports.

## Reference PlantUML

```plantuml
@startuml

[*] --> Choice1
state Choice1 <<choice>>
state Choice2 <<choice>>
state Choice3 <<choice>>
Choice1 --> Verification : Indian
Choice1 --> [*] : not Indian

Verification : entry / Citizenship status
Verification : do / Verify details
Verification : exit / Verified status

Verification --> Registration : verified

Registration : entry / Citizenship status
Registration : do / Register with ID
Registration : exit / Unique National Health ID

Registration --> Login : registered

Login : entry / National Health ID
Login : do / Login with the ID
Login : exit / Logged in to the account

Login --> Choice2 
Choice2 --> Activation : login success
Choice2 --> [*] 
Activation : entry / Logged in the account
Activation : do / Activate the account
Activation : exit / Activated account

Activation --> AddFiles : add old files
Activation --> Permission : proceed to permissions

AddFiles : entry / Activated account
AddFiles : do / Add the files
AddFiles : exit / Added old files

AddFiles --> Repository

Permission : entry / Activated account
Permission : do / Providing permissions
Permission : exit / Access of authorities

Permission --> Access : permission granted
Permission --> Repository : saving permissions

Access : entry / Checking for permission
Access : do / Accessing the files
Access : exit / Adding new files

Access --> Choice3 
Choice3 --> Repository : given permission
Choice3 --> [*] 
Access --> [*] : no permission

Government : entry / Having repository
Government : do / Accessing the details
Government : exit / Analysis report

Government --> Repository

Repository : entry / Government repository
Repository : do / Saving the details
Repository : exit / Logged out

Repository --> [*]

@enduml

```
