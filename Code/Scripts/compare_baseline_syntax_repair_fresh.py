from __future__ import annotations

import argparse
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.parser import parse_and_validate_puml_text
from validate_run_folder_fresh import configure_plantuml


DEFAULT_REPAIR_FOLDERS = {
    "Qwen 2.5 7B": {
        "baseline": "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
        "syntax_grounded": (
            "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair"
            "__syntax_grounded_no_rules_original_rag"
        ),
    },
    "Mistral": {
        "baseline": "open_source__mistral__rag_validation_generator_critic_repair",
        "syntax_grounded": (
            "open_source__mistral__rag_validation_generator_critic_repair"
            "__syntax_grounded"
        ),
    },
    "DeepSeek R1 14B": {
        "baseline": (
            "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair"
        ),
        "syntax_grounded": (
            "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair"
            "__syntax_grounded_no_rules"
        ),
    },
    "Llama 3.1 8B": {
        "baseline": (
            "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair"
        ),
        "syntax_grounded": (
            "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair"
            "__syntax_grounded"
        ),
    },
}

ISSUE_LABELS = {
    "missing_final_transition": "Missing final transition",
    "missing_initial_transition": "Missing initial transition",
    "multiple_initial_transitions": "Multiple initial transitions",
    "unreachable_states": "Unreachable states",
    "orphan_states": "Orphan states",
    "plantuml_syntax_error": "PlantUML syntax error",
    "duplicate_transitions": "Duplicate transitions",
    "choice_without_outgoing_paths": "Choice without outgoing paths",
    "choice_without_guards": "Choice without guards",
    "invalid_initial_to_final": "Invalid [*] -> [*]",
    "fork_without_multiple_outgoing": "Fork without multiple outgoing branches",
    "join_without_multiple_incoming": "Join without multiple incoming branches",
    "history_without_composite": "History state without composite state",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freshly compare baseline and syntax-grounded repair validity and "
            "violation-resolution rates across the selected four LLMs."
        )
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=Path("final_results/runs"),
        help="Folder containing the repair run folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("final_results/recalculated_repair_analysis"),
        help="Destination for analysis CSV files.",
    )
    parser.add_argument(
        "--plantuml-jar",
        type=Path,
        help="Optional path to plantuml.jar when the plantuml command is unavailable.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of diagrams to validate concurrently (default: 4).",
    )
    return parser


def normalize_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def issue_types(errors: list[str], warnings: list[str]) -> set[str]:
    found: set[str] = set()
    for issue in [*errors, *warnings]:
        text = issue.strip().lower()
        if "invalid [*] -> [*] transition" in text:
            found.add("invalid_initial_to_final")
        elif text.startswith("missing_initial_state_transition"):
            found.add("missing_initial_transition")
        elif text.startswith("multiple_initial_state_transitions"):
            found.add("multiple_initial_transitions")
        elif text.startswith("missing_final_state_transition"):
            found.add("missing_final_transition")
        elif text.startswith("duplicate_transitions_detected"):
            found.add("duplicate_transitions")
        elif text.startswith("unreachable_states_detected"):
            found.add("unreachable_states")
        elif text.startswith("orphan_states_detected"):
            found.add("orphan_states")
        elif text.startswith("choice_node_without_outgoing_transitions"):
            found.add("choice_without_outgoing_paths")
        elif text.startswith("choice_node_without_guarded_outgoing_transitions"):
            found.add("choice_without_guards")
        elif text.startswith("fork_without_multiple_outgoing_branches"):
            found.add("fork_without_multiple_outgoing")
        elif text.startswith("join_without_multiple_incoming_branches"):
            found.add("join_without_multiple_incoming")
        elif text.startswith("history_state_used_without_composite_state"):
            found.add("history_without_composite")
        elif text.startswith("plantuml_syntax_error"):
            found.add("plantuml_syntax_error")
        elif text.startswith(("unreachable:", "orphan:")):
            continue
        elif text.startswith("plantuml_command_not_found"):
            raise RuntimeError(
                "Official PlantUML compiler is unavailable; validity cannot be calculated."
            )
    return found


def validate_path(path: Path) -> dict[str, object]:
    _, validation = parse_and_validate_puml_text(
        path.read_text(encoding="utf-8")
    )
    return {
        "syntax_valid": bool(validation.valid),
        "structural_valid": bool(is_strict_state_diagram_valid(validation)),
        "issues": issue_types(list(validation.errors), list(validation.warnings)),
        "errors": list(validation.errors),
        "warnings": list(validation.warnings),
    }


def percentage(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = build_parser().parse_args()
    configure_plantuml(args.plantuml_jar)

    runs_root = args.runs_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not runs_root.is_dir():
        raise SystemExit(f"Runs root not found: {runs_root}")

    work_items: list[tuple[str, str, str, Path]] = []
    comparison_cases: list[tuple[str, str, Path, Path, Path, Path]] = []

    for model, folders in DEFAULT_REPAIR_FOLDERS.items():
        baseline_dir = runs_root / folders["baseline"]
        syntax_dir = runs_root / folders["syntax_grounded"]
        for run_dir in (baseline_dir, syntax_dir):
            if not run_dir.is_dir():
                raise SystemExit(f"Required repair folder not found: {run_dir}")

        baseline_cases = {
            path.name: path
            for path in baseline_dir.iterdir()
            if path.is_dir() and path.name.startswith("case_")
        }
        syntax_cases = {
            path.name: path
            for path in syntax_dir.iterdir()
            if path.is_dir() and path.name.startswith("case_")
        }
        if set(baseline_cases) != set(syntax_cases):
            raise SystemExit(f"Case-set mismatch for {model}")

        for case_id in sorted(baseline_cases):
            baseline_case = baseline_cases[case_id]
            syntax_case = syntax_cases[case_id]
            baseline_initial = baseline_case / "run_01.initial.puml"
            syntax_initial = syntax_case / "run_01.initial.puml"
            baseline_final = baseline_case / "run_01.puml"
            syntax_final = syntax_case / "run_01.puml"
            required = (
                baseline_initial,
                syntax_initial,
                baseline_final,
                syntax_final,
            )
            missing = [str(path) for path in required if not path.is_file()]
            if missing:
                raise SystemExit("Missing required files:\n" + "\n".join(missing))
            if normalize_text(baseline_initial) != normalize_text(syntax_initial):
                raise SystemExit(
                    f"Initial diagram mismatch for {model}/{case_id}; "
                    "the comparison is not controlled."
                )

            comparison_cases.append(
                (
                    model,
                    case_id,
                    baseline_initial,
                    syntax_initial,
                    baseline_final,
                    syntax_final,
                )
            )
            work_items.extend(
                [
                    (model, case_id, "initial", baseline_initial),
                    (model, case_id, "baseline", baseline_final),
                    (model, case_id, "syntax_grounded", syntax_final),
                ]
            )

    def run_item(
        item: tuple[str, str, str, Path]
    ) -> tuple[tuple[str, str, str], dict[str, object]]:
        model, case_id, stage, path = item
        return (model, case_id, stage), validate_path(path)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        validated = dict(executor.map(run_item, work_items))

    detail_rows: list[dict[str, object]] = []
    validity_counts: dict[tuple[str, str], Counter[str]] = {}
    initial_counts: Counter[str] = Counter()
    solved_counts: dict[str, Counter[str]] = {
        "baseline": Counter(),
        "syntax_grounded": Counter(),
    }
    new_counts: dict[str, Counter[str]] = {
        "baseline": Counter(),
        "syntax_grounded": Counter(),
    }
    by_model_initial: dict[str, Counter[str]] = {}
    by_model_solved: dict[tuple[str, str], Counter[str]] = {}

    for model, case_id, *_paths in comparison_cases:
        initial = validated[(model, case_id, "initial")]
        initial_issues = set(initial["issues"])
        by_model_initial.setdefault(model, Counter())
        for issue in initial_issues:
            initial_counts[issue] += 1
            by_model_initial[model][issue] += 1

        for method in ("baseline", "syntax_grounded"):
            final = validated[(model, case_id, method)]
            final_issues = set(final["issues"])
            validity_counts.setdefault((model, method), Counter())
            validity_counts[(model, method)]["total"] += 1
            validity_counts[(model, method)]["syntax_valid"] += int(
                bool(final["syntax_valid"])
            )
            validity_counts[(model, method)]["structural_valid"] += int(
                bool(final["structural_valid"])
            )
            by_model_solved.setdefault((model, method), Counter())

            eliminated = initial_issues - final_issues
            introduced = final_issues - initial_issues
            for issue in eliminated:
                solved_counts[method][issue] += 1
                by_model_solved[(model, method)][issue] += 1
            for issue in introduced:
                new_counts[method][issue] += 1

            detail_rows.append(
                {
                    "model": model,
                    "case_id": case_id,
                    "repair_method": method,
                    "initial_issues": ";".join(sorted(initial_issues)),
                    "final_issues": ";".join(sorted(final_issues)),
                    "solved_issues": ";".join(sorted(eliminated)),
                    "new_issues": ";".join(sorted(introduced)),
                    "syntax_valid": bool(final["syntax_valid"]),
                    "structural_valid": bool(final["structural_valid"]),
                }
            )

    validity_rows: list[dict[str, object]] = []
    for model in DEFAULT_REPAIR_FOLDERS:
        for method in ("baseline", "syntax_grounded"):
            counts = validity_counts[(model, method)]
            total = counts["total"]
            validity_rows.append(
                {
                    "model": model,
                    "repair_method": method,
                    "cases": total,
                    "syntax_valid_count": counts["syntax_valid"],
                    "syntax_valid_percent": round(
                        percentage(counts["syntax_valid"], total), 2
                    ),
                    "structural_valid_count": counts["structural_valid"],
                    "structural_valid_percent": round(
                        percentage(counts["structural_valid"], total), 2
                    ),
                }
            )

    for method in ("baseline", "syntax_grounded"):
        method_rows = [
            row for row in validity_rows if row["repair_method"] == method
        ]
        total = sum(int(row["cases"]) for row in method_rows)
        syntax_count = sum(int(row["syntax_valid_count"]) for row in method_rows)
        structural_count = sum(
            int(row["structural_valid_count"]) for row in method_rows
        )
        validity_rows.append(
            {
                "model": "Overall",
                "repair_method": method,
                "cases": total,
                "syntax_valid_count": syntax_count,
                "syntax_valid_percent": round(percentage(syntax_count, total), 2),
                "structural_valid_count": structural_count,
                "structural_valid_percent": round(
                    percentage(structural_count, total), 2
                ),
            }
        )

    issue_order = [
        issue for issue in ISSUE_LABELS if initial_counts.get(issue, 0) > 0
    ]
    issue_rows: list[dict[str, object]] = []
    for issue in issue_order:
        initial = initial_counts[issue]
        baseline_solved = solved_counts["baseline"][issue]
        syntax_solved = solved_counts["syntax_grounded"][issue]
        better = (
            "Baseline"
            if baseline_solved > syntax_solved
            else "Syntax-Grounded"
            if syntax_solved > baseline_solved
            else "Tie"
        )
        issue_rows.append(
            {
                "error_type": ISSUE_LABELS[issue],
                "initial_occurrences": initial,
                "baseline_solved": baseline_solved,
                "baseline_solved_percent": round(
                    percentage(baseline_solved, initial), 2
                ),
                "syntax_grounded_solved": syntax_solved,
                "syntax_grounded_solved_percent": round(
                    percentage(syntax_solved, initial), 2
                ),
                "better_method": better,
            }
        )

    total_initial = sum(initial_counts.values())
    total_baseline_solved = sum(solved_counts["baseline"].values())
    total_syntax_solved = sum(solved_counts["syntax_grounded"].values())
    issue_rows.append(
        {
            "error_type": "Overall error resolution",
            "initial_occurrences": total_initial,
            "baseline_solved": total_baseline_solved,
            "baseline_solved_percent": round(
                percentage(total_baseline_solved, total_initial), 2
            ),
            "syntax_grounded_solved": total_syntax_solved,
            "syntax_grounded_solved_percent": round(
                percentage(total_syntax_solved, total_initial), 2
            ),
            "better_method": (
                "Baseline"
                if total_baseline_solved > total_syntax_solved
                else "Syntax-Grounded"
                if total_syntax_solved > total_baseline_solved
                else "Tie"
            ),
        }
    )

    overall_rows: list[dict[str, object]] = []
    solved_totals = {
        "baseline": total_baseline_solved,
        "syntax_grounded": total_syntax_solved,
    }
    for method in ("baseline", "syntax_grounded"):
        validity = next(
            row
            for row in validity_rows
            if row["model"] == "Overall"
            and row["repair_method"] == method
        )
        solved = solved_totals[method]
        overall_rows.append(
            {
                "repair": (
                    "Baseline"
                    if method == "baseline"
                    else "Syntax-Grounded"
                ),
                "strict_valid_count": validity["structural_valid_count"],
                "diagram_count": validity["cases"],
                "strict_valid_percent": validity["structural_valid_percent"],
                "errors_solved": solved,
                "initial_error_occurrences": total_initial,
                "errors_solved_percent": round(
                    percentage(solved, total_initial), 2
                ),
            }
        )

    by_model_rows: list[dict[str, object]] = []
    for model in DEFAULT_REPAIR_FOLDERS:
        for issue in issue_order:
            initial = by_model_initial[model][issue]
            if not initial:
                continue
            for method in ("baseline", "syntax_grounded"):
                solved = by_model_solved[(model, method)][issue]
                by_model_rows.append(
                    {
                        "model": model,
                        "repair_method": method,
                        "error_type": ISSUE_LABELS[issue],
                        "initial_occurrences": initial,
                        "solved": solved,
                        "solved_percent": round(
                            percentage(solved, initial), 2
                        ),
                    }
                )

    new_issue_rows: list[dict[str, object]] = []
    for issue in ISSUE_LABELS:
        baseline_new = new_counts["baseline"][issue]
        syntax_new = new_counts["syntax_grounded"][issue]
        if not baseline_new and not syntax_new:
            continue
        new_issue_rows.append(
            {
                "error_type": ISSUE_LABELS[issue],
                "baseline_new_occurrences": baseline_new,
                "syntax_grounded_new_occurrences": syntax_new,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "repair_overall_results.csv", overall_rows)
    write_csv(output_dir / "repair_validity_summary.csv", validity_rows)
    write_csv(output_dir / "repair_issue_resolution_overall.csv", issue_rows)
    write_csv(
        output_dir / "repair_issue_resolution_by_model.csv", by_model_rows
    )
    write_csv(output_dir / "repair_new_issues.csv", new_issue_rows)
    write_csv(output_dir / "repair_case_details.csv", detail_rows)

    print("\nOverall results")
    print("| Repair | Strict validity | Errors solved |")
    print("| --- | ---: | ---: |")
    for row in overall_rows:
        print(
            f"| {row['repair']} | "
            f"{row['strict_valid_count']}/{row['diagram_count']} "
            f"({row['strict_valid_percent']:.2f}%) | "
            f"{row['errors_solved']}/{row['initial_error_occurrences']} "
            f"({row['errors_solved_percent']:.2f}%) |"
        )

    print("\nFresh validity")
    print(
        "| Model | Method | Syntax validity | Strict structural validity |"
    )
    print("| --- | --- | ---: | ---: |")
    for row in validity_rows:
        print(
            f"| {row['model']} | {row['repair_method']} | "
            f"{row['syntax_valid_percent']:.2f}% "
            f"({row['syntax_valid_count']}/{row['cases']}) | "
            f"{row['structural_valid_percent']:.2f}% "
            f"({row['structural_valid_count']}/{row['cases']}) |"
        )

    print("\nRepair success by error type")
    print("| Error type | Baseline | Syntax-Grounded | Better |")
    print("| --- | ---: | ---: | --- |")
    for row in issue_rows:
        print(
            f"| {row['error_type']} | "
            f"{row['baseline_solved_percent']:.2f}% "
            f"({row['baseline_solved']}/{row['initial_occurrences']}) | "
            f"{row['syntax_grounded_solved_percent']:.2f}% "
            f"({row['syntax_grounded_solved']}/{row['initial_occurrences']}) | "
            f"{row['better_method']} |"
        )

    print(f"\nCSV output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
