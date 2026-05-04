---
source_type: dataset_example
case_id: case_76_ui
domain: Ui
complexity: medium
split_role: rag_train
---

# Ui — Polished Requirement Specification

## Requirement

Ui — Polished Requirement Specification

Functional Requirements
1. The system shall allow users to open a budget-checking window from the main screen.
2. The system shall wait for the user to select a client before proceeding with the checking process.
3. The system shall require users to select a campaign related to the chosen client before allowing them to check information.
4. The system shall display results only after both a client and a campaign are selected.
5. The system shall allow users to refresh or recheck information by pressing the check button again.
6. The system shall prompt users with a confirmation message before closing the window.
7. The system shall return to the main screen if the user confirms closing the window.
8. The system shall keep the window open and allow further interaction if the user cancels the close action.

## Reference PlantUML

```plantuml
@startuml
title Check Budget Window State Machine

state "Main Window" as MainWindow
state "5 Alert Dialog" as AlertDialog

state "Check Budget Window" as CBW {
  [*] --> NoClientSelected

  state "1 No Client Selected" as NoClientSelected

  state "Selection Flow" as SelectionFlow {
    [*] --> NoCampaignSelected

    state "2 No Campaign Selected" as NoCampaignSelected

    state "Result Flow" as ResultFlow {
      [*] --> Blank
      state "3 Blank" as Blank
      state "4 Display Result" as DisplayResult

      Blank --> DisplayResult : checkButtonClicked()
      DisplayResult --> DisplayResult : checkButtonClicked()
    }

    NoCampaignSelected --> ResultFlow : campaignSelected()
    ResultFlow --> ResultFlow : campaignSelected()
  }

  NoClientSelected --> SelectionFlow : clientSelected()
  SelectionFlow --> SelectionFlow : clientSelected()
  state H <<history*>>
}

MainWindow --> CBW : checkCampaignBudget\nMenuSelected()

CBW --> AlertDialog : closeButtonClicked()

AlertDialog --> MainWindow : OK
AlertDialog --> H : Cancel

@enduml

```
