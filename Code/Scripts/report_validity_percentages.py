#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

from plantuml_pipeline.constants import PROJECT_ROOT
from plantuml_pipeline.parser import parse_and_validate_puml_text


RUN_FILE_RE = re.compile(r"^run_\d+\.puml$")

MODEL_LABELS = {
    "qwen25_7b_instruct": "Qwen 2.5 7B Instruct",
    "qwen25_14b_instruct": "Qwen 2.5 14B Instruct",
    "llama31_8b_instruct": "Llama 3.1 8B Instruct",
    "llama31_70b_instruct": "Llama 3.1 70B Instruct",
    "deepseek_r1_8b": "DeepSeek R1 8B",
    "deepseek_r1_14b": "DeepSeek R1 14B",
}

METHOD_LABELS = {
    "zero_shot": "Zero-shot",
    "few_shot": "Few-shot",
    "rag": "RAG",
    "rag_structural_validation": "RAG + Validation",
    "rag_validation_generator_critic_repair": "RAG + Critic + Repair",
}


def parse_run_id(run_id: str) -> tuple[str, str]:
    parts = run_id.split("__")
    if len(parts) < 3:
        return run_id, "unknown"
    model_key = parts[1]
    method_key = parts[2]
    return MODEL_LABELS.get(model_key, model_key), METHOD_LABELS.get(method_key, method_key)


def iter_run_files(runs_root: Path, run_id_contains: list[str]):
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if run_id_contains and not all(token in run_dir.name for token in run_id_contains):
            continue
        model, method = parse_run_id(run_dir.name)
        for puml_file in sorted(run_dir.rglob("*.puml")):
            if RUN_FILE_RE.match(puml_file.name):
                yield run_dir.name, model, method, puml_file


def percent(valid: int, total: int) -> float:
    return (valid / total * 100.0) if total else 0.0


def print_markdown_table(rows: list[dict[str, object]], title: str) -> None:
    print(f"\n{title}")
    print("| Model | Method | Total Runs | Valid | Invalid | Validity % |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in rows:
        print(
            f"| {row['model']} | {row['method']} | {row['total']} | "
            f"{row['valid']} | {row['invalid']} | {row['validity_percent']:.2f}% |"
        )


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "method",
                "total",
                "valid",
                "invalid",
                "validity_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_invalid_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "method",
                "run_id",
                "case_id",
                "run_file",
                "path",
                "errors",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_case_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "method",
                "run_id",
                "case_id",
                "run_file",
                "valid",
                "path",
                "issues",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report PlantUML validity percentage by model and method."
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=PROJECT_ROOT / "results" / "plantuml_pipeline" / "runs",
        help="Folder containing model/method run output directories.",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "validity_by_model_method.csv",
        help="CSV file to write.",
    )
    parser.add_argument(
        "--invalid-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "invalid_validity_cases.csv",
        help="CSV file listing invalid .puml files.",
    )
    parser.add_argument(
        "--state-rules-csv-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "state_rules_validity_by_model_method.csv",
        help="CSV summary for strict UML state-rule validity.",
    )
    parser.add_argument(
        "--plantuml-cases-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "plantuml_validity_cases.csv",
        help="CSV file listing PlantUML validity for every run file.",
    )
    parser.add_argument(
        "--state-rules-cases-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "state_rules_validity_cases.csv",
        help="CSV file listing strict UML state-rule validity for every run file.",
    )
    parser.add_argument(
        "--invalid-state-rules-output",
        type=Path,
        default=PROJECT_ROOT
        / "results"
        / "plantuml_pipeline"
        / "metrics"
        / "invalid_state_rules_cases.csv",
        help="CSV file listing state-rule-invalid .puml files.",
    )
    parser.add_argument(
        "--run-id-contains",
        action="append",
        default=[],
        help="Only include run folders whose run_id contains this text. Repeatable.",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Only print the table; do not write the CSV file.",
    )
    args = parser.parse_args()

    runs_root = args.runs_root.resolve()
    if not runs_root.exists():
        raise FileNotFoundError(f"Runs folder not found: {runs_root}")

    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "valid": 0, "invalid": 0}
    )
    state_grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "valid": 0, "invalid": 0}
    )
    invalid_rows: list[dict[str, object]] = []
    invalid_state_rows: list[dict[str, object]] = []
    plantuml_case_rows: list[dict[str, object]] = []
    state_case_rows: list[dict[str, object]] = []

    for run_id, model, method, puml_file in iter_run_files(runs_root, args.run_id_contains):
        _, validation = parse_and_validate_puml_text(puml_file.read_text(encoding="utf-8"))
        key = (model, method)
        grouped[key]["total"] += 1
        state_grouped[key]["total"] += 1
        plantuml_issues = list(validation.errors)
        state_issues = list(validation.errors) + list(validation.warnings)
        state_rules_valid = validation.valid and not state_issues

        plantuml_case_rows.append(
            {
                "model": model,
                "method": method,
                "run_id": run_id,
                "case_id": puml_file.parent.name,
                "run_file": puml_file.name,
                "valid": validation.valid,
                "path": str(puml_file),
                "issues": " | ".join(plantuml_issues),
            }
        )
        state_case_rows.append(
            {
                "model": model,
                "method": method,
                "run_id": run_id,
                "case_id": puml_file.parent.name,
                "run_file": puml_file.name,
                "valid": state_rules_valid,
                "path": str(puml_file),
                "issues": " | ".join(state_issues),
            }
        )

        if validation.valid:
            grouped[key]["valid"] += 1
        else:
            grouped[key]["invalid"] += 1
            invalid_rows.append(
                {
                    "model": model,
                    "method": method,
                    "run_id": run_id,
                    "case_id": puml_file.parent.name,
                    "run_file": puml_file.name,
                    "path": str(puml_file),
                    "errors": " | ".join(validation.errors),
                }
            )
        if state_rules_valid:
            state_grouped[key]["valid"] += 1
        else:
            state_grouped[key]["invalid"] += 1
            invalid_state_rows.append(
                {
                    "model": model,
                    "method": method,
                    "run_id": run_id,
                    "case_id": puml_file.parent.name,
                    "run_file": puml_file.name,
                    "path": str(puml_file),
                    "errors": " | ".join(state_issues),
                }
            )

    rows: list[dict[str, object]] = []
    for (model, method), counts in sorted(grouped.items()):
        rows.append(
            {
                "model": model,
                "method": method,
                "total": counts["total"],
                "valid": counts["valid"],
                "invalid": counts["invalid"],
                "validity_percent": round(percent(counts["valid"], counts["total"]), 2),
            }
        )
    state_rows: list[dict[str, object]] = []
    for (model, method), counts in sorted(state_grouped.items()):
        state_rows.append(
            {
                "model": model,
                "method": method,
                "total": counts["total"],
                "valid": counts["valid"],
                "invalid": counts["invalid"],
                "validity_percent": round(percent(counts["valid"], counts["total"]), 2),
            }
        )

    print_markdown_table(rows, "PlantUML render/syntax validity")
    print_markdown_table(state_rows, "Strict UML state-rule validity")

    if not args.no_csv:
        write_csv(rows, args.csv_output.resolve())
        write_invalid_csv(invalid_rows, args.invalid_output.resolve())
        write_csv(state_rows, args.state_rules_csv_output.resolve())
        write_invalid_csv(invalid_state_rows, args.invalid_state_rules_output.resolve())
        write_case_csv(plantuml_case_rows, args.plantuml_cases_output.resolve())
        write_case_csv(state_case_rows, args.state_rules_cases_output.resolve())
        print(f"\nCSV written to: {args.csv_output.resolve()}")
        print(f"Invalid case list written to: {args.invalid_output.resolve()}")
        print(f"State-rule CSV written to: {args.state_rules_csv_output.resolve()}")
        print(f"State-rule invalid case list written to: {args.invalid_state_rules_output.resolve()}")
        print(f"PlantUML per-case table written to: {args.plantuml_cases_output.resolve()}")
        print(f"State-rule per-case table written to: {args.state_rules_cases_output.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
