from __future__ import annotations

import re
import statistics
from difflib import SequenceMatcher
from typing import Any, Iterable

from .models import DiagramGraph, ValidationResult

EVENT_TOKEN_RE = re.compile(r"[a-z0-9]+")
EVENT_STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "for",
    "and",
    "or",
    "of",
    "on",
    "in",
    "by",
    "with",
    "from",
    "user",
    "system",
}
EVENT_SYNONYMS = {
    "login": "authenticate",
    "signin": "authenticate",
    "sign": "authenticate",
    "authenticate": "authenticate",
    "authorization": "authorize",
    "authorise": "authorize",
    "authorize": "authorize",
    "approval": "approve",
    "approve": "approve",
    "accepted": "approve",
    "accept": "approve",
    "decline": "reject",
    "deny": "reject",
    "reject": "reject",
    "failed": "fail",
    "failure": "fail",
    "error": "fail",
    "logout": "logout",
    "signout": "logout",
    "cancelled": "cancel",
    "canceled": "cancel",
    "abort": "cancel",
    "cancel": "cancel",
    "pay": "payment",
    "paid": "payment",
    "purchase": "payment",
    "billing": "payment",
    "payment": "payment",
    "register": "register",
    "registration": "register",
    "access": "access",
    "view": "access",
    "open": "access",
    "select": "access",
    "choose": "access",
    "submit": "submit",
    "send": "submit",
    "retry": "retry",
    "reattempt": "retry",
    "timeout": "timeout",
}


def _to_set(items: Iterable[Any]) -> set[Any]:
    return set(items)


def prf(pred: set[Any], gold: set[Any]) -> tuple[float, float, float, int, int, int]:
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1, tp, fp, fn


def complexity_bucket(state_count: int) -> str:
    if state_count <= 6:
        return "simple"
    if state_count <= 14:
        return "medium"
    return "complex"


def _normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _state_key(state: str) -> str:
    return _normalize_token(state.strip())


def _transition_key_relaxed(src: str, dst: str) -> tuple[str, str]:
    return (_state_key(src), _state_key(dst))


def _canonical_event_tokens(event: str) -> tuple[str, ...]:
    raw_tokens = [m.group(0) for m in EVENT_TOKEN_RE.finditer(event.lower())]
    tokens: list[str] = []
    for tok in raw_tokens:
        if tok in EVENT_STOPWORDS:
            continue
        tokens.append(EVENT_SYNONYMS.get(tok, tok))
    return tuple(sorted(set(tokens)))


def _event_similarity(event_a: str, event_b: str) -> float:
    norm_a = " ".join(_canonical_event_tokens(event_a))
    norm_b = " ".join(_canonical_event_tokens(event_b))
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        # Keep unlabeled/labeled transitions partially compatible.
        return 0.70

    set_a = set(norm_a.split())
    set_b = set(norm_b.split())
    token_overlap = len(set_a & set_b) / len(set_a | set_b) if (set_a or set_b) else 1.0
    string_ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
    return 0.7 * token_overlap + 0.3 * string_ratio


def _semantic_transition_prf(
    pred_transitions: set[tuple[str, str, str]],
    gold_transitions: set[tuple[str, str, str]],
    threshold: float = 0.55,
) -> tuple[float, float, float, int, int, int, float]:
    pred_list = [
        (_state_key(src), _state_key(dst), event)
        for src, event, dst in sorted(pred_transitions, key=lambda t: (t[0], t[2], t[1]))
    ]
    gold_list = [
        (_state_key(src), _state_key(dst), event)
        for src, event, dst in sorted(gold_transitions, key=lambda t: (t[0], t[2], t[1]))
    ]

    candidates: list[tuple[float, int, int]] = []
    for i, (psrc, pdst, pevent) in enumerate(pred_list):
        for j, (gsrc, gdst, gevent) in enumerate(gold_list):
            if psrc != gsrc or pdst != gdst:
                continue
            sim = _event_similarity(pevent, gevent)
            if sim >= threshold:
                candidates.append((sim, i, j))

    candidates.sort(key=lambda x: x[0], reverse=True)
    used_pred: set[int] = set()
    used_gold: set[int] = set()
    matched_scores: list[float] = []
    for sim, i, j in candidates:
        if i in used_pred or j in used_gold:
            continue
        used_pred.add(i)
        used_gold.add(j)
        matched_scores.append(sim)

    tp = len(matched_scores)
    fp = len(pred_list) - tp
    fn = len(gold_list) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    mean_sim = sum(matched_scores) / len(matched_scores) if matched_scores else 0.0
    return precision, recall, f1, tp, fp, fn, mean_sim


def compute_metrics(
    pred_graph: DiagramGraph,
    pred_validation: ValidationResult,
    gold_graph: DiagramGraph,
) -> dict[str, Any]:
    pred_states = _to_set(pred_graph.states)
    gold_states = _to_set(gold_graph.states)
    pred_transitions = _to_set(pred_graph.transitions)
    gold_transitions = _to_set(gold_graph.transitions)

    s_p, s_r, s_f1, s_tp, s_fp, s_fn = prf(pred_states, gold_states)
    t_p, t_r, t_f1, t_tp, t_fp, t_fn = prf(pred_transitions, gold_transitions)

    unsupported_states = len(pred_states - gold_states)
    unsupported_transitions = len(pred_transitions - gold_transitions)
    hallucination_states_rate = unsupported_states / len(pred_states) if pred_states else 0.0
    hallucination_transitions_rate = (
        unsupported_transitions / len(pred_transitions) if pred_transitions else 0.0
    )
    missing_transition_rate = t_fn / len(gold_transitions) if gold_transitions else 0.0
    overall_f1 = (s_f1 + t_f1) / 2.0

    # Relaxed metrics: normalize state naming and ignore transition event text.
    pred_states_relaxed = {k for k in (_state_key(s) for s in pred_states) if k}
    gold_states_relaxed = {k for k in (_state_key(s) for s in gold_states) if k}
    pred_transitions_relaxed = {
        _transition_key_relaxed(src, dst) for (src, _, dst) in pred_transitions
    }
    gold_transitions_relaxed = {
        _transition_key_relaxed(src, dst) for (src, _, dst) in gold_transitions
    }

    rs_p, rs_r, rs_f1, rs_tp, rs_fp, rs_fn = prf(pred_states_relaxed, gold_states_relaxed)
    rt_p, rt_r, rt_f1, rt_tp, rt_fp, rt_fn = prf(pred_transitions_relaxed, gold_transitions_relaxed)

    unsupported_states_relaxed = len(pred_states_relaxed - gold_states_relaxed)
    unsupported_transitions_relaxed = len(pred_transitions_relaxed - gold_transitions_relaxed)
    hallucination_states_rate_relaxed = (
        unsupported_states_relaxed / len(pred_states_relaxed) if pred_states_relaxed else 0.0
    )
    hallucination_transitions_rate_relaxed = (
        unsupported_transitions_relaxed / len(pred_transitions_relaxed)
        if pred_transitions_relaxed
        else 0.0
    )
    missing_transition_rate_relaxed = (
        rt_fn / len(gold_transitions_relaxed) if gold_transitions_relaxed else 0.0
    )
    overall_f1_relaxed = (rs_f1 + rt_f1) / 2.0
    weighted_f1_relaxed_70_30 = (0.7 * rs_f1) + (0.3 * rt_f1)
    sem_p, sem_r, sem_f1, sem_tp, sem_fp, sem_fn, sem_mean = _semantic_transition_prf(
        pred_transitions=pred_transitions,
        gold_transitions=gold_transitions,
        threshold=0.55,
    )
    overall_f1_semantic = (rs_f1 + sem_f1) / 2.0
    weighted_f1_semantic_70_30 = (0.7 * rs_f1) + (0.3 * sem_f1)

    return {
        "state_precision": s_p,
        "state_recall": s_r,
        "state_f1": s_f1,
        "state_tp": s_tp,
        "state_fp": s_fp,
        "state_fn": s_fn,
        "transition_precision": t_p,
        "transition_recall": t_r,
        "transition_f1": t_f1,
        "transition_tp": t_tp,
        "transition_fp": t_fp,
        "transition_fn": t_fn,
        "state_precision_relaxed": rs_p,
        "state_recall_relaxed": rs_r,
        "state_f1_relaxed": rs_f1,
        "state_tp_relaxed": rs_tp,
        "state_fp_relaxed": rs_fp,
        "state_fn_relaxed": rs_fn,
        "transition_precision_relaxed": rt_p,
        "transition_recall_relaxed": rt_r,
        "transition_f1_relaxed": rt_f1,
        "transition_tp_relaxed": rt_tp,
        "transition_fp_relaxed": rt_fp,
        "transition_fn_relaxed": rt_fn,
        "transition_precision_semantic": sem_p,
        "transition_recall_semantic": sem_r,
        "transition_f1_semantic": sem_f1,
        "transition_tp_semantic": sem_tp,
        "transition_fp_semantic": sem_fp,
        "transition_fn_semantic": sem_fn,
        "transition_event_similarity_mean": sem_mean,
        "structural_valid": pred_validation.valid,
        "structural_errors": list(pred_validation.errors),
        "structural_warnings": list(pred_validation.warnings),
        "hallucination_state_rate": hallucination_states_rate,
        "hallucination_transition_rate": hallucination_transitions_rate,
        "hallucination_state_rate_relaxed": hallucination_states_rate_relaxed,
        "hallucination_transition_rate_relaxed": hallucination_transitions_rate_relaxed,
        "missing_transition_rate": missing_transition_rate,
        "missing_transition_rate_relaxed": missing_transition_rate_relaxed,
        "overall_f1": overall_f1,
        "overall_f1_relaxed": overall_f1_relaxed,
        "weighted_f1_relaxed_70_30": weighted_f1_relaxed_70_30,
        "overall_f1_semantic": overall_f1_semantic,
        "weighted_f1_semantic_70_30": weighted_f1_semantic_70_30,
    }


def summarize_metrics(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_config: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_config.setdefault(row["run_id"], []).append(row)

    summary_config: list[dict[str, Any]] = []
    summary_complexity: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []

    for run_id, group in sorted(by_config.items()):

        def mean(key: str) -> float:
            vals = [float(item.get(key, 0.0)) for item in group]
            return sum(vals) / len(vals) if vals else 0.0

        pass_rate = sum(1 for item in group if item.get("structural_valid")) / len(group)
        summary_config.append(
            {
                "run_id": run_id,
                "samples": len(group),
                "state_f1_mean": mean("state_f1"),
                "transition_f1_mean": mean("transition_f1"),
                "transition_f1_semantic_mean": mean("transition_f1_semantic"),
                "overall_f1_mean": mean("overall_f1"),
                "state_f1_relaxed_mean": mean("state_f1_relaxed"),
                "transition_f1_relaxed_mean": mean("transition_f1_relaxed"),
                "overall_f1_relaxed_mean": mean("overall_f1_relaxed"),
                "weighted_f1_relaxed_70_30_mean": mean("weighted_f1_relaxed_70_30"),
                "overall_f1_semantic_mean": mean("overall_f1_semantic"),
                "weighted_f1_semantic_70_30_mean": mean("weighted_f1_semantic_70_30"),
                "structural_valid_rate": pass_rate,
                "hallucination_state_rate_mean": mean("hallucination_state_rate"),
                "hallucination_transition_rate_mean": mean("hallucination_transition_rate"),
                "hallucination_state_rate_relaxed_mean": mean("hallucination_state_rate_relaxed"),
                "hallucination_transition_rate_relaxed_mean": mean(
                    "hallucination_transition_rate_relaxed"
                ),
                "missing_transition_rate_mean": mean("missing_transition_rate"),
                "missing_transition_rate_relaxed_mean": mean("missing_transition_rate_relaxed"),
            }
        )

        by_complexity: dict[str, list[dict[str, Any]]] = {}
        for item in group:
            by_complexity.setdefault(item["complexity"], []).append(item)
        for complexity, cgroup in sorted(by_complexity.items()):
            summary_complexity.append(
                {
                    "run_id": run_id,
                    "complexity": complexity,
                    "samples": len(cgroup),
                    "state_f1_mean": sum(float(x["state_f1"]) for x in cgroup) / len(cgroup),
                    "transition_f1_mean": sum(float(x["transition_f1"]) for x in cgroup) / len(cgroup),
                    "transition_f1_semantic_mean": sum(
                        float(x.get("transition_f1_semantic", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "overall_f1_mean": sum(float(x["overall_f1"]) for x in cgroup) / len(cgroup),
                    "state_f1_relaxed_mean": sum(
                        float(x.get("state_f1_relaxed", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "transition_f1_relaxed_mean": sum(
                        float(x.get("transition_f1_relaxed", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "overall_f1_relaxed_mean": sum(
                        float(x.get("overall_f1_relaxed", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "weighted_f1_relaxed_70_30_mean": sum(
                        float(x.get("weighted_f1_relaxed_70_30", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "overall_f1_semantic_mean": sum(
                        float(x.get("overall_f1_semantic", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "weighted_f1_semantic_70_30_mean": sum(
                        float(x.get("weighted_f1_semantic_70_30", 0.0)) for x in cgroup
                    )
                    / len(cgroup),
                    "structural_valid_rate": sum(1 for x in cgroup if x["structural_valid"]) / len(cgroup),
                }
            )

        # Stability: std-dev of overall_f1 across repeated runs for each case, then averaged.
        by_case: dict[str, list[dict[str, Any]]] = {}
        for item in group:
            by_case.setdefault(item["case_id"], []).append(item)
        stds: list[float] = []
        stds_relaxed: list[float] = []
        stds_semantic: list[float] = []
        for case_id, crows in sorted(by_case.items()):
            vals = [float(x["overall_f1"]) for x in sorted(crows, key=lambda r: int(r["run_index"]))]
            std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            stds.append(std)
            vals_relaxed = [
                float(x.get("overall_f1_relaxed", 0.0))
                for x in sorted(crows, key=lambda r: int(r["run_index"]))
            ]
            std_relaxed = statistics.pstdev(vals_relaxed) if len(vals_relaxed) > 1 else 0.0
            stds_relaxed.append(std_relaxed)
            vals_semantic = [
                float(x.get("overall_f1_semantic", 0.0))
                for x in sorted(crows, key=lambda r: int(r["run_index"]))
            ]
            std_semantic = statistics.pstdev(vals_semantic) if len(vals_semantic) > 1 else 0.0
            stds_semantic.append(std_semantic)
            stability_rows.append(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "runs": len(vals),
                    "overall_f1_stddev": std,
                    "overall_f1_relaxed_stddev": std_relaxed,
                    "overall_f1_semantic_stddev": std_semantic,
                }
            )
        config_stability = sum(stds) / len(stds) if stds else 0.0
        config_stability_relaxed = sum(stds_relaxed) / len(stds_relaxed) if stds_relaxed else 0.0
        config_stability_semantic = sum(stds_semantic) / len(stds_semantic) if stds_semantic else 0.0
        for rec in summary_config:
            if rec["run_id"] == run_id:
                rec["stability_overall_f1_stddev_mean"] = config_stability
                rec["stability_overall_f1_relaxed_stddev_mean"] = config_stability_relaxed
                rec["stability_overall_f1_semantic_stddev_mean"] = config_stability_semantic
                break

    return summary_config, summary_complexity, stability_rows
