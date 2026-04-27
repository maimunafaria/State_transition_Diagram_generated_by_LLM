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
from .prompting import resolve_rag_context

GOLD_FREE_SCORE_WEIGHTS = {
    "structural_score": 0.35,
    "requirement_coverage_score": 0.30,
    "consensus_score": 0.20,
    "diagram_quality_score": 0.15,
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_REQUIREMENT_LINE_RE = re.compile(r"^\s*(?:\d+[\).]|[-*])\s+(.*\S)\s*$")
_STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "allow",
    "allows",
    "an",
    "and",
    "are",
    "as",
    "at",
    "available",
    "be",
    "between",
    "by",
    "can",
    "complete",
    "completed",
    "current",
    "different",
    "do",
    "does",
    "during",
    "each",
    "enable",
    "enables",
    "end",
    "ensure",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "process",
    "provide",
    "provides",
    "related",
    "shall",
    "should",
    "support",
    "supports",
    "system",
    "that",
    "the",
    "their",
    "then",
    "to",
    "use",
    "user",
    "users",
    "when",
    "where",
    "whether",
    "with",
}
_TOKEN_SYNONYMS = {
    "authenticate": "login",
    "authenticated": "login",
    "authentication": "login",
    "signin": "login",
    "sign": "login",
    "login": "login",
    "logged": "login",
    "logout": "logout",
    "signout": "logout",
    "register": "registration",
    "registered": "registration",
    "registration": "registration",
    "validate": "validation",
    "validated": "validation",
    "validating": "validation",
    "validation": "validation",
    "verify": "validation",
    "verified": "validation",
    "verification": "validation",
    "pay": "payment",
    "paid": "payment",
    "payment": "payment",
    "payments": "payment",
    "purchase": "purchase",
    "purchases": "purchase",
    "buy": "purchase",
    "choose": "select",
    "chosen": "select",
    "select": "select",
    "selected": "select",
    "view": "view",
    "display": "view",
    "show": "view",
    "shown": "view",
    "read": "view",
    "finish": "finish",
    "finished": "finish",
    "failure": "fail",
    "failed": "fail",
    "fails": "fail",
    "invalid": "fail",
    "cancel": "cancel",
    "cancelled": "cancel",
    "canceled": "cancel",
}


def safe_strategy_tag(strategy: str) -> str:
    return strategy.strip().lower().replace(" ", "_")


def _canonical_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for match in _TOKEN_RE.finditer(text.lower()):
        token = match.group(0)
        if token in _STOPWORDS or len(token) < 2:
            continue
        tokens.add(_TOKEN_SYNONYMS.get(token, token))
    return tokens


def _extract_requirement_items(requirement: str) -> list[tuple[str, set[str]]]:
    items: list[tuple[str, set[str]]] = []
    fallback_parts: list[str] = []
    for line in requirement.splitlines():
        match = _REQUIREMENT_LINE_RE.match(line)
        if match:
            text = match.group(1).strip()
            tokens = _canonical_tokens(text)
            if tokens:
                items.append((text, tokens))
        elif line.strip():
            fallback_parts.append(line.strip())

    if items:
        return items

    # Non-numbered requirements still get coverage scoring from sentence-like chunks.
    chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[.!?])\s+|\n+", " ".join(fallback_parts))
        if chunk.strip()
    ]
    for chunk in chunks:
        tokens = _canonical_tokens(chunk)
        if tokens:
            items.append((chunk, tokens))
    return items


def _candidate_text_tokens(graph: DiagramGraph) -> set[str]:
    parts: list[str] = []
    parts.extend(graph.states)
    parts.extend(graph.final_states)
    for src, event, dst in graph.transitions:
        parts.extend([src, event, dst])
    return _canonical_tokens(" ".join(parts))


def _normalized_state_keys(graph: DiagramGraph) -> set[str]:
    keys: set[str] = set()
    for state in graph.states:
        tokens = _canonical_tokens(state)
        if tokens:
            keys.add(" ".join(sorted(tokens)))
    return keys


def _normalized_transition_keys(graph: DiagramGraph) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for src, event, dst in graph.transitions:
        src_key = " ".join(sorted(_canonical_tokens(src)))
        dst_key = " ".join(sorted(_canonical_tokens(dst)))
        event_key = " ".join(sorted(_canonical_tokens(event)))
        if src_key and dst_key:
            keys.add((src_key, event_key, dst_key))
    return keys


def _jaccard(left: set[Any], right: set[Any]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _candidate_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_graph: DiagramGraph = left["graph"]
    right_graph: DiagramGraph = right["graph"]
    state_similarity = _jaccard(_normalized_state_keys(left_graph), _normalized_state_keys(right_graph))
    transition_similarity = _jaccard(
        _normalized_transition_keys(left_graph),
        _normalized_transition_keys(right_graph),
    )
    return (0.60 * state_similarity) + (0.40 * transition_similarity)


def _structural_score(graph: DiagramGraph, validation: ValidationResult) -> tuple[float, dict[str, Any]]:
    score = 1.0
    penalties: dict[str, float] = {}

    if not validation.valid:
        penalties["invalid_plantuml"] = 0.50
    if not validation.initial_state:
        penalties["missing_or_ambiguous_initial"] = 0.15
    if not graph.final_states:
        penalties["missing_final_state"] = 0.15
    if validation.state_count == 0:
        penalties["no_states"] = 0.20
    if validation.transition_count == 0:
        penalties["no_transitions"] = 0.20

    unreachable_rate = len(validation.unreachable_states) / max(1, validation.state_count)
    if unreachable_rate:
        penalties["unreachable_state_rate"] = min(0.25, 0.25 * unreachable_rate)

    duplicate_rate = validation.duplicate_transition_count / max(1, validation.transition_count)
    if duplicate_rate:
        penalties["duplicate_transition_rate"] = min(0.10, 0.10 * duplicate_rate)

    warning_text = "\n".join(validation.warnings).lower()
    warning_penalties = {
        "orphan_states_detected": 0.08,
        "choice_node_without_outgoing_transitions": 0.08,
        "choice_node_without_guarded_outgoing_transitions": 0.04,
        "fork_without_multiple_outgoing_branches": 0.04,
        "join_without_multiple_incoming_branches": 0.04,
        "history_state_used_without_composite_state": 0.04,
    }
    for marker, penalty in warning_penalties.items():
        if marker in warning_text:
            penalties[marker] = penalty

    score -= sum(penalties.values())
    score = max(0.0, min(1.0, score))
    return score, {
        "penalties": penalties,
        "unreachable_rate": unreachable_rate,
        "duplicate_transition_rate": duplicate_rate,
    }


def _requirement_coverage_score(
    requirement: str,
    graph: DiagramGraph,
) -> tuple[float, dict[str, Any]]:
    requirement_items = _extract_requirement_items(requirement)
    candidate_tokens = _candidate_text_tokens(graph)
    if not requirement_items:
        return 0.0, {
            "covered_count": 0,
            "total_count": 0,
            "covered_requirements": [],
            "missing_requirements": [],
            "candidate_tokens": sorted(candidate_tokens)[:80],
        }

    covered: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    partial_scores: list[float] = []
    for idx, (text, req_tokens) in enumerate(requirement_items, start=1):
        overlap = sorted(req_tokens & candidate_tokens)
        overlap_ratio = len(overlap) / max(1, len(req_tokens))
        # A requirement with two meaningful concepts should not require every word
        # to appear verbatim; normalized concept overlap is enough for this selector.
        required_hits = 1 if len(req_tokens) <= 2 else 2
        is_covered = len(overlap) >= required_hits or overlap_ratio >= 0.35
        partial_score = min(1.0, overlap_ratio / 0.45)
        partial_scores.append(partial_score)
        payload = {
            "index": idx,
            "text": text,
            "matched_tokens": overlap,
            "coverage": overlap_ratio,
        }
        if is_covered:
            covered.append(payload)
        else:
            missing.append(payload)

    binary_coverage = len(covered) / len(requirement_items)
    mean_partial = sum(partial_scores) / len(partial_scores)
    score = (0.65 * binary_coverage) + (0.35 * mean_partial)
    return max(0.0, min(1.0, score)), {
        "covered_count": len(covered),
        "total_count": len(requirement_items),
        "covered_requirements": covered,
        "missing_requirements": missing,
        "candidate_tokens": sorted(candidate_tokens)[:80],
    }


def _consensus_scores(candidates: list[dict[str, Any]]) -> dict[int, float]:
    if len(candidates) <= 1:
        return {id(cand): 1.0 for cand in candidates}

    scores: dict[int, float] = {}
    for candidate in candidates:
        similarities = [
            _candidate_similarity(candidate, other)
            for other in candidates
            if other is not candidate
        ]
        scores[id(candidate)] = sum(similarities) / len(similarities) if similarities else 0.0
    return scores


def _diagram_quality_score(graph: DiagramGraph, validation: ValidationResult) -> tuple[float, dict[str, Any]]:
    state_count = validation.state_count
    transition_count = validation.transition_count
    score = 1.0
    penalties: dict[str, float] = {}

    if state_count < 3:
        penalties["too_few_states"] = 0.25
    elif state_count > 30:
        penalties["too_many_states"] = min(0.25, (state_count - 30) / 80)

    if transition_count < max(1, state_count - 1):
        penalties["sparse_transitions"] = min(
            0.20,
            (max(1, state_count - 1) - transition_count) / max(5, state_count) * 0.20,
        )
    elif state_count and transition_count > state_count * 3:
        penalties["overdense_transitions"] = min(0.15, (transition_count - state_count * 3) / 100)

    unlabeled = sum(1 for _, event, _ in graph.transitions if not event.strip())
    unlabeled_rate = unlabeled / max(1, len(graph.transitions))
    if unlabeled_rate > 0.60:
        penalties["high_unlabeled_transition_rate"] = min(0.15, (unlabeled_rate - 0.60) * 0.30)

    if not validation.initial_state:
        penalties["no_single_initial"] = 0.10
    if not graph.final_states:
        penalties["no_final"] = 0.10

    warning_text = "\n".join(validation.warnings).lower()
    if "orphan_states_detected" in warning_text:
        penalties["orphan_states"] = 0.08
    if "choice_node_without_outgoing_transitions" in warning_text:
        penalties["broken_choice_node"] = 0.08

    score -= sum(penalties.values())
    score = max(0.0, min(1.0, score))
    return score, {
        "penalties": penalties,
        "state_count": state_count,
        "transition_count": transition_count,
        "unlabeled_transition_rate": unlabeled_rate,
    }


def score_gold_free_candidates(
    candidates: list[dict[str, Any]],
    requirement: str,
) -> list[dict[str, Any]]:
    consensus_by_id = _consensus_scores(candidates)
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        graph: DiagramGraph = candidate["graph"]
        validation: ValidationResult = candidate["validation"]
        structural, structural_meta = _structural_score(graph, validation)
        coverage, coverage_meta = _requirement_coverage_score(requirement, graph)
        consensus = consensus_by_id.get(id(candidate), 0.0)
        quality, quality_meta = _diagram_quality_score(graph, validation)
        final_score = (
            GOLD_FREE_SCORE_WEIGHTS["structural_score"] * structural
            + GOLD_FREE_SCORE_WEIGHTS["requirement_coverage_score"] * coverage
            + GOLD_FREE_SCORE_WEIGHTS["consensus_score"] * consensus
            + GOLD_FREE_SCORE_WEIGHTS["diagram_quality_score"] * quality
        )
        scored_candidate = dict(candidate)
        scored_candidate["gold_free_scores"] = {
            "final_score": final_score,
            "structural_score": structural,
            "requirement_coverage_score": coverage,
            "consensus_score": consensus,
            "diagram_quality_score": quality,
            "weights": dict(GOLD_FREE_SCORE_WEIGHTS),
            "structural": structural_meta,
            "requirement_coverage": coverage_meta,
            "diagram_quality": quality_meta,
        }
        scored.append(scored_candidate)

    scored.sort(
        key=lambda cand: (
            float(cand["gold_free_scores"]["final_score"]),
            float(cand["gold_free_scores"]["requirement_coverage_score"]),
            float(cand["gold_free_scores"]["structural_score"]),
            float(cand["gold_free_scores"]["diagram_quality_score"]),
        ),
        reverse=True,
    )
    return scored


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


def _iter_final_run_puml_paths(case_dir: Path) -> list[Path]:
    # Keep only final run files, e.g. run_01.puml. Intermediate repair files
    # such as run_01.initial.puml and run_01.repair_02.puml are audit artifacts.
    return [
        path
        for path in sorted(case_dir.glob("run_*.puml"))
        if re.fullmatch(r"run_\d+\.puml", path.name)
    ]


def _model_key_from_run_id(run_id: str) -> str:
    lowered = run_id.lower()
    if "qwen" in lowered:
        return "qwen"
    if "llama" in lowered:
        return "llama"
    if "deepseek" in lowered:
        return "deepseek"
    if "gpt" in lowered:
        return "gpt"
    return run_id


def _load_candidate_from_puml(
    puml_path: Path,
    run_id: str,
    model_key: str,
) -> dict[str, Any] | None:
    meta_path = puml_path.with_name(puml_path.name.replace(".puml", ".meta.json"))
    if meta_path.exists():
        try:
            meta = json.loads(read_text(meta_path))
        except json.JSONDecodeError:
            return None
        if str(meta.get("status", "")) != "ok":
            return None
    puml_text = normalize_puml_text(read_text(puml_path))
    graph, validation = parse_and_validate_puml_text(puml_text)
    return {
        "model": model_key,
        "run_id": run_id,
        "puml_path": str(puml_path),
        "puml_text": puml_text,
        "graph": graph,
        "validation": validation,
    }


def collect_ensemble_candidates(
    results_root: Path,
    case_id: str,
    strategy: str,
    qwen_prefix: str,
    llama_prefix: str,
    deepseek_prefix: str = "",
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    source_models = [("qwen", qwen_prefix), ("llama", llama_prefix)]
    if deepseek_prefix:
        source_models.append(("deepseek", deepseek_prefix))
    for model_key, prefix in source_models:
        run_id = f"{prefix}__{strategy}"
        case_dir = results_root / "runs" / run_id / case_id
        if not case_dir.exists():
            continue
        for puml_path in _iter_final_run_puml_paths(case_dir):
            candidate = _load_candidate_from_puml(puml_path, run_id=run_id, model_key=model_key)
            if candidate:
                candidates.append(candidate)
    return candidates


def collect_candidates_from_run_ids(
    results_root: Path,
    case_id: str,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for run_id in run_ids:
        case_dir = results_root / "runs" / run_id / case_id
        if not case_dir.exists():
            continue
        model_key = _model_key_from_run_id(run_id)
        for puml_path in _iter_final_run_puml_paths(case_dir):
            candidate = _load_candidate_from_puml(puml_path, run_id=run_id, model_key=model_key)
            if candidate:
                candidates.append(candidate)
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
    requirement: str = "",
    selection_method: str = "gold_free",
) -> list[dict[str, Any]]:
    if max_candidates <= 0:
        return []

    if selection_method == "gold_free" and requirement.strip():
        ranked = score_gold_free_candidates(candidates, requirement=requirement)
        chosen: list[dict[str, Any]] = []
        seen_puml: set[str] = set()
        remaining = list(ranked)
        while remaining and len(chosen) < max_candidates:
            best_index = 0
            best_score = float("-inf")
            for idx, cand in enumerate(remaining):
                puml_text = normalize_puml_text(str(cand.get("puml_text", "")))
                if puml_text in seen_puml:
                    continue
                base_score = float(cand["gold_free_scores"]["final_score"])
                diversity_penalty = (
                    max(_candidate_similarity(cand, selected) for selected in chosen) * 0.20
                    if chosen
                    else 0.0
                )
                model_bonus = (
                    0.03
                    if chosen and str(cand.get("model", "")) not in {str(c.get("model", "")) for c in chosen}
                    else 0.0
                )
                adjusted_score = base_score - diversity_penalty + model_bonus
                if adjusted_score > best_score:
                    best_score = adjusted_score
                    best_index = idx

            cand = remaining.pop(best_index)
            puml_text = normalize_puml_text(str(cand.get("puml_text", "")))
            if puml_text in seen_puml:
                continue
            seen_puml.add(puml_text)
            selected = dict(cand)
            selected["gold_free_scores"] = dict(cand["gold_free_scores"])
            selected["gold_free_scores"]["selection_adjusted_score"] = best_score
            selected["gold_free_scores"]["selection_rank"] = len(chosen) + 1
            chosen.append(selected)

        return chosen

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
        score_details = cand.get("gold_free_scores") or {}
        score_suffix = ""
        if score_details:
            score_suffix = (
                f" | gold_free_score={float(score_details.get('final_score', 0.0)):.3f}"
                f" | coverage={float(score_details.get('requirement_coverage_score', 0.0)):.3f}"
                f" | consensus={float(score_details.get('consensus_score', 0.0)):.3f}"
                f" | quality={float(score_details.get('diagram_quality_score', 0.0)):.3f}"
            )
        details = (
            f"Candidate {idx} | model={cand.get('model')} | run_id={cand.get('run_id')} | "
            f"valid={validation.valid} | errors={len(validation.errors)} | "
            f"states={len(graph.states)} | transitions={len(set(graph.transitions))}"
            f"{score_suffix}"
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
    rag_mode: str = "lexical",
    rag_db_dir: Path | None = None,
    rag_collection_name: str = "uml_docs",
) -> tuple[str, dict[str, Any]]:
    if not candidates:
        raise ValueError("No candidates available for stacked ensemble")

    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    selected = select_stacking_candidates(
        candidates,
        max_candidates=max_candidates,
        requirement=requirement,
        selection_method="gold_free",
    )
    if not selected:
        raise ValueError("No candidates selected for stacked ensemble")

    rag_context = ""
    rag_trace: list[dict[str, Any]] = []
    if top_k_rag > 0 and (rag_mode == "vector" or rag_docs):
        rag_context, rag_trace = resolve_rag_context(
            query=requirement,
            docs=rag_docs,
            top_k=top_k_rag,
            max_chars_per_doc=rag_max_chars_per_doc,
            query_domain_hints=rag_domain_hints,
            rag_mode=rag_mode,
            rag_db_dir=rag_db_dir,
            rag_collection_name=rag_collection_name,
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
        "prompt": prompt,
        "candidate_count_total": len(candidates),
        "candidate_count_used": len(selected),
        "rag_enabled": bool(top_k_rag > 0 and (rag_mode == "vector" or rag_docs)),
        "rag_mode": rag_mode,
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
                "gold_free_scores": c.get("gold_free_scores", {}),
            }
            for c in selected
        ],
        "prompt_length_chars": len(prompt),
    }
    return final_puml, stack_meta
