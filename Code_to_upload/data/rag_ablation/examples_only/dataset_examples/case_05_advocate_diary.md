---
source_type: dataset_example
case_id: case_05_advocate_diary
domain: Advocate Diary
complexity: complex
split_role: rag_train
---

# Advocate Diary — Polished Requirement Specification

## Requirement

Advocate Diary — Polished Requirement Specification

Functional Requirements
1. The system shall allow users to explore blogs and news updates.
2. The system shall permit users to leave at any time after viewing blogs and news updates.
3. The system shall enable users to create an account by providing their details.
4. The system shall check the provided details during account creation.
5. The system shall prevent users from proceeding if the provided details are incorrect during account creation.
6. The system shall allow users to sign in using a password after creating an account.
7. The system shall check the entered password during sign-in.
8. The system shall allow users to add a new case after signing in.
9. The system shall require users to select a category ( civil or criminal ) when adding a new case.
10. The system shall allow users to enter details for the selected category when adding a new case.
11. The system shall enable users to set reminders after entering case details.
12. The system shall allow users to upload related documents for their cases.
13. The system shall enable users to file something online after signing in.
14. The system shall allow users to download model forms after signing in.
15. The system shall enable users to view references ( quick or book )after signing in.
16. The system shall allow users to provide feedback after signing in.
17. The system shall permit users to leave the system after completing their tasks.

## Reference PlantUML

```plantuml
@startuml
title UML state machine diagram

state "View blogs as news updates" as ViewBlogs
ViewBlogs : entry/Visit page
ViewBlogs : do/Shows blogs and news updates
ViewBlogs : exit/Leave the page

state "Register" as Register
Register : entry/New user
Register : do/Verify details
Register : exit/Verified details

state "Login" as Login
Login : entry/Registered
Login : do/Verify password
Login : exit/View details

state "View details and logs" as ViewDetails
ViewDetails : entry/Login
ViewDetails : do/Show details of case and logs
ViewDetails : exit/Do required function

state "Add case" as AddCase
AddCase : entry/Wants to add case
AddCase : do/Show Category
AddCase : exit/Selects a category

state "Civil" as Civil
Civil : entry/Selects this category
Civil : do/update view table
Civil : exit/Allows to add details

state "Criminal" as Criminal
Criminal : entry/Selects this category
Criminal : do/Update the view table
Criminal : exit/Allows to add details

state "Add details" as AddDetails
AddDetails : entry/Selects category
AddDetails : do/Add details about case
AddDetails : exit/Update view table

state "Add remainder" as AddReminder
AddReminder : entry/Adds details
AddReminder : do/Add remainder
AddReminder : exit/Update calender

state "Upload document" as UploadDocument
UploadDocument : entry/Add details
UploadDocument : do/Upload documents
UploadDocument : exit/leave page

state "File online" as FileOnline
FileOnline : entry/Prefers online filing
FileOnline : do/Select category
FileOnline : exit/Click a link

state "Redirect to page" as RedirectPage
RedirectPage : entry/Click a link
RedirectPage : do/Redirects to page
RedirectPage : exit/Returns to page

state "Download model forms" as DownloadForms
DownloadForms : entry/wants to download forms
DownloadForms : do/Select a form
DownloadForms : exit/Downloads form

state "Reference" as Reference
Reference : entry/Pefers to refer
Reference : do/Select a category
Reference : exit/prefered categoried is showed

state "Quick References" as QuickReferences
QuickReferences : entry/Selects quick references
QuickReferences : do/Shows some Quick references
QuickReferences : exit/Leave the page

state "Books" as Books
Books : entry/Selects books
Books : do/Shows books
Books : exit/Leave page

state "Feedback" as Feedback
Feedback : entry/Wants to give feedback
Feedback : do/Add feedback
Feedback : exit/Exit page

state "Logout" as Logout
Logout : entry/Wants to leave the site
Logout : do/The session of logged in user ended
Logout : exit/Leave the site

state J1 <<choice>>
state J2 <<choice>>
state J3 <<choice>>
state J4 <<choice>>
state J5 <<choice>>
state J6 <<choice>>

state J10 <<choice>>

[*] --> J1

J1 --> ViewBlogs
J1 --> Register

ViewBlogs --> [*]

Register --> J2
J2 --> [*] : [Invalid Credentials]
J2 --> Login : [Valid]

Login --> [*] : [Improper]
Login --> ViewDetails : [Proper]

ViewDetails --> J3

J3 --> AddCase
J3 --> FileOnline
J3 --> DownloadForms
J3 --> Reference
J3 --> Feedback

AddCase --> J4
J4 --> Civil
J4 --> Criminal

Civil --> J5
Criminal --> J5
J5 --> AddDetails
AddDetails --> AddReminder
AddReminder --> UploadDocument
UploadDocument --> J10

FileOnline --> RedirectPage
RedirectPage --> J10

DownloadForms --> J10

Reference --> J6
J6 --> QuickReferences
J6 --> Books
QuickReferences --> J10
Books --> J10

Feedback --> J10

J10 --> Logout
Logout --> [*]

@enduml

```
