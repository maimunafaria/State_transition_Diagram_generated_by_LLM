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
