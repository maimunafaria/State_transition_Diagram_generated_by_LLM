from __future__ import annotations

import unittest

from plantuml_pipeline.graph_repair import (
    apply_deterministic_graph_repairs,
    apply_graph_edit_plan,
    parse_graph_edit_plan,
)
from plantuml_pipeline.generation import validator_guided_repair_score
from plantuml_pipeline.parser import parse_and_validate_puml_text


def validate_without_compiler(puml_text: str):
    return parse_and_validate_puml_text(puml_text, official_syntax=False)[1]


class ParserAliasTests(unittest.TestCase):
    def test_alias_used_before_declaration_resolves_to_visible_label(self) -> None:
        puml = """@startuml
[*] --> CreateUser
state "Create User" as CreateUser
state "Done" as Done
CreateUser --> Done
Done --> [*]
@enduml
"""
        graph, validation = parse_and_validate_puml_text(
            puml,
            official_syntax=False,
        )

        self.assertEqual(graph.initial_targets, ["Create User"])
        self.assertEqual(graph.states, {"Create User", "Done"})
        self.assertEqual(validation.warnings, [])


class DeterministicGraphRepairTests(unittest.TestCase):
    def test_removes_duplicate_and_adds_unique_final_transition(self) -> None:
        puml = """@startuml
state A
state B
[*] --> A
A --> B : finish
A --> B : finish
@enduml
"""
        validation = validate_without_compiler(puml)
        repaired, edits = apply_deterministic_graph_repairs(puml, validation)
        repaired_validation = validate_without_compiler(repaired)

        self.assertTrue(any(edit["operation"] == "remove_duplicate_transition" for edit in edits))
        self.assertTrue(any(edit["operation"] == "add_final_transition" for edit in edits))
        self.assertEqual(repaired.count("A --> B : finish"), 1)
        self.assertIn("B --> [*]", repaired)
        self.assertEqual(repaired_validation.warnings, [])

    def test_selects_only_initial_target_that_reaches_every_state(self) -> None:
        puml = """@startuml
state A
state B
state C
[*] --> A
[*] --> B
A --> B
B --> C
C --> [*]
@enduml
"""
        validation = validate_without_compiler(puml)
        repaired, edits = apply_deterministic_graph_repairs(puml, validation)
        repaired_validation = validate_without_compiler(repaired)

        self.assertTrue(any(edit["operation"] == "set_initial" for edit in edits))
        self.assertEqual(repaired.count("[*] -->"), 1)
        self.assertIn("[*] --> A", repaired)
        self.assertEqual(repaired_validation.warnings, [])

    def test_does_not_guess_how_to_connect_an_orphan(self) -> None:
        puml = """@startuml
state A
state B
state Orphan
[*] --> A
A --> B
B --> [*]
@enduml
"""
        validation = validate_without_compiler(puml)
        repaired, edits = apply_deterministic_graph_repairs(puml, validation)

        self.assertEqual(repaired, puml)
        self.assertEqual(edits, [])

    def test_score_detects_partial_reduction_in_unreachable_states(self) -> None:
        before = """@startuml
state A
state B
state C
state D
[*] --> A
A --> B
B --> [*]
@enduml
"""
        after = """@startuml
state A
state B
state C
state D
[*] --> A
A --> B
B --> C
B --> [*]
@enduml
"""
        before_validation = validate_without_compiler(before)
        after_validation = validate_without_compiler(after)

        self.assertLess(
            validator_guided_repair_score(after_validation),
            validator_guided_repair_score(before_validation),
        )


class LlmGraphEditPlanTests(unittest.TestCase):
    def test_parses_and_applies_orphan_connection_plan(self) -> None:
        puml = """@startuml
state "Start Work" as StartWork
state "Finish Work" as FinishWork
state "Archive Work" as ArchiveWork
[*] --> StartWork
StartWork --> FinishWork : complete
FinishWork --> [*]
@enduml
"""
        response = """{
          "edits": [
            {
              "operation": "add_transition",
              "source": "Finish Work",
              "target": "Archive Work",
              "label": "archive"
            },
            {
              "operation": "add_final_transition",
              "state": "Archive Work"
            }
          ],
          "reason": "Connect the requirement-supported archive state."
        }"""
        plan, reason, parse_error = parse_graph_edit_plan(response)
        repaired, applied, apply_error = apply_graph_edit_plan(puml, plan)
        validation = validate_without_compiler(repaired)

        self.assertEqual(parse_error, "")
        self.assertEqual(apply_error, "")
        self.assertIn("requirement-supported", reason)
        self.assertEqual(len(applied), 2)
        self.assertIn("FinishWork --> ArchiveWork : archive", repaired)
        self.assertIn("ArchiveWork --> [*]", repaired)
        self.assertEqual(validation.warnings, [])

    def test_replaces_unguarded_choice_label(self) -> None:
        puml = """@startuml
state Start
state Decision <<choice>>
state Accepted
[*] --> Start
Start --> Decision
Decision --> Accepted : approved
Accepted --> [*]
@enduml
"""
        plan = [
            {
                "operation": "replace_transition_label",
                "source": "Decision",
                "target": "Accepted",
                "old_label": "approved",
                "new_label": "[approved]",
            }
        ]
        repaired, applied, error = apply_graph_edit_plan(puml, plan)
        validation = validate_without_compiler(repaired)

        self.assertEqual(error, "")
        self.assertEqual(len(applied), 1)
        self.assertIn("Decision --> Accepted : [approved]", repaired)
        self.assertNotIn(
            "choice_node_without_guarded_outgoing_transitions",
            "\n".join(validation.warnings),
        )

    def test_rejects_unknown_state_without_changing_candidate(self) -> None:
        puml = """@startuml
state A
state B
[*] --> A
A --> B
B --> [*]
@enduml
"""
        repaired, applied, error = apply_graph_edit_plan(
            puml,
            [
                {
                    "operation": "add_transition",
                    "source": "A",
                    "target": "InventedState",
                    "label": "event",
                }
            ],
        )

        self.assertEqual(repaired, puml)
        self.assertEqual(applied, [])
        self.assertIn("unknown_or_ambiguous_state", error)


if __name__ == "__main__":
    unittest.main()
