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
    "llama31_8b_instruct": "Llama 3.1 8B Instruct",
    "llama31_70b_instruct": "Llama 3.1 70B Instruct",
    "deepseek_r1_8b": "DeepSeek R1 8B",
    "deepseek_r1_14b": "DeepSeek R1 14B",
}

METHOD_LABELS = {
    "zero_shot": "Zero-shot",
    "few_shot": "Few-shot",
}


def parse_run_id(run_id: str) -> tuple[str, str]:
    parts = run_id.split("__")
    if len(parts) < 3:
        return run_id, "unknown"
    model_key = parts[1]
    method_key = parts[-1]
    return MODEL_LABELS.get(model_key, model_key), METHOD_LABELS.get(method_key, method_key)


def iter_run_files(runs_root: Path):
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        model, method = parse_run_id(run_dir.name)
        for puml_file in sorted(run_dir.rglob("*.puml")):
            if RUN_FILE_RE.match(puml_file.name):
                yield run_dir.name, model, method, puml_file


def percent(valid: int, total: int) -> float:
    return (valid / total * 100.0) if total else 0.0


def print_markdown_table(rows: list[dict[str, object]]) -> None:
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
    invalid_rows: list[dict[str, object]] = []

    for run_id, model, method, puml_file in iter_run_files(runs_root):
        _, validation = parse_and_validate_puml_text(puml_file.read_text(encoding="utf-8"))
        key = (model, method)
        grouped[key]["total"] += 1
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

    print_markdown_table(rows)

    if not args.no_csv:
        write_csv(rows, args.csv_output.resolve())
        write_invalid_csv(invalid_rows, args.invalid_output.resolve())
        print(f"\nCSV written to: {args.csv_output.resolve()}")
        print(f"Invalid case list written to: {args.invalid_output.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
