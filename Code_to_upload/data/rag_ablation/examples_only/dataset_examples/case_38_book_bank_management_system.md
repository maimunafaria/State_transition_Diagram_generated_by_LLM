---
source_type: dataset_example
case_id: case_38_book_bank_management_system
domain: Book Bank Management System
complexity: complex
split_role: rag_train
---

# Book Bank Management System — Polished Requirement Specification

## Requirement

Book Bank Management System — Polished Requirement Specification

Functional Requirements
1. The system shall allow a user to register by entering their details.
2. The system shall issue a member ID and complete the registration upon correct entry of details.
3. The system shall require the user to re-enter their details upon incorrect entry of details.
4. The system shall allow a user to log in after successful registration using their member ID and password.
5. The system shall allow the user to continue upon correct entry of member ID and password during login. Otherwise, they cannot log in.
6. The system shall allow a user to search for a book by entering its details.
7. The system shall show suggestions if a book is found during a search; otherwise, it shall allow the user to choose another option.
8. The system shall allow a user to get a book by entering its ID and their member ID.
9. The system shall allow the user to get the book if their membership is active; otherwise, it shall require them to pay the fine amount first.
10. The system shall allow a user to buy a book by entering its ID and seeing the price.
11. The system shall provide the book if the user pays; otherwise, it shall end the process there.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram

state "Registration" as Registration {
  [*] --> RegEnterDetails

  state "Enter Details" as RegEnterDetails
  state "Get Member_ID" as GetMemberID
  state "Successful Registration" as SuccessfulRegistration
  state "Re-enter Details" as ReEnterDetails

  RegEnterDetails --> GetMemberID : [Valid]
  RegEnterDetails --> ReEnterDetails : [Invalid]
  ReEnterDetails --> RegEnterDetails
  GetMemberID --> SuccessfulRegistration
}

state "Authentication" as Authentication {
  [*] --> AuthEnterMemberID

  state "Enter Member_ID" as AuthEnterMemberID
  state "Enter Password" as EnterPassword
  state "successful Login" as SuccessfulLogin
  state "Invalid Member_ID or Password" as InvalidCreds

  AuthEnterMemberID --> EnterPassword
  EnterPassword --> SuccessfulLogin : [Valid]
  EnterPassword --> InvalidCreds : [Invalid]
}

state "Search Books" as SearchBooks {
  [*] --> EnterBookDetails

  state "Enter Book Details" as EnterBookDetails
  state "Display Suggestion" as DisplaySuggestion
  state "choose Alternate option" as ChooseAlternate

  EnterBookDetails --> DisplaySuggestion : [Found]
  EnterBookDetails --> ChooseAlternate : [Not Found]
}

state "Get Books" as GetBooksState {
  [*] --> GetEnterBookID

  state "Enter Book_ID" as GetEnterBookID
  state "Enter Member_ID" as GetEnterMemberID
  state "Obtain Books" as ObtainBooks
  state "Pay Fine Amount" as PayFineAmount

  GetEnterBookID --> GetEnterMemberID
  GetEnterMemberID --> ObtainBooks : [Active Member]
  GetEnterMemberID --> PayFineAmount : [Inactive Member]
}

state "Buy Books" as BuyBooks {
  [*] --> BuyEnterBookID

  state "Enter Book_ID" as BuyEnterBookID
  state "Display Book Amount" as DisplayBookAmount
  state "Get Books" as BuyGetBooks
  state BuyNotPaidEnd <<choice>>

  BuyEnterBookID --> DisplayBookAmount
  DisplayBookAmount --> BuyGetBooks : [Paid]
  DisplayBookAmount --> BuyNotPaidEnd : [Not Paid]
  BuyNotPaidEnd --> [*]
}

state StartJoin <<choice>>

[*] --> StartJoin
StartJoin --> Registration
StartJoin --> Authentication
StartJoin --> SearchBooks
StartJoin --> GetBooksState
StartJoin --> BuyBooks

SuccessfulRegistration --> AuthEnterMemberID

SuccessfulLogin --> EnterBookDetails
SuccessfulLogin --> GetEnterBookID
SuccessfulLogin --> BuyEnterBookID


ObtainBooks --> [*]
BuyGetBooks --> [*]

@enduml

```
