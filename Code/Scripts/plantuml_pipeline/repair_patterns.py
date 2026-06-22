from __future__ import annotations


def syntax_patterns_for_issues(issues: list[str]) -> list[tuple[str, str]]:
    patterns: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(name: str, snippet: str) -> None:
        if name not in seen:
            patterns.append((name, snippet.strip()))
            seen.add(name)

    for issue in issues:
        low = issue.lower()
        if "plantuml_syntax_error" in low or "empty src/dst" in low:
            add(
                "valid state-diagram skeleton",
                """
@startuml
[*] --> INITIAL_STATE
INITIAL_STATE --> NEXT_STATE : SUPPORTED_EVENT
NEXT_STATE --> [*] : COMPLETION_EVENT
@enduml
""",
            )
        if "invalid [*]" in low:
            add(
                "replace direct pseudo-state termination",
                """
' Replace [*] --> [*] with a real terminal-state transition
TERMINAL_STATE --> [*] : COMPLETION_EVENT
""",
            )
        if "multiple_initial_state_transitions" in low:
            add(
                "exactly one top-level initial transition",
                """
[*] --> INITIAL_STATE

' Replace every additional [*] --> OTHER_STATE with a normal supported transition
REACHABLE_STATE --> OTHER_STATE : SUPPORTED_EVENT
""",
            )
        if "missing_initial_state_transition" in low:
            add(
                "missing initial transition",
                """
[*] --> INITIAL_STATE
""",
            )
        if "missing_final_state_transition" in low:
            add(
                "missing final transition",
                """
TERMINAL_STATE --> [*] : COMPLETION_EVENT
""",
            )
        if "orphan" in low:
            add(
                "connect a requirement-supported orphan state",
                """
PREVIOUS_STATE --> ORPHAN_STATE : SUPPORTED_EVENT
ORPHAN_STATE --> NEXT_STATE : SUPPORTED_EVENT
""",
            )
        if "unreachable" in low:
            add(
                "connect a requirement-supported unreachable state",
                """
REACHABLE_STATE --> UNREACHABLE_STATE : SUPPORTED_EVENT
UNREACHABLE_STATE --> NEXT_STATE : SUPPORTED_EVENT
""",
            )
        if "duplicate_transitions" in low:
            add(
                "merge duplicate transitions",
                """
' Keep one transition for the same source and target
SOURCE_STATE --> TARGET_STATE : COMBINED_SUPPORTED_EVENT
""",
            )
        if "choice_node_without_outgoing" in low or "choice_node_without_guarded" in low:
            add(
                "valid guarded choice node",
                """
state DECISION_NODE <<choice>>
SOURCE_STATE --> DECISION_NODE : SUPPORTED_EVENT
DECISION_NODE --> FIRST_STATE : [FIRST_GUARD]
DECISION_NODE --> SECOND_STATE : [SECOND_GUARD]
""",
            )
        if "fork_without_multiple_outgoing" in low:
            add(
                "valid fork node",
                """
state FORK_NODE <<fork>>
SOURCE_STATE --> FORK_NODE : SUPPORTED_EVENT
FORK_NODE --> FIRST_PARALLEL_STATE
FORK_NODE --> SECOND_PARALLEL_STATE
""",
            )
        if "join_without_multiple_incoming" in low:
            add(
                "valid join node",
                """
state JOIN_NODE <<join>>
FIRST_PARALLEL_STATE --> JOIN_NODE
SECOND_PARALLEL_STATE --> JOIN_NODE
JOIN_NODE --> NEXT_STATE
""",
            )
        if "history_state_used_without_composite_state" in low:
            add(
                "history state inside a composite state",
                """
state COMPOSITE_STATE {
  [H] --> RESUMED_CHILD_STATE
}
""",
            )

    if not patterns:
        add(
            "generic valid transition",
            """
SOURCE_STATE --> TARGET_STATE : SUPPORTED_EVENT
""",
        )
    return patterns


def format_syntax_patterns(issues: list[str]) -> str:
    sections: list[str] = []
    for index, (name, snippet) in enumerate(syntax_patterns_for_issues(issues), start=1):
        sections.append(f"Pattern {index}: {name}\n{snippet}")
    return "\n\n".join(sections)


def format_hybrid_issue_repair_blocks(issues: list[str]) -> str:
    blocks: list[str] = []
    seen: set[str] = set()

    def add(
        key: str,
        issue_name: str,
        objective: str,
        pattern: str,
        restriction: str,
    ) -> None:
        if key in seen:
            return
        seen.add(key)
        blocks.append(
            "\n".join(
                [
                    f"Issue: {issue_name}",
                    "",
                    "Repair objective:",
                    objective,
                    "",
                    "Valid syntax pattern:",
                    pattern.strip(),
                    "",
                    "Restriction:",
                    restriction,
                ]
            )
        )

    for issue in issues:
        low = issue.lower()
        if "plantuml_syntax_error" in low or "empty src/dst" in low:
            add(
                "syntax_error",
                "plantuml_syntax_error",
                "Restore a valid PlantUML state-machine structure before repairing other issues.",
                """@startuml
[*] --> INITIAL_STATE
INITIAL_STATE --> NEXT_STATE : SUPPORTED_EVENT
NEXT_STATE --> [*] : COMPLETION_EVENT
@enduml""",
                "Preserve valid existing declarations and transitions; replace only malformed syntax.",
            )
        if "invalid [*]" in low:
            add(
                "invalid_pseudostate_transition",
                "invalid_initial_to_final_transition",
                "Replace every direct initial-to-final pseudostate transition with a real lifecycle path.",
                """[*] --> INITIAL_STATE
INITIAL_STATE --> TERMINAL_STATE : SUPPORTED_EVENT
TERMINAL_STATE --> [*] : COMPLETION_EVENT""",
                "Use existing requirement-supported lifecycle states and do not leave [*] --> [*].",
            )
        if "multiple_initial_state_transitions" in low:
            add(
                "multiple_initial",
                "multiple_initial_state_transitions",
                "Keep exactly one top-level initial transition and connect other entry states normally.",
                """[*] --> INITIAL_STATE
REACHABLE_STATE --> OTHER_STATE : SUPPORTED_EVENT""",
                "Do not create a choice node or new state merely to remove an extra initial transition.",
            )
        if "missing_initial_state_transition" in low:
            add(
                "missing_initial",
                "missing_initial_state_transition",
                "Add exactly one transition from the initial pseudostate to the first lifecycle state.",
                "[*] --> INITIAL_STATE",
                "Use an existing requirement-supported first state and do not add another top-level initial transition.",
            )
        if "missing_final_state_transition" in low:
            add(
                "missing_final",
                "missing_final_state_transition",
                "Add at least one final transition from an existing natural terminal state.",
                "TERMINAL_STATE --> [*] : COMPLETION_EVENT",
                "Use an existing requirement-supported terminal state; do not create a new state when one can naturally terminate the lifecycle.",
            )
        if "orphan" in low:
            add(
                "orphan",
                "orphan_states_detected",
                "Connect every listed requirement-supported orphan state to the lifecycle with reasonable incoming or outgoing transitions.",
                """PREVIOUS_STATE --> ORPHAN_STATE : SUPPORTED_EVENT
ORPHAN_STATE --> NEXT_STATE : SUPPORTED_EVENT""",
                "Use only requirement-supported transitions; remove an orphan state only when the requirement does not support it.",
            )
        if "unreachable" in low:
            add(
                "unreachable",
                "unreachable_states_detected",
                "Create a valid path from a reachable state to every listed requirement-supported unreachable state.",
                """REACHABLE_STATE --> UNREACHABLE_STATE : SUPPORTED_EVENT
UNREACHABLE_STATE --> NEXT_STATE : SUPPORTED_EVENT""",
                "Do not connect a state using invented or unsupported system behavior.",
            )
        if "duplicate_transitions" in low:
            add(
                "duplicate",
                "duplicate_transitions_detected",
                "Keep only one transition for each duplicated source-target-event combination.",
                "SOURCE_STATE --> TARGET_STATE : SUPPORTED_EVENT",
                "Remove an identical duplicate without changing unrelated transitions; merge labels only when both meanings are requirement-supported.",
            )
        if "choice_node_without_outgoing" in low:
            add(
                "choice_outgoing",
                "choice_node_without_outgoing_transitions",
                "Add requirement-supported outgoing alternatives to every listed choice node.",
                """CHOICE_NODE --> FIRST_STATE : [FIRST_GUARD]
CHOICE_NODE --> SECOND_STATE : [SECOND_GUARD]""",
                "Do not invent branches; remove the choice stereotype if the requirement supports no decision.",
            )
        if "choice_node_without_guarded" in low:
            add(
                "choice_guards",
                "choice_node_outgoing_transitions_without_guards",
                "Add mutually meaningful guards to all outgoing transitions from the choice node.",
                """CHOICE_NODE --> FIRST_STATE : [FIRST_GUARD]
CHOICE_NODE --> SECOND_STATE : [SECOND_GUARD]""",
                "Use guards supported by the requirement or existing transition meaning.",
            )
        if "fork_without_multiple_outgoing" in low:
            add(
                "fork",
                "fork_without_multiple_outgoing_branches",
                "Give each retained fork node at least two requirement-supported outgoing parallel branches.",
                """SOURCE_STATE --> FORK_NODE : SUPPORTED_EVENT
FORK_NODE --> FIRST_PARALLEL_STATE
FORK_NODE --> SECOND_PARALLEL_STATE""",
                "Remove the fork stereotype instead when the requirement does not describe parallel behavior.",
            )
        if "join_without_multiple_incoming" in low:
            add(
                "join",
                "join_without_multiple_incoming_branches",
                "Give each retained join node at least two incoming parallel branches.",
                """FIRST_PARALLEL_STATE --> JOIN_NODE
SECOND_PARALLEL_STATE --> JOIN_NODE
JOIN_NODE --> NEXT_STATE""",
                "Remove the join stereotype instead when the requirement does not merge parallel behavior.",
            )
        if "history_state_used_without_composite_state" in low:
            add(
                "history",
                "history_state_used_without_composite_state",
                "Place each retained history pseudostate inside its requirement-supported composite state.",
                """state COMPOSITE_STATE {
  [H] --> RESUMED_CHILD_STATE
}""",
                "Remove history behavior when the requirement does not support resuming a composite state.",
            )

    if not blocks:
        add(
            "generic",
            "listed_validation_issue",
            "Fix the listed issue with the smallest requirement-preserving transition edit.",
            "SOURCE_STATE --> TARGET_STATE : SUPPORTED_EVENT",
            "Do not change unrelated states, transitions, or labels.",
        )
    return "\n\n".join(blocks)


def format_all_structural_validation_patterns() -> str:
    return """--- PlantUML Structural Validation Patterns ---

The uppercase identifiers below are placeholders.
Replace them with existing requirement-supported states, events, and guards.
Do not copy placeholder names into the final diagram.

Pattern 1: never connect the initial pseudostate directly to the final pseudostate

' Invalid
[*] --> [*]

' Valid
[*] --> INITIAL_STATE
INITIAL_STATE --> TERMINAL_STATE : SUPPORTED_EVENT
TERMINAL_STATE --> [*] : COMPLETION_EVENT


Pattern 2: use exactly one top-level initial transition

' Invalid
[*] --> FIRST_STATE
[*] --> SECOND_STATE

' Valid
[*] --> FIRST_STATE
FIRST_STATE --> SECOND_STATE : SUPPORTED_EVENT


Pattern 3: add a missing initial transition

[*] --> INITIAL_STATE


Pattern 4: add a missing final transition

TERMINAL_STATE --> [*] : COMPLETION_EVENT


Pattern 5: connect every requirement-supported orphan state

PREVIOUS_STATE --> ORPHAN_STATE : SUPPORTED_EVENT
ORPHAN_STATE --> NEXT_STATE : SUPPORTED_EVENT

' If ORPHAN_STATE is unsupported by the requirement, omit it.


Pattern 6: create a path to every requirement-supported unreachable state

REACHABLE_STATE --> UNREACHABLE_STATE : SUPPORTED_EVENT
UNREACHABLE_STATE --> NEXT_STATE : SUPPORTED_EVENT

' If UNREACHABLE_STATE is unsupported by the requirement, omit it.


Pattern 7: keep only one transition for the same source and target

' Invalid
SOURCE_STATE --> TARGET_STATE : FIRST_EVENT
SOURCE_STATE --> TARGET_STATE : FIRST_EVENT

' Valid
SOURCE_STATE --> TARGET_STATE : COMBINED_SUPPORTED_EVENT


Pattern 8: every choice node must have outgoing transitions

state DECISION_NODE <<choice>>
SOURCE_STATE --> DECISION_NODE : SUPPORTED_EVENT
DECISION_NODE --> FIRST_STATE : [FIRST_GUARD]
DECISION_NODE --> SECOND_STATE : [SECOND_GUARD]


Pattern 9: choice-node outgoing transitions must use guards

' Invalid
DECISION_NODE --> FIRST_STATE
DECISION_NODE --> SECOND_STATE

' Valid
DECISION_NODE --> FIRST_STATE : [FIRST_GUARD]
DECISION_NODE --> SECOND_STATE : [SECOND_GUARD]


Pattern 10: a fork node must have multiple outgoing branches

state FORK_NODE <<fork>>
SOURCE_STATE --> FORK_NODE : SUPPORTED_EVENT
FORK_NODE --> FIRST_PARALLEL_STATE
FORK_NODE --> SECOND_PARALLEL_STATE


Pattern 11: a join node must have multiple incoming branches

state JOIN_NODE <<join>>
FIRST_PARALLEL_STATE --> JOIN_NODE
SECOND_PARALLEL_STATE --> JOIN_NODE
JOIN_NODE --> NEXT_STATE


Pattern 12: use history only inside a composite state

state COMPOSITE_STATE {
  [H] --> RESUMED_CHILD_STATE
}


Pattern 13: do not add another [*] transition inside a composite state

' Invalid
state PARENT_STATE {
  [*] --> CHILD_STATE
}

' Valid
state PARENT_STATE {
  state CHILD_STATE
}
PARENT_STATE --> CHILD_STATE : SUPPORTED_EVENT
""".strip()
