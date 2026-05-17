---
source_type: dataset_example
case_id: case_40_startup_meet
domain: Startup Meet
complexity: complex
split_role: rag_train
---

# Startup Meet — Polished Requirement Specification

## Requirement

Startup Meet — Polished Requirement Specification

Functional Requirements
1. The system shall allow the user to select their roll (investor, entrepreneur, or mentor).
2. The system shall enable the user to sign in after choosing a role.
3. The system shall allow the signed-in user to submit a startup idea.
4. The system shall review the submitted startup idea.
5. The system shall provide mentorship based on the review result.
6. The system shall make an investment decision if the startup idea is presented to an investor.
7. The system shall provide funding based on the investment decision.
8. The system shall end the process once all actions are completed.

## Reference PlantUML

```plantuml
@startuml
title UML State Chart Diagram

[*] --> UserType

state UserType <<choice>>

UserType --> InvestorLogin : [Investor user]
UserType --> EntrepreneurLogin : [Entrepreneur user]
UserType --> MentorLogin : [Mentor user]

state "Investor Login" as InvestorLogin
InvestorLogin : entry / Action needed
InvestorLogin : do / enter login credentials
InvestorLogin : exit / Entered into system

state "Entrepreneur Login" as EntrepreneurLogin
EntrepreneurLogin : entry / Action needed
EntrepreneurLogin : do / enter login credentials
EntrepreneurLogin : exit / Entered into system

state "Mentor Login" as MentorLogin
MentorLogin : entry / Action needed
MentorLogin : do / enter login credentials
MentorLogin : exit / Entered into system

state MergeLogin <<choice>>

InvestorLogin --> MergeLogin
EntrepreneurLogin --> MergeLogin
MentorLogin --> MergeLogin

state "Startup idea" as StartupIdea
StartupIdea : entry / Submitted by entrepreneur
StartupIdea : do / file the idea
StartupIdea : exit / accept or decline state

MergeLogin --> StartupIdea

state "Decision on Startup idea" as DecisionIdea
DecisionIdea : entry / startup idea state
DecisionIdea : do / accept or decline
DecisionIdea : exit / NIL

StartupIdea --> DecisionIdea

state ChoiceDecision <<choice>>
DecisionIdea --> ChoiceDecision

state "Accept mentorship" as AcceptMentorship
AcceptMentorship : entry / decision on mentorship
AcceptMentorship : do / mentorship
AcceptMentorship : exit / NIL

state "Present Idea" as PresentIdea
PresentIdea : entry / Decision on startup
PresentIdea : do / present idea to investor
PresentIdea : exit / Decision on investing

state "Investment" as Investment
Investment : entry / Decision to invest
Investment : do / give investment
Investment : exit / share in profit

ChoiceDecision --> AcceptMentorship
ChoiceDecision --> PresentIdea

state MergeEnd <<choice>>

AcceptMentorship --> MergeEnd
PresentIdea --> Investment
Investment --> MergeEnd
ChoiceDecision --> MergeEnd
MergeEnd --> [*]

@enduml

```
