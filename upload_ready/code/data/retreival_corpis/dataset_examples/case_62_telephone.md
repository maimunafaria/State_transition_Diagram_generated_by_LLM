---
source_type: dataset_example
case_id: case_62_telephone
domain: Telephone
complexity: medium
split_role: rag_train
---

# Telephone — Polished Requirement Specification

## Requirement

Telephone — Polished Requirement Specification

Functional Requirements
1. The system shall provide a dial tone upon receiver pickup.
2. The system shall start processing the entered number when the user begins entering digits.
3. The system shall inform the user or play a message if the entered number is incomplete or incorrect.
4. The system shall play a message to prompt the user if they stop dialing for a while.
5. The system shall attempt to connect the call once a valid number is entered.
6. The system shall play a busy tone if the line is busy.
7. The system shall start ringing on the other end if the connection goes through.
8. The system shall connect the call and allow both parties to talk when the person being called answers.
9. The system shall end the call and return to an idle state if either party hangs up.
10. The system shall allow calls to be stopped or terminated at any point.

## Reference PlantUML

```plantuml
@startuml
title Telephone State Machine

[*] --> Idle

Idle --> Active : lift receiver / get dial tone
Active --> Idle : caller hangs up / disconnect

state Active {

    [*] --> DialTone

    state DialTone
    DialTone : do / play dial tone

    DialTone --> Dialing : dial digit(n)
    DialTone --> TimeOut : after (15 sec.)

    state Dialing

    Dialing --> Dialing : dial digit(n) [incomplete]
    Dialing --> Connecting : dial digit(n) [valid] / connect
    Dialing --> Invalid : dial digit(n) [invalid]
    Dialing --> TimeOut : after (15 sec.)

    state Invalid
    Invalid : do / play message

    state TimeOut
    TimeOut : do / play message

    state Connecting
    Connecting --> Busy : busy
    Connecting --> Ringing : connected

    state Busy
    Busy : do / play busy tone

    state Ringing
    Ringing : do / play ringing tone

    Ringing --> Talking : callee answers / enable speech

    state Talking
    Talking --> Pinned : callee hangs up
    Talking --> Pinned : callee answers

    state Pinned

}

Active --> [*] : terminate
Active --> [*] : abort

@enduml

```
