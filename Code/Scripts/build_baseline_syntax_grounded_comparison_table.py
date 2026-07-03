from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_VALIDITY_CSV = (
    PROJECT_ROOT
    / "final_results"
    / "recalculated_repair_analysis"
    / "repair_validity_summary.csv"
)
DEFAULT_HUMAN_CSV = (
    PROJECT_ROOT
    / "final_results"
    / "llm_judge"
    / "final_human_comparison"
    / "human_llm_final97_analysis_input.csv"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "final_results" / "paper_tables"

MODEL_ORDER = ("LLaMA", "Mistral", "DeepSeek", "Qwen")
METHOD_ORDER = ("Baseline", "Syntax-Grounded")
CRITERION_ORDER = (
    "Completeness",
    "Correctness",
    "Understandability",
    "Terminological alignment",
)

MODEL_ALIASES = {
    "Llama 3.1 8B": "LLaMA",
    "Llama_3.1_8B": "LLaMA",
    "Mistral": "Mistral",
    "DeepSeek R1 14B": "DeepSeek",
    "DeepSeek_R1_14B": "DeepSeek",
    "Qwen 2.5 7B": "Qwen",
    "Qwen_2.5_7B": "Qwen",
}
METHOD_ALIASES = {
    "baseline": "Baseline",
    "baseline_repair": "Baseline",
    "syntax_grounded": "Syntax-Grounded",
    "syntax_grounded_repair": "Syntax-Grounded",
}
CRITERION_ALIASES = {
    "completeness": "Completeness",
    "correctness": "Correctness",
    "understandability": "Understandability",
    "terminological_alignment": "Terminological alignment",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def format_score(value: float) -> str:
    return str(int(value)) if value.is_integer() else f"{value:.1f}"


def build_rows(
    validity_rows: list[dict[str, str]],
    human_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []

    for row in validity_rows:
        if row["model"].strip().lower() == "overall":
            continue
        model = MODEL_ALIASES[row["model"].strip()]
        method = METHOD_ALIASES[row["repair_method"].strip()]
        cases = int(row["cases"])
        for metric, count_field, percent_field in (
            ("Syntactic", "syntax_valid_count", "syntax_valid_percent"),
            ("Structural", "structural_valid_count", "structural_valid_percent"),
        ):
            count = int(row[count_field])
            percent = float(row[percent_field])
            output.append(
                {
                    "evaluation_type": "Automatic",
                    "metric": metric,
                    "repair_method": method,
                    "model": model,
                    "value": f"{percent:.2f}",
                    "count": count,
                    "denominator": cases,
                    "formatted_value": f"{percent:.2f}%, n={count}",
                }
            )

    grouped_scores: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in human_rows:
        method_raw = row["repair_strategy"].strip()
        if method_raw not in METHOD_ALIASES:
            continue
        key = (
            METHOD_ALIASES[method_raw],
            MODEL_ALIASES[row["generator_model"].strip()],
            CRITERION_ALIASES[row["criterion"].strip()],
        )
        grouped_scores[key].append(float(row["human_score"]))

    for (method, model, criterion), scores in grouped_scores.items():
        median = float(statistics.median(scores))
        output.append(
            {
                "evaluation_type": "Human",
                "metric": criterion,
                "repair_method": method,
                "model": model,
                "value": format_score(median),
                "count": len(scores),
                "denominator": len(scores),
                "formatted_value": format_score(median),
            }
        )

    return output


def build_wide_rows(long_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    values = {
        (
            str(row["evaluation_type"]),
            str(row["metric"]),
            str(row["repair_method"]),
            str(row["model"]),
        ): str(row["formatted_value"])
        for row in long_rows
    }
    output: list[dict[str, object]] = []
    metric_groups = (
        ("Automatic", ("Syntactic", "Structural")),
        ("Human", CRITERION_ORDER),
    )
    for evaluation_type, metrics in metric_groups:
        for metric in metrics:
            row: dict[str, object] = {
                "evaluation_type": evaluation_type,
                "metric": metric,
            }
            for method in METHOD_ORDER:
                for model in MODEL_ORDER:
                    column = f"{method} - {model}"
                    row[column] = values.get(
                        (evaluation_type, metric, method, model),
                        "",
                    )
            output.append(row)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Baseline versus Syntax-Grounded repair table using freshly "
            "validated automatic scores and the final human-reference scores."
        )
    )
    parser.add_argument("--validity-csv", type=Path, default=DEFAULT_VALIDITY_CSV)
    parser.add_argument("--human-csv", type=Path, default=DEFAULT_HUMAN_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    long_rows = build_rows(read_csv(args.validity_csv), read_csv(args.human_csv))
    wide_rows = build_wide_rows(long_rows)

    long_path = args.output_dir / "baseline_vs_syntax_grounded_values_long.csv"
    wide_path = args.output_dir / "baseline_vs_syntax_grounded_table.csv"
    long_fields = [
        "evaluation_type",
        "metric",
        "repair_method",
        "model",
        "value",
        "count",
        "denominator",
        "formatted_value",
    ]
    wide_fields = [
        "evaluation_type",
        "metric",
        *[
            f"{method} - {model}"
            for method in METHOD_ORDER
            for model in MODEL_ORDER
        ],
    ]
    write_csv(long_path, long_fields, long_rows)
    write_csv(wide_path, wide_fields, wide_rows)

    print(f"Saved: {wide_path}")
    print(f"Saved: {long_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
