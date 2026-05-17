#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any


CODE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = CODE_ROOT.parent
SCRIPTS_DIR = PROJECT_ROOT / "Code" / "Scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_structural_validity_rq import countable_violation_types, percent  # noqa: E402
from plantuml_pipeline.parser import parse_and_validate_puml_text  # noqa: E402
from report_validity_percentages import parse_run_id  # noqa: E402


DEFAULT_RUNS_ROOT = PROJECT_ROOT / "results" / "plantuml_pipeline" / "runs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "repair_effectiveness"
RUN_FILE_RE = re.compile(r"^run_(\d+)\.puml$")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def strict_valid(validation: Any) -> bool:
    return validation.valid and not (list(validation.errors) + list(validation.warnings))


def validation_issues(validation: Any) -> list[str]:
    return list(validation.errors) + list(validation.warnings)


def graph_diff(initial_graph: Any, final_graph: Any) -> dict[str, object]:
    initial_states = set(initial_graph.states)
    final_states = set(final_graph.states)
    initial_transitions = set(initial_graph.transitions)
    final_transitions = set(final_graph.transitions)
    initial_edges = {(src, dst) for src, _event, dst in initial_transitions}
    final_edges = {(src, dst) for src, _event, dst in final_transitions}

    shared_edges = initial_edges & final_edges
    modified_transition_labels = 0
    for edge in shared_edges:
        initial_events = {event for src, event, dst in initial_transitions if (src, dst) == edge}
        final_events = {event for src, event, dst in final_transitions if (src, dst) == edge}
        if initial_events != final_events:
            modified_transition_labels += 1

    added_states = final_states - initial_states
    deleted_states = initial_states - final_states
    added_transitions = final_transitions - initial_transitions
    deleted_transitions = initial_transitions - final_transitions
    added_edges = final_edges - initial_edges
    deleted_edges = initial_edges - final_edges

    return {
        "added_states_count": len(added_states),
        "deleted_states_count": len(deleted_states),
        "added_transitions_count": len(added_transitions),
        "deleted_transitions_count": len(deleted_transitions),
        "added_transition_edges_count": len(added_edges),
        "deleted_transition_edges_count": len(deleted_edges),
        "modified_transition_labels_count": modified_transition_labels,
        "total_graph_change_count": (
            len(added_states)
            + len(deleted_states)
            + len(added_transitions)
            + len(deleted_transitions)
            + modified_transition_labels
        ),
        "added_states": ";".join(sorted(added_states)),
        "deleted_states": ";".join(sorted(deleted_states)),
    }


def repair_iterations(meta: dict[str, Any], case_dir: Path) -> tuple[int, int]:
    attempts = [
        int(item.get("attempt", 0))
        for item in meta.get("attempt_artifacts", [])
        if item.get("stage") == "repair"
    ]
    attempted_iterations = max(attempts) if attempts else len(list(case_dir.glob("run_*.repair_*.puml")))

    accepted_attempts = [
        int(item.get("attempt", 0))
        for item in meta.get("attempt_artifacts", [])
        if item.get("stage") == "repair" and item.get("accepted")
    ]
    accepted_iterations = max(accepted_attempts) if accepted_attempts else attempted_iterations
    return attempted_iterations, accepted_iterations


def iter_repair_cases(runs_root: Path):
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        if "repair" not in run_dir.name:
            continue
        model, method = parse_run_id(run_dir.name)
        for final_path in sorted(run_dir.glob("*/run_*.puml")):
            if ".repair_" in final_path.name or ".initial" in final_path.name:
                continue
            if not RUN_FILE_RE.match(final_path.name):
                continue
            initial_path = final_path.with_name(final_path.stem + ".initial.puml")
            meta_path = final_path.with_suffix(".meta.json")
            if not initial_path.exists() or not meta_path.exists():
                continue
            yield run_dir.name, model, method, final_path.parent.name, initial_path, final_path, meta_path


def build_repair_rows(runs_root: Path, official_syntax: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run_id, model, method, case_id, initial_path, final_path, meta_path in iter_repair_cases(runs_root):
        meta = read_json(meta_path)
        initial_graph, initial_validation = parse_and_validate_puml_text(
            initial_path.read_text(encoding="utf-8"),
            official_syntax=official_syntax,
        )
        final_graph, final_validation = parse_and_validate_puml_text(
            final_path.read_text(encoding="utf-8"),
            official_syntax=official_syntax,
        )

        initial_issue_types = countable_violation_types(validation_issues(initial_validation))
        final_issue_types = countable_violation_types(validation_issues(final_validation))
        initial_issue_set = set(initial_issue_types)
        final_issue_set = set(final_issue_types)
        new_issue_types = sorted(final_issue_set - initial_issue_set)
        eliminated_issue_types = sorted(initial_issue_set - final_issue_set)
        attempted_iterations, accepted_iterations = repair_iterations(meta, final_path.parent)
        diff = graph_diff(initial_graph, final_graph)

        initial_strict_valid = strict_valid(initial_validation)
        final_strict_valid = strict_valid(final_validation)
        initial_count = len(initial_issue_types)
        final_count = len(final_issue_types)

        rows.append(
            {
                "model": model,
                "method": method,
                "run_id": run_id,
                "case_id": case_id,
                "initial_plantuml_valid": initial_validation.valid,
                "final_plantuml_valid": final_validation.valid,
                "initial_structural_valid": initial_strict_valid,
                "final_structural_valid": final_strict_valid,
                "repair_success": final_strict_valid,
                "validity_recovered": (not initial_strict_valid) and final_strict_valid,
                "structurally_improved": final_count < initial_count,
                "structurally_worsened": final_count > initial_count,
                "unchanged_violation_count": final_count == initial_count,
                "initial_violation_count": initial_count,
                "final_violation_count": final_count,
                "violation_reduction": initial_count - final_count,
                "violation_reduction_percent": round(
                    ((initial_count - final_count) / initial_count * 100.0), 2
                )
                if initial_count
                else 0.0,
                "regressed_new_violation_type": bool(new_issue_types),
                "new_violation_type_count": len(new_issue_types),
                "new_violation_types": ";".join(new_issue_types),
                "eliminated_violation_types": ";".join(eliminated_issue_types),
                "attempted_repair_iterations": attempted_iterations,
                "accepted_repair_iterations": accepted_iterations,
                "initial_path": str(initial_path),
                "final_path": str(final_path),
                **diff,
            }
        )
    return rows


def summarize(rows: list[dict[str, object]], group_fields: tuple[str, ...]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[field] for field in group_fields)].append(row)

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        group_rows = grouped[key]
        total = len(group_rows)
        initial_invalid_rows = [
            row for row in group_rows if not bool(row["initial_structural_valid"])
        ]
        initial_invalid_total = len(initial_invalid_rows)
        repair_success = sum(1 for row in group_rows if bool(row["repair_success"]))
        recovered = sum(1 for row in group_rows if bool(row["validity_recovered"]))
        improved = sum(1 for row in group_rows if bool(row["structurally_improved"]))
        regressed = sum(1 for row in group_rows if bool(row["regressed_new_violation_type"]))
        initial_counts = [int(row["initial_violation_count"]) for row in group_rows]
        final_counts = [int(row["final_violation_count"]) for row in group_rows]
        reductions = [int(row["violation_reduction"]) for row in group_rows]

        output.append(
            {
                **dict(zip(group_fields, key)),
                "total": total,
                "initial_invalid": initial_invalid_total,
                "repair_success": repair_success,
                "repair_success_rate": percent(repair_success, total),
                "validity_recovered": recovered,
                "validity_recovery_rate": percent(recovered, initial_invalid_total),
                "structurally_improved": improved,
                "structural_improvement_rate": percent(improved, total),
                "regressed_new_violation_type": regressed,
                "regression_rate": percent(regressed, total),
                "mean_initial_violations": round(mean(initial_counts), 4) if initial_counts else 0.0,
                "mean_final_violations": round(mean(final_counts), 4) if final_counts else 0.0,
                "mean_violation_reduction": round(mean(reductions), 4) if reductions else 0.0,
                "median_violation_reduction": round(median(reductions), 4) if reductions else 0.0,
                "mean_attempted_repair_iterations": round(
                    mean(int(row["attempted_repair_iterations"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_accepted_repair_iterations": round(
                    mean(int(row["accepted_repair_iterations"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_added_states": round(
                    mean(int(row["added_states_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_deleted_states": round(
                    mean(int(row["deleted_states_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_added_transitions": round(
                    mean(int(row["added_transitions_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_deleted_transitions": round(
                    mean(int(row["deleted_transitions_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_modified_transition_labels": round(
                    mean(int(row["modified_transition_labels_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
                "mean_total_graph_change": round(
                    mean(int(row["total_graph_change_count"]) for row in group_rows), 4
                )
                if group_rows
                else 0.0,
            }
        )
    return output


def summarize_new_violations(rows: list[dict[str, object]], group_fields: tuple[str, ...]) -> list[dict[str, object]]:
    denominators: Counter[tuple[object, ...]] = Counter()
    counts: Counter[tuple[object, ...]] = Counter()
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        denominators[key] += 1
        for violation in str(row["new_violation_types"]).split(";"):
            if violation:
                counts[(*key, violation)] += 1

    output: list[dict[str, object]] = []
    for key, count in sorted(counts.items()):
        group_key = key[:-1]
        violation = key[-1]
        total = denominators[group_key]
        output.append(
            {
                **dict(zip(group_fields, group_key)),
                "new_violation_type": violation,
                "count": count,
                "total": total,
                "frequency_percent": percent(count, total),
            }
        )
    return output


def write_markdown_summary(
    path: Path,
    by_model_method_rows: list[dict[str, object]],
) -> None:
    def table(rows: list[dict[str, object]], fields: list[str]) -> str:
        lines = [
            "| " + " | ".join(fields) + " |",
            "| " + " | ".join("---" for _ in fields) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
        return "\n".join(lines)

    path.parent.mkdir(parents=True, exist_ok=True)
    content = [
        "# Repair Effectiveness Analysis",
        "",
        "Repair success is final strict structural validity. Validity recovery is invalid-to-valid transition. Regression means the final diagram introduced at least one violation type not present initially.",
        "",
        "## By LLM and Method",
        table(
            by_model_method_rows,
            [
                "model",
                "method",
                "total",
                "repair_success_rate",
                "structural_improvement_rate",
                "validity_recovery_rate",
                "regression_rate",
                "mean_attempted_repair_iterations",
                "mean_violation_reduction",
                "mean_total_graph_change",
            ],
        ),
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze repair effectiveness, regressions, and graph-change minimality."
    )
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--official-syntax",
        action="store_true",
        help="Also run plantuml -checkonly for initial/final files. Slower.",
    )
    args = parser.parse_args()

    rows = build_repair_rows(args.runs_root.resolve(), official_syntax=args.official_syntax)
    output_dir = args.output_dir.resolve()

    by_model_method_rows = summarize(rows, ("model", "method"))
    new_violation_by_model_rows = summarize_new_violations(rows, ("model", "method"))

    detail_fields = [
        "model",
        "method",
        "run_id",
        "case_id",
        "initial_plantuml_valid",
        "final_plantuml_valid",
        "initial_structural_valid",
        "final_structural_valid",
        "repair_success",
        "validity_recovered",
        "structurally_improved",
        "structurally_worsened",
        "unchanged_violation_count",
        "initial_violation_count",
        "final_violation_count",
        "violation_reduction",
        "violation_reduction_percent",
        "regressed_new_violation_type",
        "new_violation_type_count",
        "new_violation_types",
        "eliminated_violation_types",
        "attempted_repair_iterations",
        "accepted_repair_iterations",
        "added_states_count",
        "deleted_states_count",
        "added_transitions_count",
        "deleted_transitions_count",
        "added_transition_edges_count",
        "deleted_transition_edges_count",
        "modified_transition_labels_count",
        "total_graph_change_count",
        "added_states",
        "deleted_states",
        "initial_path",
        "final_path",
    ]
    by_model_fields = [
        "model",
        "method",
        "total",
        "initial_invalid",
        "repair_success",
        "repair_success_rate",
        "validity_recovered",
        "validity_recovery_rate",
        "structurally_improved",
        "structural_improvement_rate",
        "regressed_new_violation_type",
        "regression_rate",
        "mean_initial_violations",
        "mean_final_violations",
        "mean_violation_reduction",
        "median_violation_reduction",
        "mean_attempted_repair_iterations",
        "mean_accepted_repair_iterations",
        "mean_added_states",
        "mean_deleted_states",
        "mean_added_transitions",
        "mean_deleted_transitions",
        "mean_modified_transition_labels",
        "mean_total_graph_change",
    ]

    write_csv(output_dir / "repair_detail.csv", rows, detail_fields)
    write_csv(
        output_dir / "repair_summary_by_model_method.csv",
        by_model_method_rows,
        by_model_fields,
    )
    write_csv(
        output_dir / "repair_new_violation_types_by_model_method.csv",
        new_violation_by_model_rows,
        ["model", "method", "new_violation_type", "count", "total", "frequency_percent"],
    )
    write_markdown_summary(output_dir / "summary.md", by_model_method_rows)

    print(f"Wrote repair effectiveness analysis to: {output_dir}")
    print(f"Summary: {output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
