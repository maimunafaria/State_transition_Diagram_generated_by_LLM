#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
from sentence_transformers import SentenceTransformer

from evaluate_semantic_state_matching import (
    DEFAULT_EMBEDDING_MODEL,
    configure_determinism,
    encode_state_names,
    extract_real_states,
    json_cell,
)
from plantuml_pipeline.parser import normalize_puml_text, parse_plantuml


DEFAULT_LABEL_SIMILARITY_THRESHOLD = 0.80
LABEL_STATUSES = (
    "similar",
    "dissimilar",
    "both_missing",
    "candidate_label_missing",
    "ground_truth_label_missing",
)
CSV_FIELDS = [
    "llm_name",
    "method_name",
    "case_id",
    "candidate_path",
    "ground_truth_path",
    "state_mappings_csv",
    "label_embedding_model",
    "label_similarity_threshold",
    "ground_truth_transitions",
    "candidate_transitions",
    "matched_transition_pairs",
    "missing_ground_truth_transitions",
    "extra_candidate_transitions",
    "ground_truth_transition_count",
    "candidate_transition_count",
    "matched_transition_count",
    "missing_transition_count",
    "extra_transition_count",
    "similar_label_count",
    "dissimilar_label_count",
    "both_missing_label_count",
    "candidate_label_missing_count",
    "ground_truth_label_missing_count",
    "topology_transition_precision",
    "topology_transition_recall",
    "topology_transition_f1",
]


@dataclass(frozen=True)
class Transition:
    index: int
    source: str
    label: str
    target: str


@dataclass
class PreparedCase:
    mapping_row: dict[str, str]
    ground_truth_transitions: list[Transition]
    candidate_transitions: list[Transition]
    candidate_state_mapping: dict[str, str]


def transition_to_dict(transition: Transition) -> dict[str, Any]:
    return {
        "index": transition.index,
        "source": transition.source,
        "label": transition.label,
        "target": transition.target,
    }


def candidate_transition_to_dict(
    transition: Transition,
    state_mapping: dict[str, str],
) -> dict[str, Any]:
    value = transition_to_dict(transition)
    value["mapped_source"] = state_mapping.get(transition.source)
    value["mapped_target"] = state_mapping.get(transition.target)
    return value


def extract_real_transitions(puml_text: str) -> list[Transition]:
    graph = parse_plantuml(puml_text)
    real_states = {state.visible for state in extract_real_states(puml_text)}
    transitions: list[Transition] = []
    for original_index, (source, label, target) in enumerate(
        graph.transitions,
        start=1,
    ):
        visible_source = graph.aliases.get(source, source)
        visible_target = graph.aliases.get(target, target)
        if visible_source not in real_states or visible_target not in real_states:
            continue
        transitions.append(
            Transition(
                index=original_index,
                source=visible_source,
                label=label.strip(),
                target=visible_target,
            )
        )
    return transitions


def load_state_mapping_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"State-mapping CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_fields = {
            "llm_name",
            "method_name",
            "case_id",
            "candidate_path",
            "ground_truth_path",
            "embedding_model",
            "matched_state_pairs",
        }
        if reader.fieldnames is None or not required_fields.issubset(
            reader.fieldnames
        ):
            missing = sorted(required_fields - set(reader.fieldnames or []))
            raise ValueError(
                f"State-mapping CSV is missing required columns: {missing}"
            )
        rows = list(reader)
    if not rows:
        raise ValueError(f"State-mapping CSV has no data rows: {path}")
    return rows


def parse_candidate_state_mapping(row: dict[str, str]) -> dict[str, str]:
    try:
        pairs = json.loads(row["matched_state_pairs"])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid matched_state_pairs JSON for {row['case_id']}: {exc}"
        ) from exc
    if not isinstance(pairs, list):
        raise ValueError(
            f"matched_state_pairs must be a JSON list for {row['case_id']}"
        )

    mapping: dict[str, str] = {}
    mapped_ground_truth_states: set[str] = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError(
                f"Invalid state pair for {row['case_id']}: {pair!r}"
            )
        candidate_state = str(pair.get("candidate_state", "")).strip()
        ground_truth_state = str(pair.get("ground_truth_state", "")).strip()
        if not candidate_state or not ground_truth_state:
            raise ValueError(
                f"State pair lacks an endpoint for {row['case_id']}: {pair!r}"
            )
        if candidate_state in mapping:
            raise ValueError(
                f"Candidate state mapped more than once for {row['case_id']}: "
                f"{candidate_state}"
            )
        if ground_truth_state in mapped_ground_truth_states:
            raise ValueError(
                f"Ground-truth state mapped more than once for {row['case_id']}: "
                f"{ground_truth_state}"
            )
        mapping[candidate_state] = ground_truth_state
        mapped_ground_truth_states.add(ground_truth_state)
    return mapping


def prepare_cases(rows: list[dict[str, str]]) -> list[PreparedCase]:
    prepared: list[PreparedCase] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (row["llm_name"], row["method_name"], row["case_id"])
        if key in seen_keys:
            raise ValueError(f"Duplicate state-mapping row: {'|'.join(key)}")
        seen_keys.add(key)

        candidate_path = Path(row["candidate_path"])
        ground_truth_path = Path(row["ground_truth_path"])
        if not candidate_path.is_file():
            raise FileNotFoundError(
                f"Candidate PlantUML file not found: {candidate_path}"
            )
        if not ground_truth_path.is_file():
            raise FileNotFoundError(
                f"Ground-truth PlantUML file not found: {ground_truth_path}"
            )
        candidate_puml = normalize_puml_text(
            candidate_path.read_text(encoding="utf-8", errors="replace")
        )
        ground_truth_puml = normalize_puml_text(
            ground_truth_path.read_text(encoding="utf-8", errors="replace")
        )
        prepared.append(
            PreparedCase(
                mapping_row=row,
                ground_truth_transitions=extract_real_transitions(
                    ground_truth_puml
                ),
                candidate_transitions=extract_real_transitions(candidate_puml),
                candidate_state_mapping=parse_candidate_state_mapping(row),
            )
        )
    return prepared


def label_pair_utility(
    ground_truth_label: str,
    candidate_label: str,
    embedding_lookup: dict[str, np.ndarray],
) -> float:
    if not ground_truth_label and not candidate_label:
        return 2.0
    if not ground_truth_label or not candidate_label:
        return 0.0
    similarity = float(
        embedding_lookup[ground_truth_label]
        @ embedding_lookup[candidate_label]
    )
    return 1.0 + float(np.clip(similarity, -1.0, 1.0))


def label_diagnostic(
    ground_truth_label: str,
    candidate_label: str,
    embedding_lookup: dict[str, np.ndarray],
    threshold: float,
) -> tuple[str, float | None]:
    if not ground_truth_label and not candidate_label:
        return "both_missing", None
    if not candidate_label:
        return "candidate_label_missing", None
    if not ground_truth_label:
        return "ground_truth_label_missing", None
    similarity = float(
        np.clip(
            embedding_lookup[ground_truth_label]
            @ embedding_lookup[candidate_label],
            -1.0,
            1.0,
        )
    )
    status = "similar" if similarity >= threshold else "dissimilar"
    return status, round(similarity, 6)


def pair_parallel_transitions(
    ground_truth_transitions: list[Transition],
    candidate_transitions: list[Transition],
    embedding_lookup: dict[str, np.ndarray],
) -> list[tuple[int, int]]:
    if not ground_truth_transitions or not candidate_transitions:
        return []
    utility = np.asarray(
        [
            [
                label_pair_utility(
                    ground_truth.label,
                    candidate.label,
                    embedding_lookup,
                )
                for candidate in candidate_transitions
            ]
            for ground_truth in ground_truth_transitions
        ],
        dtype=np.float64,
    )
    row_indexes, column_indexes = linear_sum_assignment(-utility)
    return sorted(
        (
            (int(row_index), int(column_index))
            for row_index, column_index in zip(
                row_indexes,
                column_indexes,
                strict=True,
            )
        ),
        key=lambda item: item[0],
    )


def match_transitions(
    ground_truth_transitions: list[Transition],
    candidate_transitions: list[Transition],
    state_mapping: dict[str, str],
    embedding_lookup: dict[str, np.ndarray],
    label_threshold: float,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    ground_truth_groups: dict[tuple[str, str], list[Transition]] = defaultdict(
        list
    )
    for transition in ground_truth_transitions:
        ground_truth_groups[(transition.source, transition.target)].append(
            transition
        )

    candidate_groups: dict[tuple[str, str], list[Transition]] = defaultdict(list)
    unmapped_candidate_indexes: set[int] = set()
    for transition in candidate_transitions:
        mapped_source = state_mapping.get(transition.source)
        mapped_target = state_mapping.get(transition.target)
        if mapped_source is None or mapped_target is None:
            unmapped_candidate_indexes.add(transition.index)
            continue
        candidate_groups[(mapped_source, mapped_target)].append(transition)

    matched_pairs: list[dict[str, Any]] = []
    matched_ground_truth_indexes: set[int] = set()
    matched_candidate_indexes: set[int] = set()
    for topology in sorted(set(ground_truth_groups) & set(candidate_groups)):
        ground_truth_group = ground_truth_groups[topology]
        candidate_group = candidate_groups[topology]
        for ground_truth_index, candidate_index in pair_parallel_transitions(
            ground_truth_group,
            candidate_group,
            embedding_lookup,
        ):
            ground_truth = ground_truth_group[ground_truth_index]
            candidate = candidate_group[candidate_index]
            label_status, label_similarity = label_diagnostic(
                ground_truth.label,
                candidate.label,
                embedding_lookup,
                label_threshold,
            )
            matched_ground_truth_indexes.add(ground_truth.index)
            matched_candidate_indexes.add(candidate.index)
            matched_pairs.append(
                {
                    "ground_truth_transition": transition_to_dict(ground_truth),
                    "candidate_transition": candidate_transition_to_dict(
                        candidate,
                        state_mapping,
                    ),
                    "label_status": label_status,
                    "label_similarity": label_similarity,
                }
            )

    matched_pairs.sort(
        key=lambda pair: (
            pair["ground_truth_transition"]["index"],
            pair["candidate_transition"]["index"],
        )
    )
    missing = [
        transition_to_dict(transition)
        for transition in ground_truth_transitions
        if transition.index not in matched_ground_truth_indexes
    ]
    extra = [
        candidate_transition_to_dict(transition, state_mapping)
        for transition in candidate_transitions
        if (
            transition.index in unmapped_candidate_indexes
            or transition.index not in matched_candidate_indexes
        )
    ]
    return matched_pairs, missing, extra


def transition_metrics(
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


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
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
        print(
            f"  Ground-truth transitions: "
            f"{json_cell(row['_ground_truth_transitions'])}"
        )
        print(
            f"  Candidate transitions:    "
            f"{json_cell(row['_candidate_transitions'])}"
        )
        for pair in row["_matched_pairs"]:
            ground_truth = pair["ground_truth_transition"]
            candidate = pair["candidate_transition"]
            similarity = pair["label_similarity"]
            similarity_text = (
                f", similarity={similarity:.6f}"
                if similarity is not None
                else ""
            )
            print(
                "  MATCH: "
                f"{ground_truth['source']} -> {ground_truth['target']} "
                f"<-> {candidate['source']} -> {candidate['target']} "
                f"[{pair['label_status']}{similarity_text}]"
            )
        print(f"  Missing: {json_cell(row['_missing_transitions'])}")
        print(f"  Extra:   {json_cell(row['_extra_transitions'])}")
        print(
            "  Precision/Recall/F1: "
            f"{row['topology_transition_precision']:.4f}/"
            f"{row['topology_transition_recall']:.4f}/"
            f"{row['topology_transition_f1']:.4f}"
        )
        if printed >= sample_count:
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate topology-based semantic transition precision, recall, "
            "and F1 using an existing semantic state-mapping CSV."
        )
    )
    parser.add_argument(
        "--state-mappings-csv",
        type=Path,
        default=Path(
            "results/plantuml_pipeline/semantic_state_matching/"
            "semantic_state_matches.csv"
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "results/plantuml_pipeline/semantic_transition_matching/"
            "topology_transition_matches.csv"
        ),
    )
    parser.add_argument(
        "--label-embedding-model",
        default="",
        help=(
            "Local sentence-embedding model for label diagnostics. "
            "Defaults to the state-mapping CSV model."
        ),
    )
    parser.add_argument(
        "--label-similarity-threshold",
        type=float,
        default=DEFAULT_LABEL_SIMILARITY_THRESHOLD,
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-count", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not -1.0 <= args.label_similarity_threshold <= 1.0:
        raise ValueError(
            "--label-similarity-threshold must be between -1.0 and 1.0"
        )
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")
    if args.sample_count < 0:
        raise ValueError("--sample-count must not be negative")

    configure_determinism(args.seed)
    mapping_rows = load_state_mapping_rows(args.state_mappings_csv)
    prepared_cases = prepare_cases(mapping_rows)
    mapping_models = {
        row["embedding_model"].strip()
        for row in mapping_rows
        if row["embedding_model"].strip()
    }
    if args.label_embedding_model:
        label_embedding_model = args.label_embedding_model
    elif len(mapping_models) == 1:
        label_embedding_model = next(iter(mapping_models))
    elif not mapping_models:
        label_embedding_model = DEFAULT_EMBEDDING_MODEL
    else:
        raise ValueError(
            "State-mapping CSV contains multiple embedding models; specify "
            "--label-embedding-model explicitly."
        )

    labels = [
        transition.label
        for prepared in prepared_cases
        for transition in (
            prepared.ground_truth_transitions
            + prepared.candidate_transitions
        )
        if transition.label
    ]
    print(
        f"State mappings: {args.state_mappings_csv}\n"
        f"Label embedding model: {label_embedding_model}\n"
        f"Label similarity threshold: "
        f"{args.label_similarity_threshold:.2f}\n"
        f"Device: {args.device}\n"
        f"Seed: {args.seed}\n"
        f"Candidate diagrams: {len(prepared_cases)}"
    )
    embedding_lookup: dict[str, np.ndarray] = {}
    if labels:
        model = SentenceTransformer(label_embedding_model, device=args.device)
        model.eval()
        embedding_lookup = encode_state_names(
            model,
            labels,
            args.batch_size,
        )

    result_rows: list[dict[str, Any]] = []
    for prepared in prepared_cases:
        row = prepared.mapping_row
        matched_pairs, missing, extra = match_transitions(
            prepared.ground_truth_transitions,
            prepared.candidate_transitions,
            prepared.candidate_state_mapping,
            embedding_lookup,
            args.label_similarity_threshold,
        )
        matched_count = len(matched_pairs)
        precision, recall, f1 = transition_metrics(
            matched_count,
            len(prepared.ground_truth_transitions),
            len(prepared.candidate_transitions),
        )
        ground_truth_values = [
            transition_to_dict(transition)
            for transition in prepared.ground_truth_transitions
        ]
        candidate_values = [
            candidate_transition_to_dict(
                transition,
                prepared.candidate_state_mapping,
            )
            for transition in prepared.candidate_transitions
        ]
        status_counts = {
            status: sum(
                pair["label_status"] == status
                for pair in matched_pairs
            )
            for status in LABEL_STATUSES
        }
        output_row: dict[str, Any] = {
            "llm_name": row["llm_name"],
            "method_name": row["method_name"],
            "case_id": row["case_id"],
            "candidate_path": row["candidate_path"],
            "ground_truth_path": row["ground_truth_path"],
            "state_mappings_csv": str(args.state_mappings_csv),
            "label_embedding_model": label_embedding_model,
            "label_similarity_threshold": (
                f"{args.label_similarity_threshold:.6f}"
            ),
            "ground_truth_transitions": json_cell(ground_truth_values),
            "candidate_transitions": json_cell(candidate_values),
            "matched_transition_pairs": json_cell(matched_pairs),
            "missing_ground_truth_transitions": json_cell(missing),
            "extra_candidate_transitions": json_cell(extra),
            "ground_truth_transition_count": len(
                prepared.ground_truth_transitions
            ),
            "candidate_transition_count": len(
                prepared.candidate_transitions
            ),
            "matched_transition_count": matched_count,
            "missing_transition_count": len(missing),
            "extra_transition_count": len(extra),
            "similar_label_count": status_counts["similar"],
            "dissimilar_label_count": status_counts["dissimilar"],
            "both_missing_label_count": status_counts["both_missing"],
            "candidate_label_missing_count": status_counts[
                "candidate_label_missing"
            ],
            "ground_truth_label_missing_count": status_counts[
                "ground_truth_label_missing"
            ],
            "topology_transition_precision": round(precision, 6),
            "topology_transition_recall": round(recall, 6),
            "topology_transition_f1": round(f1, 6),
            "_ground_truth_transitions": ground_truth_values,
            "_candidate_transitions": candidate_values,
            "_matched_pairs": matched_pairs,
            "_missing_transitions": missing,
            "_extra_transitions": extra,
        }
        result_rows.append(output_row)

    write_results_csv(args.output_csv, result_rows)
    print_sample_results(result_rows, args.sample_count)
    print(f"\nWrote {len(result_rows)} rows: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
