#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
from sentence_transformers import SentenceTransformer

from plantuml_pipeline.dataset import load_cases
from plantuml_pipeline.parser import normalize_puml_text, parse_and_validate_puml_text


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.80
SYNONYM_CANONICAL_FORMS = {
    "accept": "approval",
    "accepted": "approval",
    "account creation": "registration",
    "application form": "application",
    "approve": "approval",
    "approved": "approval",
    "cash payment": "cash",
    "certificate application": "apply certificate",
    "check location": "location",
    "checkout": "payment",
    "confirm payment": "payment",
    "create account": "registration",
    "decline": "rejection",
    "declined": "rejection",
    "display": "view",
    "exit": "logout",
    "find": "search",
    "finish": "complete",
    "finished": "complete",
    "generate report": "report",
    "log in": "login",
    "log out": "logout",
    "logged in": "login",
    "logged out": "logout",
    "login": "login",
    "logout": "logout",
    "news": "news and experts",
    "pay": "payment",
    "payment": "payment",
    "read news": "news and experts",
    "register": "registration",
    "registration": "registration",
    "reject": "rejection",
    "rejected": "rejection",
    "remove": "delete",
    "removed": "delete",
    "send": "submit",
    "sent": "submit",
    "show": "view",
    "sign in": "login",
    "signin": "login",
    "signed in": "login",
    "submit": "submit",
    "submitted": "submit",
    "symptom check": "symptoms checker",
    "symptom checker": "symptoms checker",
    "symptoms check": "symptoms checker",
    "symptoms checker": "symptoms checker",
    "view": "view",
}
TOKEN_CANONICAL_FORMS = {
    "accept": "approval",
    "accepted": "approval",
    "approve": "approval",
    "approved": "approval",
    "approving": "approval",
    "choose": "select",
    "choosing": "select",
    "collecting": "collect",
    "confirm": "confirmation",
    "confirmed": "confirmation",
    "create": "registration",
    "created": "registration",
    "decline": "rejection",
    "declined": "rejection",
    "delete": "delete",
    "deleted": "delete",
    "display": "view",
    "displaying": "view",
    "entering": "enter",
    "exit": "logout",
    "find": "search",
    "finished": "complete",
    "finishing": "complete",
    "generate": "report",
    "generated": "report",
    "generating": "report",
    "login": "login",
    "logout": "logout",
    "paid": "payment",
    "pay": "payment",
    "register": "registration",
    "registered": "registration",
    "reject": "rejection",
    "rejected": "rejection",
    "rejecting": "rejection",
    "remove": "delete",
    "removed": "delete",
    "removing": "delete",
    "request": "request",
    "requests": "request",
    "searching": "search",
    "selecting": "select",
    "send": "submit",
    "sent": "submit",
    "show": "view",
    "showing": "view",
    "submit": "submit",
    "submitted": "submit",
    "submitting": "submit",
    "users": "user",
    "viewing": "view",
}
GENERIC_CONTAINMENT_TOKENS = {
    "active",
    "data",
    "details",
    "end",
    "idle",
    "info",
    "input",
    "main",
    "menu",
    "new",
    "page",
    "process",
    "result",
    "start",
    "state",
    "user",
    "view",
}
TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
}
PSEUDOSTATE_STEREOTYPES = {
    "choice",
    "fork",
    "join",
    "history",
    "deephistory",
    "shallowhistory",
    "initial",
    "final",
    "start",
    "end",
    "entrypoint",
    "exitpoint",
    "junction",
    "terminate",
}
CSV_FIELDS = [
    "llm_name",
    "method_name",
    "case_id",
    "candidate_path",
    "ground_truth_path",
    "embedding_model",
    "similarity_threshold",
    "relaxed_similarity_threshold",
    "ground_truth_states",
    "candidate_states",
    "matched_state_pairs",
    "missing_ground_truth_states",
    "extra_candidate_states",
    "ground_truth_state_count",
    "candidate_state_count",
    "matched_state_count",
    "missing_state_count",
    "extra_state_count",
    "semantic_state_precision",
    "semantic_state_recall",
    "semantic_state_f1",
]


@dataclass(frozen=True)
class StateName:
    visible: str
    normalized: str


@dataclass(frozen=True)
class CandidateDiagram:
    llm_name: str
    method_name: str
    case_id: str
    puml_path: Path


def normalize_state_name(name: str) -> str:
    normalized = name.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == '"':
        normalized = normalized[1:-1]
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", normalized)
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", normalized)
    normalized = normalized.lower()
    normalized = " ".join(normalized.split())
    normalized = SYNONYM_CANONICAL_FORMS.get(normalized, normalized)
    normalized_tokens = [
        TOKEN_CANONICAL_FORMS.get(token, token)
        for token in normalized.split()
    ]
    normalized = " ".join(normalized_tokens)
    return SYNONYM_CANONICAL_FORMS.get(normalized, normalized)


def meaningful_tokens(normalized_name: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_name)
        if token not in TOKEN_STOPWORDS
    }


def is_lexical_containment_match(
    ground_truth_state: StateName,
    candidate_state: StateName,
) -> bool:
    ground_truth_tokens = meaningful_tokens(ground_truth_state.normalized)
    candidate_tokens = meaningful_tokens(candidate_state.normalized)
    if not ground_truth_tokens or not candidate_tokens:
        return False

    smaller = (
        ground_truth_tokens
        if len(ground_truth_tokens) <= len(candidate_tokens)
        else candidate_tokens
    )
    larger = (
        candidate_tokens
        if len(ground_truth_tokens) <= len(candidate_tokens)
        else ground_truth_tokens
    )
    if not smaller <= larger:
        return False
    if len(smaller) == 1 and next(iter(smaller)) in GENERIC_CONTAINMENT_TOKENS:
        return False
    return True


def extract_real_states(puml_text: str) -> list[StateName]:
    graph, _ = parse_and_validate_puml_text(puml_text, official_syntax=False)
    history_states = {
        graph.aliases.get(state, state)
        for state in graph.history_states
        if state
    }
    visible_states: set[str] = set()

    for parsed_state in graph.states:
        visible = graph.aliases.get(parsed_state, parsed_state).strip()
        if not visible or visible in {"[*]", "[H]", "[H*]"}:
            continue
        stereotypes = {
            stereotype.replace(" ", "").lower()
            for stereotype in (
                graph.stereotypes.get(parsed_state, set())
                | graph.stereotypes.get(visible, set())
            )
        }
        if stereotypes & PSEUDOSTATE_STEREOTYPES:
            continue
        if visible in history_states:
            continue
        if normalize_state_name(visible):
            visible_states.add(visible)

    return sorted(
        (
            StateName(visible=visible, normalized=normalize_state_name(visible))
            for visible in visible_states
        ),
        key=lambda state: (state.normalized, state.visible),
    )


def discover_candidate_diagrams(root: Path) -> list[CandidateDiagram]:
    diagrams: list[CandidateDiagram] = []
    for puml_path in sorted(root.glob("*/*/case_*/diagram.puml")):
        case_dir = puml_path.parent
        method_dir = case_dir.parent
        llm_dir = method_dir.parent
        diagrams.append(
            CandidateDiagram(
                llm_name=llm_dir.name,
                method_name=method_dir.name,
                case_id=case_dir.name,
                puml_path=puml_path,
            )
        )
    return sorted(
        diagrams,
        key=lambda item: (
            item.case_id,
            item.llm_name,
            item.method_name,
            str(item.puml_path),
        ),
    )


def discover_candidate_run(specification: str) -> list[CandidateDiagram]:
    parts = specification.split("|", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError(
            "--candidate-run must use the format LLM_NAME|METHOD_NAME|RUN_FOLDER"
        )
    llm_name, method_name, run_folder = (part.strip() for part in parts)
    run_path = Path(run_folder)
    if not run_path.is_dir():
        raise FileNotFoundError(f"Candidate run folder not found: {run_path}")

    diagrams = [
        CandidateDiagram(
            llm_name=llm_name,
            method_name=method_name,
            case_id=puml_path.parent.name,
            puml_path=puml_path,
        )
        for puml_path in sorted(run_path.glob("case_*/run_01.puml"))
    ]
    if not diagrams:
        raise FileNotFoundError(
            f"No case_*/run_01.puml files found under {run_path}"
        )
    return diagrams


def sort_and_validate_candidate_keys(
    diagrams: list[CandidateDiagram],
) -> list[CandidateDiagram]:
    sorted_diagrams = sorted(
        diagrams,
        key=lambda item: (
            item.case_id,
            item.llm_name,
            item.method_name,
            str(item.puml_path),
        ),
    )
    seen: set[tuple[str, str, str]] = set()
    for diagram in sorted_diagrams:
        key = (diagram.llm_name, diagram.method_name, diagram.case_id)
        if key in seen:
            raise ValueError(
                "Duplicate candidate key: "
                f"{diagram.llm_name}|{diagram.method_name}|{diagram.case_id}"
            )
        seen.add(key)
    return sorted_diagrams


def configure_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    random.seed(seed)
    np.random.seed(seed)

    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.set_num_threads(1)


def encode_state_names(
    model: SentenceTransformer,
    normalized_names: list[str],
    batch_size: int,
) -> dict[str, np.ndarray]:
    unique_names = sorted(set(normalized_names))
    if not unique_names:
        return {}
    embeddings = model.encode(
        unique_names,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return {
        name: np.asarray(embedding, dtype=np.float64)
        for name, embedding in zip(unique_names, embeddings, strict=True)
    }


def match_states(
    ground_truth_states: list[StateName],
    candidate_states: list[StateName],
    embedding_lookup: dict[str, np.ndarray],
    threshold: float,
    relaxed_threshold: float | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    if not ground_truth_states or not candidate_states:
        return (
            [],
            [state.visible for state in ground_truth_states],
            [state.visible for state in candidate_states],
        )

    ground_truth_matrix = np.vstack(
        [embedding_lookup[state.normalized] for state in ground_truth_states]
    )
    candidate_matrix = np.vstack(
        [embedding_lookup[state.normalized] for state in candidate_states]
    )
    similarities = np.clip(
        ground_truth_matrix @ candidate_matrix.T,
        -1.0,
        1.0,
    )

    maximum_pair_count = min(len(ground_truth_states), len(candidate_states))
    cardinality_bonus = (2 * maximum_pair_count) + 1
    exact_normalized_matches = np.asarray(
        [
            [
                ground_truth.normalized == candidate.normalized
                for candidate in candidate_states
            ]
            for ground_truth in ground_truth_states
        ],
        dtype=bool,
    )
    lexical_containment_matches = np.asarray(
        [
            [
                is_lexical_containment_match(ground_truth, candidate)
                for candidate in candidate_states
            ]
            for ground_truth in ground_truth_states
        ],
        dtype=bool,
    )
    strict_candidates = (similarities >= threshold) | exact_normalized_matches
    utility = np.where(strict_candidates, cardinality_bonus + similarities, 0.0)
    row_indexes, column_indexes = linear_sum_assignment(-utility)

    accepted_indexes = sorted(
        (
            (int(row_index), int(column_index))
            for row_index, column_index in zip(
                row_indexes,
                column_indexes,
                strict=True,
            )
            if strict_candidates[row_index, column_index]
        ),
        key=lambda item: item[0],
    )

    if relaxed_threshold is not None:
        if relaxed_threshold > threshold:
            raise ValueError("relaxed_threshold must be less than or equal to threshold")
        unmatched_ground_truth = [
            index
            for index in range(len(ground_truth_states))
            if index not in {row_index for row_index, _ in accepted_indexes}
        ]
        unmatched_candidates = [
            index
            for index in range(len(candidate_states))
            if index not in {column_index for _, column_index in accepted_indexes}
        ]
        if unmatched_ground_truth and unmatched_candidates:
            relaxed_utility = np.zeros(
                (len(unmatched_ground_truth), len(unmatched_candidates)),
                dtype=np.float64,
            )
            for local_row, row_index in enumerate(unmatched_ground_truth):
                for local_column, column_index in enumerate(unmatched_candidates):
                    similarity = similarities[row_index, column_index]
                    if (
                        similarity >= relaxed_threshold
                        or lexical_containment_matches[row_index, column_index]
                    ):
                        relaxed_utility[local_row, local_column] = (
                            cardinality_bonus
                            + max(float(similarity), relaxed_threshold)
                        )
            relaxed_rows, relaxed_columns = linear_sum_assignment(
                -relaxed_utility
            )
            relaxed_indexes = sorted(
                (
                    (
                        unmatched_ground_truth[int(local_row)],
                        unmatched_candidates[int(local_column)],
                    )
                    for local_row, local_column in zip(
                        relaxed_rows,
                        relaxed_columns,
                        strict=True,
                    )
                    if relaxed_utility[
                        int(local_row),
                        int(local_column),
                    ]
                    > 0.0
                ),
                key=lambda item: item[0],
            )
            accepted_indexes = sorted(
                accepted_indexes + relaxed_indexes,
                key=lambda item: item[0],
            )
    matched_ground_truth = {row_index for row_index, _ in accepted_indexes}
    matched_candidates = {column_index for _, column_index in accepted_indexes}

    matched_pairs = [
        {
            "ground_truth_state": ground_truth_states[row_index].visible,
            "candidate_state": candidate_states[column_index].visible,
            "ground_truth_normalized": ground_truth_states[row_index].normalized,
            "candidate_normalized": candidate_states[column_index].normalized,
            "similarity": round(
                float(similarities[row_index, column_index]),
                6,
            ),
            "match_type": (
                "exact_normalized"
                if exact_normalized_matches[row_index, column_index]
                else (
                    "strict"
                    if similarities[row_index, column_index] >= threshold
                    else (
                        "relaxed_lexical"
                        if lexical_containment_matches[
                            row_index,
                            column_index,
                        ]
                        else "relaxed"
                    )
                )
            ),
        }
        for row_index, column_index in accepted_indexes
    ]
    missing = [
        state.visible
        for index, state in enumerate(ground_truth_states)
        if index not in matched_ground_truth
    ]
    extra = [
        state.visible
        for index, state in enumerate(candidate_states)
        if index not in matched_candidates
    ]
    return matched_pairs, missing, extra


def semantic_metrics(
    matched_count: int,
    ground_truth_count: int,
    candidate_count: int,
) -> tuple[float, float, float]:
    precision = matched_count / candidate_count if candidate_count else 0.0
    recall = matched_count / ground_truth_count if ground_truth_count else 0.0
    f1 = (
        (2.0 * precision * recall) / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def write_results_csv(output_path: Path, rows: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def print_sample_results(rows: list[dict[str, Any]], sample_count: int) -> None:
    if sample_count <= 0:
        return
    printed = 0
    seen_cases: set[str] = set()
    for row in rows:
        case_id = str(row["case_id"])
        if case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        printed += 1
        print(
            f"\n[SAMPLE {printed}] {case_id} | "
            f"{row['llm_name']} | {row['method_name']}"
        )
        print(f"  Ground truth states: {json_cell(row['_ground_truth_states'])}")
        print(f"  Candidate states:    {json_cell(row['_candidate_states'])}")
        for pair in row["_matched_pairs"]:
            print(
                "  MATCH: "
                f"{pair['ground_truth_state']} <-> {pair['candidate_state']} "
                f"({pair['similarity']:.6f})"
            )
        print(f"  Missing: {json_cell(row['_missing_states'])}")
        print(f"  Extra:   {json_cell(row['_extra_states'])}")
        print(
            "  Precision/Recall/F1: "
            f"{row['semantic_state_precision']:.4f}/"
            f"{row['semantic_state_recall']:.4f}/"
            f"{row['semantic_state_f1']:.4f}"
        )
        if printed >= sample_count:
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate reference-based semantic state precision, recall, and F1 "
            "for strict-valid PlantUML candidates."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--valid-diagrams-root",
        type=Path,
        default=Path("valid_diagrams"),
    )
    parser.add_argument(
        "--candidate-run",
        action="append",
        default=[],
        metavar="LLM|METHOD|RUN_FOLDER",
        help=(
            "Evaluate case_*/run_01.puml files directly from a run folder. "
            "May be repeated; when supplied, --valid-diagrams-root is ignored."
        ),
    )
    parser.add_argument(
        "--allow-non-strict",
        action="store_true",
        help=(
            "Include candidates that fail strict structural validation. "
            "Their semantic state metrics remain independent of structural validity."
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "results/plantuml_pipeline/semantic_state_matching/"
            "semantic_state_matches.csv"
        ),
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--relaxed-threshold",
        type=float,
        default=None,
        help=(
            "Optional second-pass threshold for unmatched state names. "
            "Use this to count high-confidence human-obvious paraphrases "
            "without lowering the main strict threshold."
        ),
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-count", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not -1.0 <= args.threshold <= 1.0:
        raise ValueError("--threshold must be between -1.0 and 1.0")
    if args.relaxed_threshold is not None:
        if not -1.0 <= args.relaxed_threshold <= 1.0:
            raise ValueError("--relaxed-threshold must be between -1.0 and 1.0")
        if args.relaxed_threshold > args.threshold:
            raise ValueError(
                "--relaxed-threshold must be less than or equal to --threshold"
            )
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.sample_count < 0:
        raise ValueError("--sample-count must not be negative")
    if not args.dataset_root.is_dir():
        raise FileNotFoundError(f"Dataset folder not found: {args.dataset_root}")
    if not args.candidate_run and not args.valid_diagrams_root.is_dir():
        raise FileNotFoundError(
            f"Valid-diagrams folder not found: {args.valid_diagrams_root}"
        )

    configure_determinism(args.seed)
    cases = {case.case_id: case for case in load_cases(args.dataset_root)}
    if args.candidate_run:
        candidates = sort_and_validate_candidate_keys(
            [
                diagram
                for specification in args.candidate_run
                for diagram in discover_candidate_run(specification)
            ]
        )
    else:
        candidates = sort_and_validate_candidate_keys(
            discover_candidate_diagrams(args.valid_diagrams_root)
        )
    if not candidates:
        raise FileNotFoundError(
            "No candidate PlantUML diagrams were discovered."
        )

    prepared: list[
        tuple[CandidateDiagram, list[StateName], list[StateName], Path]
    ] = []
    all_normalized_names: list[str] = []
    non_strict_count = 0
    for candidate in candidates:
        case = cases.get(candidate.case_id)
        if case is None:
            raise KeyError(
                f"No ground-truth dataset case found for {candidate.case_id}"
            )
        candidate_puml = normalize_puml_text(
            candidate.puml_path.read_text(encoding="utf-8", errors="replace")
        )
        _, validation = parse_and_validate_puml_text(
            candidate_puml,
            official_syntax=False,
        )
        strict_issues = list(validation.errors) + list(validation.warnings)
        if strict_issues:
            non_strict_count += 1
            if not args.allow_non_strict:
                raise ValueError(
                    f"Candidate is not structurally strict-valid: "
                    f"{candidate.puml_path}: {strict_issues}. "
                    "Use --allow-non-strict only when intentionally evaluating "
                    "semantic states for the full raw set."
                )

        ground_truth_states = extract_real_states(case.gold_puml)
        candidate_states = extract_real_states(candidate_puml)
        all_normalized_names.extend(
            state.normalized
            for state in ground_truth_states + candidate_states
        )
        prepared.append(
            (
                candidate,
                ground_truth_states,
                candidate_states,
                case.path / "diagram.puml",
            )
        )

    print(
        f"Embedding model: {args.embedding_model}\n"
        f"Similarity threshold: {args.threshold:.2f}\n"
        f"Relaxed threshold: "
        f"{args.relaxed_threshold if args.relaxed_threshold is not None else 'disabled'}\n"
        f"Device: {args.device}\n"
        f"Seed: {args.seed}\n"
        f"Candidate diagrams: {len(prepared)}\n"
        f"Strict-valid candidates: {len(prepared) - non_strict_count}\n"
        f"Non-strict candidates included: {non_strict_count}"
    )
    model = SentenceTransformer(args.embedding_model, device=args.device)
    model.eval()
    embedding_lookup = encode_state_names(
        model,
        all_normalized_names,
        args.batch_size,
    )

    result_rows: list[dict[str, Any]] = []
    for candidate, ground_truth_states, candidate_states, ground_truth_path in prepared:
        matched_pairs, missing_states, extra_states = match_states(
            ground_truth_states,
            candidate_states,
            embedding_lookup,
            args.threshold,
            args.relaxed_threshold,
        )
        matched_count = len(matched_pairs)
        precision, recall, f1 = semantic_metrics(
            matched_count,
            len(ground_truth_states),
            len(candidate_states),
        )
        ground_truth_names = [state.visible for state in ground_truth_states]
        candidate_names = [state.visible for state in candidate_states]
        row: dict[str, Any] = {
            "llm_name": candidate.llm_name,
            "method_name": candidate.method_name,
            "case_id": candidate.case_id,
            "candidate_path": str(candidate.puml_path),
            "ground_truth_path": str(ground_truth_path),
            "embedding_model": args.embedding_model,
            "similarity_threshold": f"{args.threshold:.6f}",
            "relaxed_similarity_threshold": (
                f"{args.relaxed_threshold:.6f}"
                if args.relaxed_threshold is not None
                else ""
            ),
            "ground_truth_states": json_cell(ground_truth_names),
            "candidate_states": json_cell(candidate_names),
            "matched_state_pairs": json_cell(matched_pairs),
            "missing_ground_truth_states": json_cell(missing_states),
            "extra_candidate_states": json_cell(extra_states),
            "ground_truth_state_count": len(ground_truth_states),
            "candidate_state_count": len(candidate_states),
            "matched_state_count": matched_count,
            "missing_state_count": len(missing_states),
            "extra_state_count": len(extra_states),
            "semantic_state_precision": round(precision, 6),
            "semantic_state_recall": round(recall, 6),
            "semantic_state_f1": round(f1, 6),
            "_ground_truth_states": ground_truth_names,
            "_candidate_states": candidate_names,
            "_matched_pairs": matched_pairs,
            "_missing_states": missing_states,
            "_extra_states": extra_states,
        }
        result_rows.append(row)

    write_results_csv(args.output_csv, result_rows)
    print_sample_results(result_rows, args.sample_count)
    print(f"\nWrote {len(result_rows)} rows: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
