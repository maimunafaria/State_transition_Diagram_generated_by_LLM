from __future__ import annotations

from .constants import STATE_ALIAS_RE, STATE_DECL_RE, TRANSITION_RE
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

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_inline_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("@"):
            continue
        if line.startswith("skinparam") or line.startswith("hide") or line.startswith("title"):
            continue

        alias_match = STATE_ALIAS_RE.match(line)
        if alias_match:
            label = sanitize_name(alias_match.group("label"))
            alias = alias_match.group("alias").strip()
            aliases[alias] = label
            states.add(label)
            continue

        state_match = STATE_DECL_RE.match(line)
        if state_match:
            state_name = sanitize_name(state_match.group("name"))
            if state_name and state_name != "[*]":
                states.add(state_name)
            continue

        trans_match = TRANSITION_RE.match(line)
        if trans_match:
            src_raw = sanitize_name(trans_match.group("src"))
            dst_raw = sanitize_name(trans_match.group("dst"))
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
    )


def validate_graph(graph: DiagramGraph) -> ValidationResult:
    errors = list(graph.parse_errors)
    warnings: list[str] = []

    initial_candidates = sorted(set(graph.initial_targets))
    if not initial_candidates:
        errors.append("missing_initial_state_transition ([*] --> state)")
        initial_state = None
    elif len(initial_candidates) > 1:
        errors.append(f"multiple_initial_state_targets ({', '.join(initial_candidates)})")
        initial_state = None
    else:
        initial_state = initial_candidates[0]

    dup_count = len(graph.transitions) - len(set(graph.transitions))
    if dup_count > 0:
        errors.append(f"duplicate_transitions_detected ({dup_count})")

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


def parse_and_validate_puml_text(puml_text: str) -> tuple[DiagramGraph, ValidationResult]:
    graph = parse_plantuml(puml_text)
    validation = validate_graph(graph)
    return graph, validation
