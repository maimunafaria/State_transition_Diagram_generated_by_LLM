---
source_type: dataset_example
case_id: case_27_equihealth
domain: Equihealth
complexity: complex
split_role: rag_train
---

# Equihealth — Polished Requirement Specification

## Requirement

Equihealth — Polished Requirement Specification

Functional Requirements
1. The system shall allow new users to create an account.
2. The system shall check if a user's registration is completed before allowing them to sign in.
3. The system shall display different dashboards based on the user type after they sign in (patient, health worker, or government official).
4. The system shall show a patient dashboard to users who enter as patients, allowing them to provide medical information.
5. The system shall allow health workers to check and use the medical information provided by patients for further analysis.
6. The system shall prepare alerts based on the analyzed information, which may be sent to either the patient or the health worker.
7. The system shall show planned activities (from the analysis) to health workers.
8. The system shall display health planning results (from the analysis) to government officials.
9. The system shall allow users to log out after they complete their tasks.

## Reference PlantUML

```plantuml
@startuml
title UML state machine diagram

[*] --> J1 : [check user]
state J1 <<choice>>
state J2 <<choice>>
state J3 <<choice>>
state J4 <<choice>>
state "Register" as Register
Register : entry/when the user are user
Register : do/Register process
Register : exit/ successful registration
Register : exit/ invalid registration

state "Login" as Login {

  state "Patient dashboard" as PatientDashboard
  PatientDashboard : entry/if the user is logged in as patient
  PatientDashboard : do/dashboard is displayed
  PatientDashboard : exit/when user logout

  state "Health worker Dashboard" as HealthWorkerDashboard
  HealthWorkerDashboard : entry/if the user is logged in as health worker
  HealthWorkerDashboard : do/display the health worker dashboard
  HealthWorkerDashboard : exit/if health worker logout

  state "Government dashboard" as GovernmentDashboard
  GovernmentDashboard : entry/if the user is government official
  GovernmentDashboard : do/display government dashboard
  GovernmentDashboard : exit/after his activity is finished

  state "Data Entry" as DataEntry
  DataEntry : entry/if the data entry is logged in as patient
  DataEntry : do/data entry is processed
  DataEntry : exit/after data entry is completed
  DataEntry : exit/send the data for validation

  state "Validation of medical data" as ValidationMedicalData
  ValidationMedicalData : entry/if the data entry by the patient is completed
  ValidationMedicalData : do/validate the data by healthworker
  ValidationMedicalData : exit/after validation of medical data is completed

  state "Health Financing" as HealthPlanning
  HealthPlanning : entry/analysis of data should be done
  HealthPlanning : do/the basis of analysed data the best health schemes are drafted
  HealthPlanning : exit/ the health schemes are sent to the government dashboard

  state "Analysis" as Analysis
  Analysis : entry/if the data entered is validated
  Analysis : do/analysis of data
  Analysis : exit/after analysis of data
  Analysis : exit/send data to health monitoring
  Analysis : exit/send data to activity scheduling module

  state "Activity Scheduling" as ActivityScheduling
  ActivityScheduling : entry/analysis of data should be done
  ActivityScheduling : do/activity is scheduled for the healthworkers
  ActivityScheduling : exit/the activity scheduling is complete
  ActivityScheduling : exit/send data to alert module
  ActivityScheduling : exit/send the schedule to health worker dashboard

  state "Alerts" as Alerts
  Alerts : entry/when data from analysis is received
  Alerts : do/prepare alerts
  Alerts : exit/after sending alerts patient dashboard and health worker dashboard

  [*] --> LJ
  state LJ <<choice>>

  LJ --> PatientDashboard
  LJ --> HealthWorkerDashboard
  LJ --> GovernmentDashboard

  PatientDashboard --> DataEntry
  DataEntry --> ValidationMedicalData
  DataEntry --> Analysis

  Analysis --> ActivityScheduling
  Analysis --> Alerts
  Analysis --> HealthPlanning
  Alerts --> PatientDashboard
  Alerts --> HealthWorkerDashboard
  ActivityScheduling --> HealthWorkerDashboard
  HealthWorkerDashboard --> ValidationMedicalData
  HealthPlanning --> GovernmentDashboard
}

state "Logout" as Logout
Logout : entry/when the user completes his process
Logout : do/logout user
Logout : exit/successfully logged out

J1 --> Register : [ new user ]
Register --> J2
J1 --> J2
J2 --> J3
J3 --> Login
J3 --> J4
Login --> J4
J4 --> Logout
J2 --> [*]
Logout --> [*]

@enduml

```
