from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _to_float(value: str) -> float:
    return float(value)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sample_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate model-level stability across repeated runs from per-case fresh metrics CSV."
        )
    )
    parser.add_argument(
        "--input-csv",
        required=True,
        help="Per-case CSV produced by recompute_run_metrics_fresh.py",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        help="Output summary CSV path",
    )
    parser.add_argument(
        "--state-f1-column",
        default="state_f1_relaxed",
        choices=["state_f1_exact", "state_f1_relaxed"],
        help="Which state F1 column to use for stability analysis",
    )
    parser.add_argument(
        "--expected-run-count",
        type=int,
        default=3,
        help="Expected number of independent runs per case/LLM",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_csv = Path(args.input_csv)
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with input_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    by_llm_run: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    by_llm_case: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))

    for row in rows:
        llm = row["llm_name"]
        run_id = row["results_set"]
        case_id = row["case_id"]
        by_llm_run[llm][run_id].append(row)
        by_llm_case[llm][case_id].append(row)

    summary_rows: list[dict[str, object]] = []

    for llm in sorted(by_llm_run):
        run_state_means: list[float] = []
        run_syntax_means: list[float] = []
        run_structural_means: list[float] = []

        for run_id in sorted(by_llm_run[llm]):
            run_rows = by_llm_run[llm][run_id]
            run_state_means.append(_mean([_to_float(r[args.state_f1_column]) for r in run_rows]))
            run_syntax_means.append(_mean([1.0 if _to_bool(r["syntax_valid"]) else 0.0 for r in run_rows]))
            run_structural_means.append(
                _mean([1.0 if _to_bool(r["structural_valid"]) else 0.0 for r in run_rows])
            )

        case_state_sds: list[float] = []
        syntax_consistent_cases = 0
        structural_consistent_cases = 0
        complete_cases = 0

        for case_id in sorted(by_llm_case[llm]):
            case_rows = by_llm_case[llm][case_id]
            distinct_runs = {r["results_set"] for r in case_rows}
            if len(distinct_runs) != args.expected_run_count:
                continue

            complete_cases += 1
            ordered = sorted(case_rows, key=lambda r: r["results_set"])
            case_state_values = [_to_float(r[args.state_f1_column]) for r in ordered]
            case_state_sds.append(_sample_sd(case_state_values))

            syntax_values = [_to_bool(r["syntax_valid"]) for r in ordered]
            structural_values = [_to_bool(r["structural_valid"]) for r in ordered]
            if len(set(syntax_values)) == 1:
                syntax_consistent_cases += 1
            if len(set(structural_values)) == 1:
                structural_consistent_cases += 1

        summary_rows.append(
            {
                "llm": llm,
                "mean_state_f1": round(_mean(run_state_means), 6),
                "state_f1_run_sd": round(_sample_sd(run_state_means), 6),
                "mean_case_state_f1_sd": round(_mean(case_state_sds), 6),
                "mean_syntax_validity": round(_mean(run_syntax_means), 6),
                "syntax_validity_sd": round(_sample_sd(run_syntax_means), 6),
                "mean_structural_validity": round(_mean(run_structural_means), 6),
                "structural_validity_sd": round(_sample_sd(run_structural_means), 6),
                "syntax_consistent_cases_percent": round(
                    (100.0 * syntax_consistent_cases / complete_cases) if complete_cases else 0.0,
                    6,
                ),
                "structural_consistent_cases_percent": round(
                    (100.0 * structural_consistent_cases / complete_cases) if complete_cases else 0.0,
                    6,
                ),
            }
        )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote model stability CSV: {output_csv}")
    for row in summary_rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
