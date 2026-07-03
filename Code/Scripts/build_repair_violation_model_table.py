from __future__ import annotations

import argparse
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "final_results"
    / "recalculated_repair_analysis"
    / "repair_issue_resolution_by_model.csv"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "final_results" / "paper_tables"

MODEL_ORDER = ("DeepSeek", "Llama", "Mistral", "Qwen")
MODEL_ALIASES = {
    "DeepSeek R1 14B": "DeepSeek",
    "Llama 3.1 8B": "Llama",
    "Mistral": "Mistral",
    "Qwen 2.5 7B": "Qwen",
}
METHOD_ALIASES = {
    "baseline": "baseline",
    "syntax_grounded": "syntax_grounded",
}
VIOLATION_ORDER = (
    "Missing final transition",
    "Missing initial transition",
    "Duplicate transitions",
    "Orphan states",
    "Unreachable states",
    "Multiple initial transitions",
    "Choice without outgoing paths",
    "Choice without guards",
    "PlantUML syntax error",
    "Invalid [*] -> [*]",
)
VIOLATION_LABELS = {
    "Missing final transition": "missing_final_state",
    "Missing initial transition": "missing_initial_state",
    "Duplicate transitions": "duplicate_transitions",
    "Orphan states": "orphan_states",
    "Unreachable states": "unreachable_states",
    "Multiple initial transitions": "multiple_initial_states",
    "Choice without outgoing paths": "invalid_choice_node",
    "Choice without guards": "invalid_choice_guards",
    "PlantUML syntax error": "plantuml_syntax_error",
    "Invalid [*] -> [*]": "invalid_initial_to_final",
}


def format_percent(value: float) -> str:
    if value.is_integer():
        return f"{int(value)}%"
    return f"{value:.2f}".rstrip("0").rstrip(".") + "%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a violation-resolution table with one column per generator model."
    )
    parser.add_argument("--input-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--repair-method",
        choices=tuple(METHOD_ALIASES),
        default="syntax_grounded",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    with args.input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    values: dict[tuple[str, str], str] = {}
    for row in source_rows:
        method = METHOD_ALIASES.get(row["repair_method"].strip())
        if method != args.repair_method:
            continue
        model = MODEL_ALIASES[row["model"].strip()]
        violation = row["error_type"].strip()
        initial = int(row["initial_occurrences"])
        solved = int(row["solved"])
        percent = float(row["solved_percent"])
        values[(violation, model)] = (
            f"{format_percent(percent)} ({solved}/{initial})"
        )

    output_rows: list[dict[str, str]] = []
    for violation in VIOLATION_ORDER:
        output_rows.append(
            {
                "violation_type": VIOLATION_LABELS[violation],
                **{
                    model: values.get((violation, model), "-")
                    for model in MODEL_ORDER
                },
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.output_dir
        / f"{args.repair_method}_violation_resolution_by_model.csv"
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["violation_type", *MODEL_ORDER],
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
