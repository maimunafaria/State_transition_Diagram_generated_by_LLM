from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from plantuml_pipeline.dataset import load_cases
from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.io_utils import read_text
from plantuml_pipeline.parser import check_plantuml_syntax, parse_plantuml, validate_graph


RUN_SPECS = [
    ("open_source__deepseek_r1_14b__few_shot", "DeepSeek_R1_14B", "few_shot"),
    (
        "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
        "DeepSeek_R1_14B",
        "baseline_repair",
    ),
    (
        "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded",
        "DeepSeek_R1_14B",
        "syntax_grounded_repair",
    ),
    ("open_source__llama31_8b_instruct__few_shot", "Llama_3.1_8B", "few_shot"),
    (
        "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",
        "Llama_3.1_8B",
        "baseline_repair",
    ),
    (
        "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded",
        "Llama_3.1_8B",
        "syntax_grounded_repair",
    ),
    ("open_source__mistral__rag", "Mistral", "rag"),
    (
        "open_source__mistral__rag_validation_generator_critic_repair",
        "Mistral",
        "baseline_repair",
    ),
    (
        "open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded",
        "Mistral",
        "syntax_grounded_repair",
    ),
    ("open_source__qwen25_7b_instruct__rag", "Qwen_2.5_7B", "rag"),
    (
        "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
        "Qwen_2.5_7B",
        "baseline_repair",
    ),
    (
        "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag",
        "Qwen_2.5_7B",
        "syntax_grounded_repair",
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fresh-validate untitled-folder run outputs and copy strictly valid diagrams into a clean folder structure."
    )
    parser.add_argument(
        "--runs-root",
        default="Code/untitled folder/results/plantuml_pipeline/runs",
        help="Runs root under the untitled-folder experiment.",
    )
    parser.add_argument("--dataset-root", default="dataset")
    parser.add_argument(
        "--output-dir",
        default="valid_diagrams_from_untitled",
        help="Target directory for copied valid diagrams.",
    )
    parser.add_argument(
        "--syntax-timeout",
        type=int,
        default=2,
        help="Seconds to allow for official PlantUML syntax check per diagram.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    runs_root = Path(args.runs_root)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = {case.case_id: case for case in load_cases(Path(args.dataset_root))}

    summary_rows: list[dict[str, object]] = []
    per_case_rows: list[dict[str, object]] = []

    for run_folder, llm_name, method_name in RUN_SPECS:
        run_dir = runs_root / run_folder
        if not run_dir.exists():
            continue

        total_cases = 0
        valid_cases = 0

        for case_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("case_")):
            puml_path = case_dir / "run_01.puml"
            if not puml_path.exists():
                continue
            total_cases += 1

            case = cases.get(case_dir.name)
            if case is None:
                continue

            puml_text = read_text(puml_path)
            graph = parse_plantuml(puml_text)
            validation = validate_graph(graph)
            structural_valid = bool(is_strict_state_diagram_valid(validation))

            syntax_errors: list[str] = []
            syntax_warnings: list[str] = []
            if structural_valid:
                syntax_errors, syntax_warnings = check_plantuml_syntax(puml_text, timeout=args.syntax_timeout)
                if syntax_errors:
                    validation.errors = syntax_errors
                    validation.valid = False
                else:
                    validation.errors = []
                    validation.valid = True
                if syntax_warnings:
                    validation.warnings.extend(syntax_warnings)
            else:
                validation.valid = False
                validation.errors = ["not_checked_due_to_structural_invalidity"]

            syntax_valid = bool(validation.valid)

            per_case_rows.append(
                {
                    "llm_name": llm_name,
                    "method_name": method_name,
                    "run_folder": run_folder,
                    "case_id": case.case_id,
                    "syntax_valid": syntax_valid,
                    "structural_valid": structural_valid,
                    "state_count": validation.state_count,
                    "transition_count": validation.transition_count,
                    "error_count": len(validation.errors),
                    "warning_count": len(validation.warnings),
                }
            )

            if not structural_valid or not syntax_valid:
                continue

            valid_cases += 1
            target_case_dir = output_dir / llm_name / method_name / case.case_id
            target_case_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(puml_path, target_case_dir / "diagram.puml")
            (target_case_dir / "requirement.txt").write_text(
                case.structured_requirement,
                encoding="utf-8",
            )
            (target_case_dir / "structured_requirement.txt").write_text(
                case.structured_requirement,
                encoding="utf-8",
            )
            (target_case_dir / "raw_requirement.txt").write_text(
                case.raw_requirement,
                encoding="utf-8",
            )
            (target_case_dir / "source_run_id.txt").write_text(run_folder + "\n", encoding="utf-8")

        summary_rows.append(
            {
                "llm_name": llm_name,
                "method_name": method_name,
                "run_folder": run_folder,
                "total_cases": total_cases,
                "strict_valid_count": valid_cases,
                "strict_valid_percent": (100.0 * valid_cases / total_cases) if total_cases else 0.0,
            }
        )

    summary_csv = output_dir / "valid_diagram_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    per_case_csv = output_dir / "valid_diagram_per_case.csv"
    with per_case_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_case_rows[0].keys()))
        writer.writeheader()
        writer.writerows(per_case_rows)

    readme_lines = [
        "Strictly valid diagrams copied from Code/untitled folder/results/plantuml_pipeline/runs",
        "Validation was recomputed fresh using parse_and_validate_puml_text + is_strict_state_diagram_valid.",
        "",
        "Files per case folder:",
        "- diagram.puml",
        "- requirement.txt (structured requirement used for judging)",
        "- structured_requirement.txt",
        "- raw_requirement.txt",
        "- source_run_id.txt",
    ]
    (output_dir / "README.txt").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    print(f"Wrote summary CSV: {summary_csv}")
    print(f"Wrote per-case CSV: {per_case_csv}")
    print(f"Copied valid diagrams into: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
