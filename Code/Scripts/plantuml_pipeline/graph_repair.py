from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .constants import STATE_ALIAS_RE, STATE_ALIAS_REVERSE_RE, STATE_DECL_RE, TRANSITION_RE
from .models import DiagramGraph, ValidationResult
from .parser import normalize_puml_text, parse_plantuml, sanitize_event, sanitize_name

MAX_GRAPH_EDITS = 4


def _compact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _alias_maps(puml_text: str) -> tuple[dict[str, str], dict[str, str]]:
    token_to_label: dict[str, str] = {}
    label_to_reference: dict[str, str] = {}

    for raw_line in normalize_puml_text(puml_text).splitlines():
        line = raw_line.strip()
        alias_match = STATE_ALIAS_RE.match(line) or STATE_ALIAS_REVERSE_RE.match(line)
        if alias_match:
            label = sanitize_name(alias_match.group("label"))
            alias = alias_match.group("alias").strip()
            token_to_label[alias] = label
            token_to_label[label] = label
            label_to_reference.setdefault(label, alias)
            continue

        state_match = STATE_DECL_RE.match(line)
        if not state_match:
            continue
        raw_name = state_match.group("name").strip()
        label = sanitize_name(raw_name)
        token_to_label[label] = label
        label_to_reference.setdefault(
            label,
            raw_name if raw_name.startswith('"') else label,
        )

    return token_to_label, label_to_reference


def _canonical_endpoint(endpoint: str, token_to_label: dict[str, str]) -> str:
    clean = sanitize_name(endpoint)
    return token_to_label.get(clean, clean)


def _transition_signature(
    line: str,
    token_to_label: dict[str, str],
) -> tuple[str, str, str] | None:
    match = TRANSITION_RE.match(line.strip())
    if not match:
        return None
    return (
        _canonical_endpoint(match.group("src"), token_to_label),
        sanitize_event(match.group("event")),
        _canonical_endpoint(match.group("dst"), token_to_label),
    )


def _insert_before_enduml(puml_text: str, new_lines: list[str]) -> str:
    lines = normalize_puml_text(puml_text).splitlines()
    insert_at = next(
        (
            index
            for index in range(len(lines) - 1, -1, -1)
            if lines[index].strip().lower() == "@enduml"
        ),
        len(lines),
    )
    return normalize_puml_text("\n".join(lines[:insert_at] + new_lines + lines[insert_at:]))


def _resolve_state_reference(
    requested: str,
    graph: DiagramGraph,
    puml_text: str,
) -> tuple[str, str]:
    token_to_label, label_to_reference = _alias_maps(puml_text)
    clean = sanitize_name(requested)
    canonical = token_to_label.get(clean, clean)

    if canonical not in graph.states:
        compact = _compact_name(clean)
        matches = [
            state
            for state in sorted(graph.states)
            if _compact_name(state) == compact
        ]
        if len(matches) != 1:
            return "", f"unknown_or_ambiguous_state: {requested}"
        canonical = matches[0]

    reference = label_to_reference.get(canonical)
    if reference:
        return reference, ""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", canonical):
        return canonical, ""
    return f'"{canonical}"', ""


def _remove_duplicate_transition_lines(puml_text: str) -> tuple[str, list[dict[str, Any]]]:
    token_to_label, _ = _alias_maps(puml_text)
    lines = normalize_puml_text(puml_text).splitlines()
    seen: set[tuple[str, str, str]] = set()
    output: list[str] = []
    edits: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(lines, start=1):
        signature = _transition_signature(raw_line, token_to_label)
        if signature is None or signature not in seen:
            output.append(raw_line)
            if signature is not None:
                seen.add(signature)
            continue
        edits.append(
            {
                "operation": "remove_duplicate_transition",
                "line": line_number,
                "transition": list(signature),
            }
        )

    if not edits:
        return puml_text, []
    return normalize_puml_text("\n".join(output)), edits


def _remove_invalid_initial_final_lines(
    puml_text: str,
) -> tuple[str, list[dict[str, Any]]]:
    token_to_label, _ = _alias_maps(puml_text)
    lines = normalize_puml_text(puml_text).splitlines()
    output: list[str] = []
    edits: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(lines, start=1):
        signature = _transition_signature(raw_line, token_to_label)
        if signature and signature[0] == "[*]" and signature[2] == "[*]":
            edits.append(
                {
                    "operation": "remove_invalid_initial_final_transition",
                    "line": line_number,
                }
            )
            continue
        output.append(raw_line)

    if not edits:
        return puml_text, []
    return normalize_puml_text("\n".join(output)), edits


def _reachable_states(graph: DiagramGraph, start: str) -> set[str]:
    adjacency: dict[str, set[str]] = {state: set() for state in graph.states}
    for source, _, target in graph.transitions:
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set())

    visited: set[str] = set()
    stack = [start]
    while stack:
        state = stack.pop()
        if state in visited:
            continue
        visited.add(state)
        stack.extend(sorted(adjacency.get(state, set()) - visited))
    return visited


def _real_state_candidates(graph: DiagramGraph) -> set[str]:
    pseudostereotypes = {"choice", "fork", "join", "history", "deephistory"}
    return {
        state
        for state in graph.states
        if not (graph.stereotypes.get(state, set()) & pseudostereotypes)
        and state not in graph.history_states
    }


def _deterministic_initial_state(graph: DiagramGraph) -> str:
    real_states = _real_state_candidates(graph)
    if not real_states:
        return ""
    if not graph.initial_targets:
        incoming = Counter(target for _, _, target in graph.transitions)
        roots = sorted(state for state in real_states if incoming[state] == 0)
        return roots[0] if len(roots) == 1 else ""

    if len(graph.initial_targets) > 1:
        reachability = {
            state: len(_reachable_states(graph, state))
            for state in set(graph.initial_targets)
        }
        complete = [
            state for state, count in reachability.items() if count == len(graph.states)
        ]
        return complete[0] if len(complete) == 1 else ""
    return ""


def _deterministic_final_state(graph: DiagramGraph) -> str:
    real_states = _real_state_candidates(graph)
    if graph.final_states or not real_states:
        return ""
    outgoing = Counter(source for source, _, _ in graph.transitions)
    sinks = sorted(state for state in real_states if outgoing[state] == 0)
    if len(sinks) != 1:
        return ""
    if len(graph.initial_targets) == 1:
        reachable = _reachable_states(graph, graph.initial_targets[0])
        if sinks[0] not in reachable:
            return ""
    return sinks[0]


def _set_initial_transition(
    puml_text: str,
    state: str,
) -> tuple[str, dict[str, Any] | None, str]:
    graph = parse_plantuml(puml_text)
    reference, error = _resolve_state_reference(state, graph, puml_text)
    if error:
        return puml_text, None, error

    token_to_label, _ = _alias_maps(puml_text)
    output: list[str] = []
    removed: list[str] = []
    for raw_line in normalize_puml_text(puml_text).splitlines():
        signature = _transition_signature(raw_line, token_to_label)
        if signature and signature[0] == "[*]" and signature[2] != "[*]":
            removed.append(raw_line.strip())
            continue
        output.append(raw_line)
    patched = _insert_before_enduml("\n".join(output), [f"[*] --> {reference}"])
    return (
        patched,
        {
            "operation": "set_initial",
            "state": state,
            "removed_initial_transitions": removed,
            "added": f"[*] --> {reference}",
        },
        "",
    )


def _add_final_transition(
    puml_text: str,
    state: str,
) -> tuple[str, dict[str, Any] | None, str]:
    graph = parse_plantuml(puml_text)
    reference, error = _resolve_state_reference(state, graph, puml_text)
    if error:
        return puml_text, None, error
    if state in graph.final_states or sanitize_name(state) in graph.final_states:
        return puml_text, None, "final_transition_already_exists"
    line = f"{reference} --> [*]"
    return (
        _insert_before_enduml(puml_text, [line]),
        {"operation": "add_final_transition", "state": state, "added": line},
        "",
    )


def apply_deterministic_graph_repairs(
    puml_text: str,
    validation: ValidationResult,
) -> tuple[str, list[dict[str, Any]]]:
    candidate = normalize_puml_text(puml_text)
    edits: list[dict[str, Any]] = []
    issue_text = "\n".join(validation.errors + validation.warnings).lower()

    if "invalid [*]" in issue_text:
        candidate, applied = _remove_invalid_initial_final_lines(candidate)
        edits.extend(applied)

    if "duplicate_transitions" in issue_text:
        candidate, applied = _remove_duplicate_transition_lines(candidate)
        edits.extend(applied)

    graph = parse_plantuml(candidate)
    if (
        "missing_initial_state_transition" in issue_text
        or "multiple_initial_state_transitions" in issue_text
    ):
        initial_state = _deterministic_initial_state(graph)
        if initial_state:
            candidate, applied, error = _set_initial_transition(candidate, initial_state)
            if applied and not error:
                edits.append(applied)
                graph = parse_plantuml(candidate)

    if "missing_final_state_transition" in issue_text:
        final_state = _deterministic_final_state(graph)
        if final_state:
            candidate, applied, error = _add_final_transition(candidate, final_state)
            if applied and not error:
                edits.append(applied)

    return candidate, edits


def _extract_json_object(response: str) -> tuple[dict[str, Any] | None, str]:
    clean = re.sub(
        r"<think>.*?</think>",
        "",
        response.strip(),
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if clean.startswith("```") and clean.endswith("```"):
        lines = clean.splitlines()
        clean = "\n".join(lines[1:-1]).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end < start:
        return None, "response_does_not_contain_json_object"
    try:
        payload = json.loads(clean[start : end + 1])
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {exc.msg} at line {exc.lineno} column {exc.colno}"
    if not isinstance(payload, dict):
        return None, "json_root_must_be_an_object"
    return payload, ""


def parse_graph_edit_plan(
    response: str,
) -> tuple[list[dict[str, Any]], str, str]:
    payload, error = _extract_json_object(response)
    if error or payload is None:
        return [], "", error
    if set(payload) - {"edits", "reason"}:
        return [], "", "json_contains_unsupported_root_fields"
    edits = payload.get("edits")
    reason = payload.get("reason", "")
    if not isinstance(edits, list):
        return [], "", "edits_must_be_a_list"
    if not edits:
        return [], "", "edits_must_not_be_empty"
    if len(edits) > MAX_GRAPH_EDITS:
        return [], "", f"too_many_edits: maximum is {MAX_GRAPH_EDITS}"
    if not isinstance(reason, str):
        return [], "", "reason_must_be_a_string"

    schemas = {
        "add_transition": {"operation", "source", "target", "label"},
        "remove_transition": {"operation", "source", "target", "label"},
        "set_initial": {"operation", "state"},
        "add_final_transition": {"operation", "state"},
        "replace_transition_label": {
            "operation",
            "source",
            "target",
            "old_label",
            "new_label",
        },
    }
    normalized: list[dict[str, Any]] = []
    for index, edit in enumerate(edits, start=1):
        if not isinstance(edit, dict):
            return [], "", f"edit_{index}_must_be_an_object"
        operation = edit.get("operation")
        if operation not in schemas:
            return [], "", f"edit_{index}_has_unsupported_operation"
        allowed_fields = schemas[str(operation)]
        if set(edit) - allowed_fields:
            return [], "", f"edit_{index}_contains_unsupported_fields"
        required_fields = allowed_fields - {"label", "old_label"}
        missing = required_fields - set(edit)
        if missing:
            return [], "", f"edit_{index}_missing_fields: {', '.join(sorted(missing))}"
        if any(not isinstance(value, str) for key, value in edit.items() if key != "operation"):
            return [], "", f"edit_{index}_fields_must_be_strings"
        normalized.append({key: edit.get(key, "") for key in allowed_fields})
    return normalized, reason.strip(), ""


def _add_transition(
    puml_text: str,
    source: str,
    target: str,
    label: str,
) -> tuple[str, dict[str, Any] | None, str]:
    graph = parse_plantuml(puml_text)
    source_reference, error = _resolve_state_reference(source, graph, puml_text)
    if error:
        return puml_text, None, error
    target_reference, error = _resolve_state_reference(target, graph, puml_text)
    if error:
        return puml_text, None, error

    normalized_label = sanitize_event(label)
    signature = (
        _canonical_endpoint(source, _alias_maps(puml_text)[0]),
        normalized_label,
        _canonical_endpoint(target, _alias_maps(puml_text)[0]),
    )
    if signature in graph.transitions:
        return puml_text, None, "transition_already_exists"
    line = f"{source_reference} --> {target_reference}"
    if normalized_label:
        line += f" : {normalized_label}"
    return (
        _insert_before_enduml(puml_text, [line]),
        {
            "operation": "add_transition",
            "source": source,
            "target": target,
            "label": normalized_label,
            "added": line,
        },
        "",
    )


def _remove_transition(
    puml_text: str,
    source: str,
    target: str,
    label: str,
) -> tuple[str, dict[str, Any] | None, str]:
    graph = parse_plantuml(puml_text)
    source_reference, error = _resolve_state_reference(source, graph, puml_text)
    if error:
        return puml_text, None, error
    target_reference, error = _resolve_state_reference(target, graph, puml_text)
    if error:
        return puml_text, None, error
    del source_reference, target_reference

    token_to_label, _ = _alias_maps(puml_text)
    source_name = _canonical_endpoint(source, token_to_label)
    target_name = _canonical_endpoint(target, token_to_label)
    normalized_label = sanitize_event(label)
    output: list[str] = []
    removed = ""
    for raw_line in normalize_puml_text(puml_text).splitlines():
        signature = _transition_signature(raw_line, token_to_label)
        matches = (
            signature is not None
            and signature[0] == source_name
            and signature[2] == target_name
            and (not normalized_label or signature[1] == normalized_label)
        )
        if matches and not removed:
            removed = raw_line.strip()
            continue
        output.append(raw_line)
    if not removed:
        return puml_text, None, "transition_not_found"
    return (
        normalize_puml_text("\n".join(output)),
        {
            "operation": "remove_transition",
            "source": source,
            "target": target,
            "label": normalized_label,
            "removed": removed,
        },
        "",
    )


def _replace_transition_label(
    puml_text: str,
    source: str,
    target: str,
    old_label: str,
    new_label: str,
) -> tuple[str, dict[str, Any] | None, str]:
    graph = parse_plantuml(puml_text)
    _, error = _resolve_state_reference(source, graph, puml_text)
    if error:
        return puml_text, None, error
    _, error = _resolve_state_reference(target, graph, puml_text)
    if error:
        return puml_text, None, error

    token_to_label, _ = _alias_maps(puml_text)
    source_name = _canonical_endpoint(source, token_to_label)
    target_name = _canonical_endpoint(target, token_to_label)
    clean_old = sanitize_event(old_label)
    clean_new = sanitize_event(new_label)
    if not clean_new:
        return puml_text, None, "new_label_must_not_be_empty"

    output: list[str] = []
    replaced = ""
    replacement = ""
    for raw_line in normalize_puml_text(puml_text).splitlines():
        signature = _transition_signature(raw_line, token_to_label)
        matches = (
            signature is not None
            and signature[0] == source_name
            and signature[2] == target_name
            and signature[1] == clean_old
        )
        if matches and not replaced:
            match = TRANSITION_RE.match(raw_line.strip())
            assert match is not None
            replacement = (
                f"{match.group('src')} {match.group('arrow')} {match.group('dst')} : {clean_new}"
            )
            output.append(replacement)
            replaced = raw_line.strip()
            continue
        output.append(raw_line)
    if not replaced:
        return puml_text, None, "transition_with_old_label_not_found"
    return (
        normalize_puml_text("\n".join(output)),
        {
            "operation": "replace_transition_label",
            "source": source,
            "target": target,
            "old_label": clean_old,
            "new_label": clean_new,
            "removed": replaced,
            "added": replacement,
        },
        "",
    )


def apply_graph_edit_plan(
    puml_text: str,
    edits: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], str]:
    candidate = normalize_puml_text(puml_text)
    applied: list[dict[str, Any]] = []

    for index, edit in enumerate(edits, start=1):
        operation = str(edit["operation"])
        if operation == "add_transition":
            candidate, artifact, error = _add_transition(
                candidate,
                str(edit["source"]),
                str(edit["target"]),
                str(edit.get("label", "")),
            )
        elif operation == "remove_transition":
            candidate, artifact, error = _remove_transition(
                candidate,
                str(edit["source"]),
                str(edit["target"]),
                str(edit.get("label", "")),
            )
        elif operation == "set_initial":
            candidate, artifact, error = _set_initial_transition(
                candidate,
                str(edit["state"]),
            )
        elif operation == "add_final_transition":
            candidate, artifact, error = _add_final_transition(
                candidate,
                str(edit["state"]),
            )
        else:
            candidate, artifact, error = _replace_transition_label(
                candidate,
                str(edit["source"]),
                str(edit["target"]),
                str(edit.get("old_label", "")),
                str(edit["new_label"]),
            )
        if error or artifact is None:
            return puml_text, [], f"edit_{index}_{error or 'was_not_applied'}"
        applied.append(artifact)

    if candidate == normalize_puml_text(puml_text):
        return puml_text, [], "graph_edit_plan_did_not_change_candidate"
    return candidate, applied, ""


def graph_topology_summary(puml_text: str) -> dict[str, Any]:
    graph = parse_plantuml(puml_text)
    return {
        "states": sorted(graph.states),
        "initial_targets": list(graph.initial_targets),
        "final_states": sorted(graph.final_states),
        "transitions": [
            {"source": source, "target": target, "label": label}
            for source, label, target in graph.transitions
        ],
        "stereotypes": {
            state: sorted(values)
            for state, values in sorted(graph.stereotypes.items())
        },
    }
