from __future__ import annotations

import argparse
import csv
from pathlib import Path

from plantuml_pipeline.dataset import load_cases
from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.io_utils import read_text
from plantuml_pipeline.metrics import compute_metrics
from plantuml_pipeline.parser import parse_and_validate_puml_text


DEFAULT_RUN_FOLDERS = [
    "open_source__qwen25_7b_instruct__rag",
    "open_source__mistral__rag",
    "open_source__deepseek_r1_14b__few_shot",
    "open_source__llama31_8b_instruct__few_shot",
]


DISPLAY_NAMES = {
    "open_source__qwen25_7b_instruct__rag": ("Qwen_2.5_7B", "rag"),
    "open_source__mistral__rag": ("Mistral", "rag"),
    "open_source__deepseek_r1_14b__few_shot": ("DeepSeek_R1_14B", "few_shot"),
    "open_source__llama31_8b_instruct__few_shot": ("Llama_3.1_8B", "few_shot"),
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freshly recompute syntax validity, strict structural validity, and F1 metrics from run_01.puml files."
    )
    parser.add_argument("--dataset-root", default="dataset")
    parser.add_argument(
        "--results-root",
        action="append",
        required=True,
        help="Results root containing a runs/ directory. Repeatable.",
    )
    parser.add_argument(
        "--run-folder",
        action="append",
        default=[],
        help="Specific run folder name under runs/. Repeatable. Defaults to the 4 selected raw folders.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/plantuml_pipeline/fresh_recomputed_metrics",
        help="Directory for output CSV files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    dataset_root = Path(args.dataset_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = {case.case_id: case for case in load_cases(dataset_root)}
    run_folders = args.run_folder or list(DEFAULT_RUN_FOLDERS)

    per_case_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for results_root_arg in args.results_root:
        results_root = Path(results_root_arg)
        runs_root = results_root / "runs"
        results_set = results_root.name

        for run_folder in run_folders:
            run_dir = runs_root / run_folder
            if not run_dir.exists():
                continue

            llm_name, method_name = DISPLAY_NAMES.get(run_folder, (run_folder, "unknown"))
            folder_case_rows: list[dict[str, object]] = []

            for case_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("case_")):
                puml_path = case_dir / "run_01.puml"
                if not puml_path.exists():
                    continue
                case = cases.get(case_dir.name)
                if case is None:
                    continue

                pred_puml = read_text(puml_path)
                pred_graph, pred_validation = parse_and_validate_puml_text(pred_puml)
                metrics = compute_metrics(pred_graph, pred_validation, case.gold_graph)
                syntax_valid = bool(pred_validation.valid)
                structural_valid = bool(is_strict_state_diagram_valid(pred_validation))

                row = {
                    "results_set": results_set,
                    "llm_name": llm_name,
                    "method_name": method_name,
                    "run_folder": run_folder,
                    "case_id": case.case_id,
                    "syntax_valid": syntax_valid,
                    "structural_valid": structural_valid,
                    "state_f1_exact": float(metrics["state_f1"]),
                    "transition_f1_exact": float(metrics["transition_f1"]),
                    "overall_f1_exact": float(metrics["overall_f1"]),
                    "state_f1_relaxed": float(metrics["state_f1_relaxed"]),
                    "transition_f1_relaxed": float(metrics["transition_f1_relaxed"]),
                    "overall_f1_relaxed": float(metrics["overall_f1_relaxed"]),
                }
                per_case_rows.append(row)
                folder_case_rows.append(row)

            if not folder_case_rows:
                continue

            summary_rows.append(
                {
                    "results_set": results_set,
                    "llm_name": llm_name,
                    "method_name": method_name,
                    "run_folder": run_folder,
                    "cases": len(folder_case_rows),
                    "mean_state_f1_exact": _mean([float(r["state_f1_exact"]) for r in folder_case_rows]),
                    "mean_transition_f1_exact": _mean([float(r["transition_f1_exact"]) for r in folder_case_rows]),
                    "mean_overall_f1_exact": _mean([float(r["overall_f1_exact"]) for r in folder_case_rows]),
                    "mean_state_f1_relaxed": _mean([float(r["state_f1_relaxed"]) for r in folder_case_rows]),
                    "mean_transition_f1_relaxed": _mean([float(r["transition_f1_relaxed"]) for r in folder_case_rows]),
                    "mean_overall_f1_relaxed": _mean([float(r["overall_f1_relaxed"]) for r in folder_case_rows]),
                    "syntax_valid_count": sum(1 for r in folder_case_rows if bool(r["syntax_valid"])),
                    "syntax_valid_pct": 100.0
                    * sum(1 for r in folder_case_rows if bool(r["syntax_valid"]))
                    / len(folder_case_rows),
                    "structural_valid_count": sum(1 for r in folder_case_rows if bool(r["structural_valid"])),
                    "structural_valid_pct": 100.0
                    * sum(1 for r in folder_case_rows if bool(r["structural_valid"]))
                    / len(folder_case_rows),
                }
            )

    per_case_path = output_dir / "per_case_fresh_metrics.csv"
    with per_case_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_case_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_case_rows)

    summary_path = output_dir / "summary_fresh_metrics.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"Wrote per-case CSV: {per_case_path}")
    print(f"Wrote summary CSV: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
