from __future__ import annotations

import shutil
import subprocess
import tempfile
import re
from pathlib import Path

from .constants import STATE_ALIAS_RE, STATE_ALIAS_REVERSE_RE, STATE_DECL_RE, TRANSITION_RE
from .models import DiagramGraph, ValidationResult


def sanitize_name(name: str) -> str:
    name = name.strip()
    if name.startswith('"') and name.endswith('"') and len(name) >= 2:
        name = name[1:-1]
    return " ".join(name.split())


def sanitize_event(event: str | None) -> str:
    if not event:
        return ""
    return " ".join(event.strip().split())


def normalize_stereotype(stereotype: str | None) -> str:
    if not stereotype:
        return ""
    return " ".join(stereotype.strip().lower().split())


def strip_history_suffix(name: str) -> tuple[str, bool]:
    clean = name.strip()
    if clean.endswith("[H*]"):
        return clean[:-4].strip(), True
    if clean.endswith("[H]"):
        return clean[:-3].strip(), True
    return clean, clean in {"[H]", "[H*]"}


def normalize_puml_text(text: str) -> str:
    extracted = extract_plantuml_block(text)
    if extracted:
        return extracted
    clean = text.strip()
    if not clean:
        return "@startuml\n@enduml\n"
    return "@startuml\n" + clean + "\n@enduml\n"


def extract_plantuml_block(text: str) -> str:
    if not text:
        return ""
    start = text.find("@startuml")
    end = text.rfind("@enduml")
    if start != -1 and end != -1 and end >= start:
        return text[start : end + len("@enduml")].strip() + "\n"
    return ""


def strip_inline_comment(line: str) -> str:
    # PlantUML uses single quote for inline comments.
    if "'" in line:
        return line.split("'", 1)[0]
    return line


def parse_plantuml(puml_text: str) -> DiagramGraph:
    text = normalize_puml_text(puml_text)
    aliases: dict[str, str] = {}
    states: set[str] = set()
    transitions: list[tuple[str, str, str]] = []
    initial_targets: list[str] = []
    final_states: set[str] = set()
    parse_errors: list[str] = []
    stereotypes: dict[str, set[str]] = {}
    explicit_states: set[str] = set()
    composite_states: set[str] = set()
    history_states: set[str] = set()
    composite_stack: list[str] = []
    note_block = False

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_inline_comment(raw_line).strip()
        if not line:
            continue
        low = line.lower()
        if note_block:
            if low == "end note":
                note_block = False
            continue
        if low.startswith("note ") or low == "note on link":
            note_block = "end note" not in low and not re.match(r"^note\s+.+\s*:\s*", low)
            continue
        if line.startswith("@"):
            continue
        if line in {"}", "--", "||"}:
            if line == "}" and composite_stack:
                composite_stack.pop()
            continue
        if line.startswith(("skinparam", "hide", "title", "left to right direction")):
            continue
        if ":" in line and not TRANSITION_RE.match(line):
            state_part = line.split(":", 1)[0].strip()
            if state_part and " " not in state_part and not state_part.startswith("note"):
                state_name = aliases.get(state_part, sanitize_name(state_part))
                states.add(state_name)
                explicit_states.add(state_name)
                continue

        alias_match = STATE_ALIAS_RE.match(line) or STATE_ALIAS_REVERSE_RE.match(line)
        if alias_match:
            label = sanitize_name(alias_match.group("label"))
            alias = alias_match.group("alias").strip()
            stereotype = normalize_stereotype(alias_match.groupdict().get("stereo"))
            aliases[alias] = label
            states.add(label)
            explicit_states.add(label)
            if stereotype:
                stereotypes.setdefault(label, set()).add(stereotype)
            if line.endswith("{"):
                composite_states.add(label)
                composite_stack.append(label)
            continue

        state_match = STATE_DECL_RE.match(line)
        if state_match:
            state_name = sanitize_name(state_match.group("name"))
            stereotype = normalize_stereotype(state_match.groupdict().get("stereo"))
            if state_name and state_name != "[*]":
                states.add(state_name)
                explicit_states.add(state_name)
                if stereotype:
                    stereotypes.setdefault(state_name, set()).add(stereotype)
                if line.endswith("{"):
                    composite_states.add(state_name)
                    composite_stack.append(state_name)
            continue

        trans_match = TRANSITION_RE.match(line)
        if trans_match:
            src_raw = sanitize_name(trans_match.group("src"))
            dst_raw = sanitize_name(trans_match.group("dst"))
            arrow = trans_match.group("arrow")
            hidden = "[hidden]" in arrow
            src_raw, src_history = strip_history_suffix(src_raw)
            dst_raw, dst_history = strip_history_suffix(dst_raw)
            if src_history or dst_history:
                history_states.add(src_raw if src_history else dst_raw)
            src = aliases.get(src_raw, src_raw)
            dst = aliases.get(dst_raw, dst_raw)
            event = sanitize_event(trans_match.group("event"))

            if src == "[*]" and dst != "[*]":
                initial_targets.append(dst)
                states.add(dst)
                continue

            if dst == "[*]" and src != "[*]":
                final_states.add(src)
                states.add(src)
                continue

            if src == "[*]" and dst == "[*]":
                parse_errors.append(f"line_{line_no}: invalid [*] -> [*] transition")
                continue

            if src:
                states.add(src)
            if dst:
                states.add(dst)
            if src and dst:
                if not hidden:
                    transitions.append((src, event, dst))
            else:
                parse_errors.append(f"line_{line_no}: empty src/dst in transition")
            continue

    return DiagramGraph(
        states=states,
        transitions=transitions,
        initial_targets=initial_targets,
        final_states=final_states,
        aliases=aliases,
        parse_errors=parse_errors,
        stereotypes=stereotypes,
        explicit_states=explicit_states,
        composite_states=composite_states,
        history_states=history_states,
    )


def validate_graph(graph: DiagramGraph) -> ValidationResult:
    errors = list(graph.parse_errors)
    warnings: list[str] = []

    if not graph.initial_targets:
        errors.append("missing_initial_state_transition ([*] --> state)")
        initial_state = None
    elif len(graph.initial_targets) > 1:
        errors.append(f"multiple_initial_state_transitions ({', '.join(graph.initial_targets)})")
        initial_state = None
    else:
        initial_state = graph.initial_targets[0]

    if not graph.final_states:
        errors.append("missing_final_state_transition (state --> [*])")

    dup_count = len(graph.transitions) - len(set(graph.transitions))
    if dup_count > 0:
        errors.append(f"duplicate_transitions_detected ({dup_count})")

    incoming: dict[str, int] = {state: 0 for state in graph.states}
    outgoing: dict[str, int] = {state: 0 for state in graph.states}
    for target in graph.initial_targets:
        incoming[target] = incoming.get(target, 0) + 1
    for final_state in graph.final_states:
        outgoing[final_state] = outgoing.get(final_state, 0) + 1
    for src, _, dst in graph.transitions:
        outgoing[src] = outgoing.get(src, 0) + 1
        incoming[dst] = incoming.get(dst, 0) + 1

    unreachable: list[str] = []
    if initial_state:
        adjacency: dict[str, set[str]] = {s: set() for s in graph.states}
        for src, _, dst in graph.transitions:
            adjacency.setdefault(src, set()).add(dst)
            adjacency.setdefault(dst, set())

        visited: set[str] = set()
        stack = [initial_state]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            stack.extend(sorted(adjacency.get(node, set()) - visited))

        unreachable = sorted(graph.states - visited)
        if unreachable:
            errors.append("unreachable_states_detected")
            warnings.append("unreachable: " + ", ".join(unreachable))

    orphan_states = sorted(
        state
        for state in graph.explicit_states
        if incoming.get(state, 0) == 0 and outgoing.get(state, 0) == 0
    )
    if orphan_states:
        errors.append("orphan_states_detected")
        warnings.append("orphan: " + ", ".join(orphan_states))

    for state, state_stereotypes in sorted(graph.stereotypes.items()):
        if "choice" in state_stereotypes:
            outgoing_transitions = [t for t in graph.transitions if t[0] == state]
            if not outgoing_transitions:
                errors.append(f"choice_node_without_outgoing_transitions ({state})")
            unguarded = [event for _, event, _ in outgoing_transitions if not event.strip().startswith("[")]
            if unguarded:
                errors.append(f"choice_node_without_guarded_outgoing_transitions ({state})")

        if "fork" in state_stereotypes and outgoing.get(state, 0) < 2:
            errors.append(f"fork_without_multiple_outgoing_branches ({state})")

        if "join" in state_stereotypes and incoming.get(state, 0) < 2:
            errors.append(f"join_without_multiple_incoming_branches ({state})")

    if graph.history_states and not graph.composite_states:
        errors.append("history_state_used_without_composite_state")

    return ValidationResult(
        valid=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
        initial_state=initial_state,
        duplicate_transition_count=dup_count,
        unreachable_states=unreachable,
        state_count=len(graph.states),
        transition_count=len(set(graph.transitions)),
    )


def check_plantuml_syntax(puml_text: str, timeout: int = 30) -> list[str]:
    plantuml = shutil.which("plantuml")
    if not plantuml:
        return ["plantuml_command_not_found_for_official_syntax_check"]

    text = normalize_puml_text(puml_text)
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "diagram.puml"
        path.write_text(text, encoding="utf-8")
        result = subprocess.run(
            [plantuml, "-tpng", "--no-error-image", str(path)],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    if result.returncode == 0:
        return []

    output = "\n".join(
        part.strip() for part in (result.stdout, result.stderr) if part.strip()
    ).strip()
    message = "; ".join(output.splitlines()[:2]) if output else f"exit_code={result.returncode}"
    message = message.replace(str(path), "diagram.puml")
    return [f"plantuml_syntax_error: {message}"]


def parse_and_validate_puml_text(puml_text: str) -> tuple[DiagramGraph, ValidationResult]:
    graph = parse_plantuml(puml_text)
    validation = validate_graph(graph)
    syntax_errors = check_plantuml_syntax(puml_text)
    if syntax_errors:
        validation.errors.extend(syntax_errors)
        validation.valid = False
    return graph, validation
