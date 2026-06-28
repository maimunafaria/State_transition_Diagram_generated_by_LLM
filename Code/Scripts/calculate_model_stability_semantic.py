from __future__ import annotations

import argparse
import csv
import os
import statistics
from collections import defaultdict
from pathlib import Path

from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.io_utils import read_text
from plantuml_pipeline.parser import parse_and_validate_puml_text


def _normalize_candidate_path(raw_path: str) -> Path:
    return Path(raw_path.replace("\\", os.sep))


def _to_float(value: str) -> float:
    return float(value)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _sample_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calculate model-level stability from semantic state matching CSVs across independent runs."
    )
    parser.add_argument(
        "--input-set",
        action="append",
        required=True,
        help="Repeatable. Format: run_label=path/to/semantic_state_matches.csv",
    )
    parser.add_argument("--output-csv", required=True)
    parser.add_argument("--expected-run-count", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    per_case_rows: list[dict[str, object]] = []

    for input_set in args.input_set:
        if "=" not in input_set:
            raise SystemExit(f"Invalid --input-set value: {input_set}")
        run_label, csv_path_text = input_set.split("=", 1)
        csv_path = Path(csv_path_text)
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        for row in rows:
            candidate_path = _normalize_candidate_path(row["candidate_path"])
            pred_puml = read_text(candidate_path)
            _, validation = parse_and_validate_puml_text(pred_puml)

            per_case_rows.append(
                {
                    "results_set": run_label.strip(),
                    "llm": row["llm_name"].strip(),
                    "method_name": row["method_name"].strip(),
                    "case_id": row["case_id"].strip(),
                    "semantic_state_f1": _to_float(row["semantic_state_f1"]),
                    "syntax_valid": bool(validation.valid),
                    "structural_valid": bool(is_strict_state_diagram_valid(validation)),
                }
            )

    by_llm_run: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
    by_llm_case: dict[str, dict[str, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))

    for row in per_case_rows:
        by_llm_run[str(row["llm"])][str(row["results_set"])].append(row)
        by_llm_case[str(row["llm"])][str(row["case_id"])].append(row)

    summary_rows: list[dict[str, object]] = []
    for llm in sorted(by_llm_run):
        run_state_means: list[float] = []
        run_syntax_means: list[float] = []
        run_structural_means: list[float] = []

        for run_label in sorted(by_llm_run[llm]):
            run_rows = by_llm_run[llm][run_label]
            run_state_means.append(_mean([float(r["semantic_state_f1"]) for r in run_rows]))
            run_syntax_means.append(
                _mean([1.0 if bool(r["syntax_valid"]) else 0.0 for r in run_rows])
            )
            run_structural_means.append(
                _mean([1.0 if bool(r["structural_valid"]) else 0.0 for r in run_rows])
            )

        case_state_sds: list[float] = []
        syntax_consistent_cases = 0
        structural_consistent_cases = 0
        complete_cases = 0

        for case_id in sorted(by_llm_case[llm]):
            case_rows = by_llm_case[llm][case_id]
            distinct_runs = {str(r["results_set"]) for r in case_rows}
            if len(distinct_runs) != args.expected_run_count:
                continue

            complete_cases += 1
            ordered = sorted(case_rows, key=lambda r: str(r["results_set"]))
            state_values = [float(r["semantic_state_f1"]) for r in ordered]
            case_state_sds.append(_sample_sd(state_values))

            syntax_values = [bool(r["syntax_valid"]) for r in ordered]
            structural_values = [bool(r["structural_valid"]) for r in ordered]
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

    print(f"Wrote semantic model stability CSV: {output_csv}")
    for row in summary_rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
