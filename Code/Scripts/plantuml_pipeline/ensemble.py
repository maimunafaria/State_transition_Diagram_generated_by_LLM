from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .io_utils import read_text
from .model_client import call_model
from .models import Case, DiagramGraph, ValidationResult
from .parser import normalize_puml_text, parse_and_validate_puml_text
from .prompting import retrieve_rag_context


def safe_strategy_tag(strategy: str) -> str:
    return strategy.strip().lower().replace(" ", "_")


def _puml_state_token(state: str) -> str:
    state = state.strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-\.]*", state):
        return state
    escaped = state.replace('"', '\\"')
    return f'"{escaped}"'


def build_puml_from_graph(
    states: set[str],
    transitions: set[tuple[str, str, str]],
    initial_state: str | None,
    final_states: set[str],
) -> str:
    lines: list[str] = ["@startuml"]
    if initial_state:
        lines.append(f"[*] --> {_puml_state_token(initial_state)}")
        lines.append("")

    for src, event, dst in sorted(transitions, key=lambda t: (t[0], t[1], t[2])):
        src_tok = _puml_state_token(src)
        dst_tok = _puml_state_token(dst)
        if event:
            lines.append(f"{src_tok} --> {dst_tok} : {event}")
        else:
            lines.append(f"{src_tok} --> {dst_tok}")

    if final_states:
        if transitions:
            lines.append("")
        for state in sorted(final_states):
            lines.append(f"{_puml_state_token(state)} --> [*]")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def collect_ensemble_candidates(
    results_root: Path,
    case_id: str,
    strategy: str,
    qwen_prefix: str,
    llama_prefix: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    source_models = [("qwen", qwen_prefix), ("llama", llama_prefix)]
    for model_key, prefix in source_models:
        run_id = f"{prefix}__{strategy}"
        case_dir = results_root / "runs" / run_id / case_id
        if not case_dir.exists():
            continue
        for puml_path in sorted(case_dir.glob("run_*.puml")):
            meta_path = case_dir / puml_path.name.replace(".puml", ".meta.json")
            if meta_path.exists():
                try:
                    meta = json.loads(read_text(meta_path))
                except json.JSONDecodeError:
                    continue
                if str(meta.get("status", "")) != "ok":
                    continue
            puml_text = normalize_puml_text(read_text(puml_path))
            graph, validation = parse_and_validate_puml_text(puml_text)
            candidates.append(
                {
                    "model": model_key,
                    "run_id": run_id,
                    "puml_path": str(puml_path),
                    "puml_text": puml_text,
                    "graph": graph,
                    "validation": validation,
                }
            )
    return candidates


def majority_vote_graph(
    candidates: list[dict[str, Any]],
    min_votes_override: int = 0,
) -> tuple[set[str], set[tuple[str, str, str]], str | None, set[str], dict[str, Any]]:
    candidate_count = len(candidates)
    threshold = min_votes_override if min_votes_override > 0 else (candidate_count // 2 + 1)

    state_counter: Counter[str] = Counter()
    transition_counter: Counter[tuple[str, str, str]] = Counter()
    initial_counter: Counter[str] = Counter()
    final_counter: Counter[str] = Counter()

    for cand in candidates:
        graph: DiagramGraph = cand["graph"]
        validation: ValidationResult = cand["validation"]
        state_counter.update(set(graph.states))
        transition_counter.update(set(graph.transitions))
        final_counter.update(set(graph.final_states))
        if validation.initial_state:
            initial_counter.update([validation.initial_state])

    states = {s for s, c in state_counter.items() if c >= threshold}
    transitions = {t for t, c in transition_counter.items() if c >= threshold}
    final_states = {s for s, c in final_counter.items() if c >= threshold}

    initial_state: str | None = None
    if initial_counter:
        max_votes = max(initial_counter.values())
        initial_candidates = sorted([s for s, c in initial_counter.items() if c == max_votes])
        initial_state = initial_candidates[0]

    if initial_state:
        states.add(initial_state)
    for src, _, dst in transitions:
        states.add(src)
        states.add(dst)
    final_states = {s for s in final_states if s in states}

    vote_meta = {
        "candidate_count": candidate_count,
        "vote_threshold": threshold,
        "initial_votes": dict(initial_counter),
        "top_state_votes": sorted(
            [{"state": s, "votes": c} for s, c in state_counter.items()],
            key=lambda x: (-x["votes"], x["state"]),
        )[:20],
        "top_transition_votes": sorted(
            [
                {"transition": {"from": t[0], "event": t[1], "to": t[2]}, "votes": c}
                for t, c in transition_counter.items()
            ],
            key=lambda x: (
                -x["votes"],
                x["transition"]["from"],
                x["transition"]["event"],
                x["transition"]["to"],
            ),
        )[:30],
    }
    return states, transitions, initial_state, final_states, vote_meta


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    validation: ValidationResult = candidate["validation"]
    graph: DiagramGraph = candidate["graph"]
    return (
        1 if validation.valid else 0,
        -len(validation.errors),
        len(set(graph.transitions)),
        len(graph.states),
    )


def select_stacking_candidates(
    candidates: list[dict[str, Any]],
    max_candidates: int,
) -> list[dict[str, Any]]:
    if max_candidates <= 0:
        return []
    chosen: list[dict[str, Any]] = []
    seen_puml: set[str] = set()
    for cand in sorted(candidates, key=_candidate_sort_key, reverse=True):
        puml_text = normalize_puml_text(str(cand.get("puml_text", "")))
        if puml_text in seen_puml:
            continue
        seen_puml.add(puml_text)
        chosen.append(cand)
        if len(chosen) >= max_candidates:
            break
    return chosen


def _clip_candidate_puml(puml_text: str, max_chars: int) -> str:
    text = normalize_puml_text(puml_text).strip()
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 32].rstrip()
    if not clipped.endswith("@enduml"):
        clipped += "\n@enduml"
    return clipped


def build_stacked_ensemble_prompt(
    requirement: str,
    candidates: list[dict[str, Any]],
    rag_context: str = "",
) -> str:
    parts: list[str] = [
        "You are an LLM meta-ensemble for UML state machine generation.",
        "Goal: produce ONE final PlantUML state machine from multiple candidate diagrams.",
        "Hard rules:",
        "- Output ONLY PlantUML code.",
        "- Start with @startuml and end with @enduml.",
        "- Include exactly one initial transition [*] --> state.",
        "- Keep transitions semantically grounded in the requirement.",
        "- Avoid unsupported hallucinated states/transitions.",
        "- Prefer structurally valid candidates when conflicts exist.",
        "",
        "Requirement:",
        requirement.strip(),
        "",
        "Candidate diagrams:",
    ]

    for idx, cand in enumerate(candidates, start=1):
        graph: DiagramGraph = cand["graph"]
        validation: ValidationResult = cand["validation"]
        puml_text = _clip_candidate_puml(str(cand.get("puml_text", "")), max_chars=2200)
        details = (
            f"Candidate {idx} | model={cand.get('model')} | run_id={cand.get('run_id')} | "
            f"valid={validation.valid} | errors={len(validation.errors)} | "
            f"states={len(graph.states)} | transitions={len(set(graph.transitions))}"
        )
        parts.extend([details, puml_text, ""])

    if rag_context.strip():
        parts.extend(
            [
                "Domain/reference context (support evidence):",
                rag_context.strip(),
                "",
            ]
        )

    parts.append("Return only the final PlantUML.")
    return "\n".join(parts).strip() + "\n"


def run_stacked_ensemble(
    case: Case,
    candidates: list[dict[str, Any]],
    model_name: str,
    requirement_source: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
    max_candidates: int,
    rag_docs: list[tuple[str, str, set[str]]] | None = None,
    top_k_rag: int = 0,
    rag_max_chars_per_doc: int = 1200,
    rag_domain_hints: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    if not candidates:
        raise ValueError("No candidates available for stacked ensemble")

    selected = select_stacking_candidates(candidates, max_candidates=max_candidates)
    if not selected:
        raise ValueError("No candidates selected for stacked ensemble")

    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    rag_context = ""
    rag_trace: list[dict[str, Any]] = []
    if rag_docs and top_k_rag > 0:
        rag_context, rag_trace = retrieve_rag_context(
            query=requirement,
            docs=rag_docs,
            top_k=top_k_rag,
            max_chars_per_doc=rag_max_chars_per_doc,
            query_domain_hints=rag_domain_hints,
        )

    prompt = build_stacked_ensemble_prompt(
        requirement=requirement,
        candidates=selected,
        rag_context=rag_context,
    )
    generated = call_model(
        model_name=model_name,
        prompt=prompt,
        ollama_host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    final_puml = normalize_puml_text(generated)
    stack_meta = {
        "stack_model": model_name,
        "candidate_count_total": len(candidates),
        "candidate_count_used": len(selected),
        "rag_enabled": bool(rag_docs and top_k_rag > 0),
        "rag_top_k": top_k_rag,
        "rag_max_chars_per_doc": rag_max_chars_per_doc,
        "rag_domain_hints": sorted(rag_domain_hints or set()),
        "rag_retrieved_docs": rag_trace,
        "candidate_sources": [
            {
                "model": str(c.get("model", "")),
                "run_id": str(c.get("run_id", "")),
                "puml_path": str(c.get("puml_path", "")),
                "structural_valid": bool(getattr(c.get("validation"), "valid", False)),
            }
            for c in selected
        ],
        "prompt_length_chars": len(prompt),
    }
    return final_puml, stack_meta
