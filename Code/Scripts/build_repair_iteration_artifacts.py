#!/usr/bin/env python3
"""Create repair-iteration review folders and summary tables.

The repair pipeline can attempt one or more repair calls before the final
diagram is chosen. This script keeps only final structurally valid repair
cases, then groups them by attempted repair-loop count so they can be inspected
manually and reported separately. Therefore `repair_at_once` means the loop
stopped after one repair model call, and `repair_at_zero_iterations` means the
original candidate was already structurally valid so no repair call was needed.

Outputs:
  results/plantuml_pipeline/repair_iteration_review/
  results/human_evaluation_likert/exact_repair_iteration_0_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iteration_1_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iteration_2_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iteration_3_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iteration_4_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iteration_5_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_iterations_0_1_2_table_score_only_with_n.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[2]
REPAIR_DETAIL = ROOT / "results" / "plantuml_pipeline" / "repair_effectiveness" / "repair_detail.csv"
STATE_RULES_CASES = ROOT / "results" / "plantuml_pipeline" / "metrics" / "state_rules_validity_cases.csv"
HUMAN_EVAL = ROOT / "results" / "evaluation_diagram_responses_long_form.csv"
OUT_TABLE_DIR = ROOT / "results" / "human_evaluation_likert"
OUT_REVIEW_DIR = ROOT / "results" / "plantuml_pipeline" / "repair_iteration_review"

CRITERIA = [
    ("Completeness", "completeness"),
    ("Correctness", "correctness"),
    ("Understandability", "understandability"),
    ("Terminology alignment", "terminology_alignment"),
]

MODEL_ORDER = [
    "Llama 3.1 8B Instruct",
    "Mistral",
    "DeepSeek R1 14B",
    "Qwen 2.5 7B Instruct",
]

MODEL_SHORT_LOWER = {
    "Llama 3.1 8B Instruct": "llama",
    "Mistral": "mistral",
    "DeepSeek R1 14B": "deepseek",
    "Qwen 2.5 7B Instruct": "qwen",
}

ITERATION_FOLDER = {
    0: "repair_at_zero_iterations",
    1: "repair_at_once",
    2: "repair_at_two_iterations",
    3: "repair_at_three_iterations",
    4: "repair_at_four_iterations",
    5: "repair_at_five_iterations",
}

ITERATION_LABEL = {
    0: "Repair at zero iterations",
    1: "Repair at once",
    2: "Repair at two iterations",
    3: "Repair at three iterations",
    4: "Repair at four iterations",
    5: "Repair at five iterations",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def model_sort_key(model: str) -> tuple[int, str]:
    try:
        return (MODEL_ORDER.index(model), model)
    except ValueError:
        return (len(MODEL_ORDER), model)


def case_number(case_id: str) -> str:
    match = re.match(r"case_(\d+)", case_id)
    return str(int(match.group(1))) if match else case_id


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def pct_with_n(valid: int, total: int) -> str:
    return f"{(valid / total * 100):.2f}% (n={valid}/{total})" if total else ""


def median_with_n(values: list[int]) -> str:
    if not values:
        return ""
    return f"{median(values):g} (n={len(values)})"


def numeric_scores(
    human_rows: list[dict[str, str]],
    *,
    model: str,
    case_numbers: set[str],
    criterion: str,
) -> list[int]:
    values: list[int] = []
    for row in human_rows:
        if row.get("method") != "Repair":
            continue
        if row.get("llm_used") != model:
            continue
        if row.get("case_number") not in case_numbers:
            continue
        try:
            values.append(int(float(row[criterion])))
        except Exception:
            pass
    return values


def clear_review_dir() -> None:
    if OUT_REVIEW_DIR.exists():
        shutil.rmtree(OUT_REVIEW_DIR)
    OUT_REVIEW_DIR.mkdir(parents=True, exist_ok=True)


def structurally_valid_case_keys() -> set[tuple[str, str, str]]:
    return {
        (row["model"], row["method"], row["case_id"])
        for row in read_csv(STATE_RULES_CASES)
        if row["valid"] == "True"
    }


def structurally_valid_rows(repair_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    valid_keys = structurally_valid_case_keys()
    return [
        row
        for row in repair_rows
        if (row["model"], row["method"], row["case_id"]) in valid_keys
    ]


def copy_case_artifacts(row: dict[str, str], iteration: int) -> dict[str, str]:
    model = row["model"]
    model_dir = OUT_REVIEW_DIR / MODEL_SHORT_LOWER.get(model, slug(model))
    iteration_dir = model_dir / ITERATION_FOLDER[iteration]
    case_dir = iteration_dir / row["case_id"]
    case_dir.mkdir(parents=True, exist_ok=True)

    final_path = Path(row["final_path"])
    source_dir = final_path.parent
    copied = 0
    for source in sorted(source_dir.glob("run_01*")):
        if source.is_file() and source.suffix.lower() in {".puml", ".png", ".txt", ".json"}:
            shutil.copy2(source, case_dir / source.name)
            copied += 1

    return {
        "model": model,
        "method": row["method"],
        "case_id": row["case_id"],
        "case_number": case_number(row["case_id"]),
        "attempted_repair_iterations": row["attempted_repair_iterations"],
        "accepted_repair_iterations": row["accepted_repair_iterations"],
        "repair_success": row["repair_success"],
        "final_plantuml_valid": row["final_plantuml_valid"],
        "final_structural_valid": row["final_structural_valid"],
        "initial_violation_count": row["initial_violation_count"],
        "final_violation_count": row["final_violation_count"],
        "review_folder": str(case_dir.relative_to(ROOT)),
        "copied_files": str(copied),
    }


def create_review_folders(repair_rows: list[dict[str, str]], max_iteration: int) -> None:
    clear_review_dir()
    manifest_rows: list[dict[str, str]] = []

    for model in sorted({row["model"] for row in repair_rows}, key=model_sort_key):
        model_dir = OUT_REVIEW_DIR / MODEL_SHORT_LOWER.get(model, slug(model))
        for iteration in range(0, max_iteration + 1):
            (model_dir / ITERATION_FOLDER[iteration]).mkdir(parents=True, exist_ok=True)

    for row in repair_rows:
        iteration = int(row["attempted_repair_iterations"])
        if 0 <= iteration <= max_iteration:
            manifest_rows.append(copy_case_artifacts(row, iteration))

    if manifest_rows:
        fieldnames = list(manifest_rows[0].keys())
        with (OUT_REVIEW_DIR / "manifest.csv").open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(manifest_rows)


def table_for_iterations(
    repair_rows: list[dict[str, str]],
    human_rows: list[dict[str, str]],
    iterations: list[int],
    out_path: Path,
) -> None:
    models = sorted({row["model"] for row in repair_rows}, key=model_sort_key)
    header = ["Evaluation group", "Metric"] + [
        f"{ITERATION_LABEL[iteration]} | {MODEL_SHORT_LOWER.get(model, model.lower())}"
        for iteration in iterations
        for model in models
    ]

    by_iteration_model: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in repair_rows:
        iteration = int(row["attempted_repair_iterations"])
        if iteration in iterations:
            by_iteration_model[(iteration, row["model"])].append(row)

    rows: list[list[str]] = []
    rows.append(
        ["Automatic (accuracy)", "Structural validity"]
        + [
            pct_with_n(
                sum(r["final_structural_valid"] == "True" for r in by_iteration_model[(iteration, model)]),
                len(by_iteration_model[(iteration, model)]),
            )
            for iteration in iterations
            for model in models
        ]
    )
    rows.append(
        ["Automatic (accuracy)", "Syntactic validity"]
        + [
            pct_with_n(
                sum(r["final_plantuml_valid"] == "True" for r in by_iteration_model[(iteration, model)]),
                len(by_iteration_model[(iteration, model)]),
            )
            for iteration in iterations
            for model in models
        ]
    )

    for criterion_label, criterion in CRITERIA:
        values = []
        for iteration in iterations:
            for model in models:
                subset = by_iteration_model[(iteration, model)]
                case_numbers = {case_number(row["case_id"]) for row in subset}
                values.append(
                    median_with_n(
                        numeric_scores(
                            human_rows,
                            model=model,
                            case_numbers=case_numbers,
                            criterion=criterion,
                        )
                    )
                )
        rows.append(["Human (Likert scale 1-5)", criterion_label] + values)

    write_csv(out_path, header, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-iteration",
        type=int,
        default=5,
        choices=range(0, 6),
        help="Create manual-review folders up to this attempted repair iteration.",
    )
    args = parser.parse_args()

    repair_rows = structurally_valid_rows(read_csv(REPAIR_DETAIL))
    human_rows = read_csv(HUMAN_EVAL)

    create_review_folders(repair_rows, args.max_iteration)
    table_for_iterations(
        repair_rows,
        human_rows,
        [0],
        OUT_TABLE_DIR / "exact_repair_iteration_0_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [1],
        OUT_TABLE_DIR / "exact_repair_iteration_1_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [2],
        OUT_TABLE_DIR / "exact_repair_iteration_2_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [3],
        OUT_TABLE_DIR / "exact_repair_iteration_3_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [4],
        OUT_TABLE_DIR / "exact_repair_iteration_4_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [5],
        OUT_TABLE_DIR / "exact_repair_iteration_5_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [0, 1, 2],
        OUT_TABLE_DIR / "exact_repair_iterations_0_1_2_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [0, 1, 2, 3],
        OUT_TABLE_DIR / "exact_repair_iterations_0_1_2_3_table_score_only_with_n.csv",
    )
    table_for_iterations(
        repair_rows,
        human_rows,
        [0, 1, 2, 3, 4, 5],
        OUT_TABLE_DIR / "exact_repair_iterations_0_1_2_3_4_5_table_score_only_with_n.csv",
    )

    print(f"review_dir={OUT_REVIEW_DIR}")
    print(f"tables_dir={OUT_TABLE_DIR}")


if __name__ == "__main__":
    main()
