#!/usr/bin/env python3
"""Find failed, incomplete, invalid, or missing three-LLM judgement rows."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


SCORE_COLUMNS = (
    "completeness_score",
    "correctness_score",
    "understandability_score",
    "terminological_alignment_score",
)

DEFAULT_JUDGES = (
    "deepseek-r1:14b",
    "llama3.1:8b-instruct-q4_K_M",
    "ggozad/prometheus2",
)

OUTPUT_COLUMNS = (
    "diagram_id",
    "case_id",
    "generation_model",
    "generation_method",
    "judge_model",
    "issue_type",
    "status",
    "invalid_or_missing_scores",
    "source_run_id",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def valid_likert(value: str) -> bool:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return False
    return score.is_integer() and 1 <= int(score) <= 5


def expected_diagram_ids(
    judgement_rows: list[dict[str, str]],
    expected_csv: Path | None,
) -> list[str]:
    if expected_csv is None:
        return sorted(
            {
                row.get("diagram_id", "").strip()
                for row in judgement_rows
                if row.get("diagram_id", "").strip()
            }
        )

    rows = read_csv(expected_csv)
    if not rows or "diagram_id" not in rows[0]:
        raise ValueError(
            f"Expected-diagrams CSV must contain a diagram_id column: {expected_csv}"
        )
    return sorted(
        {
            row["diagram_id"].strip()
            for row in rows
            if row.get("diagram_id", "").strip()
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a three-LLM judge CSV and report failed statuses, invalid "
            "Likert scores, duplicate rows, and missing diagram-judge pairs."
        )
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(
            "final_results/llm_judge/"
            "three_judge_reference_free_final_valid97/judge_scores_long.csv"
        ),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(
            "final_results/llm_judge/"
            "three_judge_reference_free_final_valid97/failed_judgements.csv"
        ),
    )
    parser.add_argument(
        "--expected-diagrams-csv",
        type=Path,
        help=(
            "Optional CSV containing every expected diagram_id. If omitted, "
            "the union of diagram IDs already present in the judge CSV is used."
        ),
    )
    parser.add_argument(
        "--judges",
        nargs="+",
        default=list(DEFAULT_JUDGES),
        help="Expected Ollama judge tags.",
    )
    args = parser.parse_args()

    rows = read_csv(args.input_csv)
    if not rows:
        raise ValueError(f"No judgement rows found in {args.input_csv}")

    required = {"diagram_id", "judge_model", "status", *SCORE_COLUMNS}
    missing_columns = sorted(required - set(rows[0]))
    if missing_columns:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(missing_columns)
        )

    expected_ids = expected_diagram_ids(rows, args.expected_diagrams_csv)
    expected_judges = list(dict.fromkeys(args.judges))
    row_index: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row["diagram_id"].strip(), row["judge_model"].strip())
        row_index.setdefault(key, []).append(row)

    failures: list[dict[str, str]] = []

    for diagram_id in expected_ids:
        for judge_model in expected_judges:
            matching = row_index.get((diagram_id, judge_model), [])

            if not matching:
                failures.append(
                    {
                        "diagram_id": diagram_id,
                        "case_id": "",
                        "generation_model": "",
                        "generation_method": "",
                        "judge_model": judge_model,
                        "issue_type": "missing_judgement_row",
                        "status": "missing",
                        "invalid_or_missing_scores": ";".join(SCORE_COLUMNS),
                        "source_run_id": "",
                    }
                )
                continue

            if len(matching) > 1:
                first = matching[0]
                failures.append(
                    {
                        "diagram_id": diagram_id,
                        "case_id": first.get("case_id", ""),
                        "generation_model": first.get("generation_model", ""),
                        "generation_method": first.get("generation_method", ""),
                        "judge_model": judge_model,
                        "issue_type": "duplicate_judgement_rows",
                        "status": first.get("status", ""),
                        "invalid_or_missing_scores": "",
                        "source_run_id": first.get("source_run_id", ""),
                    }
                )

            row = matching[-1]
            status = row.get("status", "").strip().lower()
            invalid_scores = [
                column
                for column in SCORE_COLUMNS
                if not valid_likert(row.get(column, ""))
            ]

            issue_types: list[str] = []
            if status != "ok":
                issue_types.append("failed_status")
            if invalid_scores:
                issue_types.append("invalid_or_missing_scores")

            if issue_types:
                failures.append(
                    {
                        "diagram_id": diagram_id,
                        "case_id": row.get("case_id", ""),
                        "generation_model": row.get("generation_model", ""),
                        "generation_method": row.get("generation_method", ""),
                        "judge_model": judge_model,
                        "issue_type": ";".join(issue_types),
                        "status": row.get("status", ""),
                        "invalid_or_missing_scores": ";".join(invalid_scores),
                        "source_run_id": row.get("source_run_id", ""),
                    }
                )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(failures)

    counts = Counter(row["judge_model"] for row in failures)
    print(f"Expected diagrams: {len(expected_ids)}")
    print(f"Expected judgement pairs: {len(expected_ids) * len(expected_judges)}")
    print(f"Failed/incomplete records: {len(failures)}")
    for judge in expected_judges:
        print(f"- {judge}: {counts[judge]}")
    print(f"Saved: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
