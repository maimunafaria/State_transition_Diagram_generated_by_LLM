from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INSTRUCTION = (
    "Repair the PlantUML state diagram based on the validation errors. "
    "Do not add unsupported behavior. Output only valid PlantUML."
)


RULES_BY_ISSUE = {
    "plantuml_syntax_error": (
        "The repaired diagram must use valid PlantUML syntax and compile "
        "without errors while preserving supported behavior."
    ),
    "missing_initial_state_transition": (
        "A valid state diagram must include exactly one top-level initial "
        "transition from [*] to the first lifecycle state."
    ),
    "multiple_initial_state_transitions": (
        "A valid state diagram should have one clear top-level initial "
        "transition. Remove or restructure extra top-level [*] transitions."
    ),
    "missing_final_state_transition": (
        "A valid state diagram must include at least one final transition "
        "from a natural terminal state to [*]."
    ),
    "invalid_initial_to_final_transition": (
        "Do not connect [*] directly to [*]. Use a real lifecycle state "
        "between the initial and final pseudostates."
    ),
    "orphan_state": (
        "Every requirement-supported state must have reasonable incoming "
        "or outgoing transitions. Unsupported orphan states should be omitted."
    ),
    "unreachable_state": (
        "Every modeled state must be reachable from the initial lifecycle path."
    ),
    "duplicate_transitions_detected": (
        "Duplicate transitions should be removed or merged into one transition "
        "with a clear label."
    ),
    "choice_without_outgoing": (
        "Every choice node must have outgoing alternatives."
    ),
    "choice_without_guard": (
        "Choice-node outgoing transitions should use guarded labels such as "
        "[valid] and [invalid]."
    ),
    "fork_without_multiple_outgoing": (
        "Use fork nodes only when splitting into multiple outgoing branches."
    ),
    "join_without_multiple_incoming": (
        "Use join nodes only when merging multiple incoming branches."
    ),
    "history_state_used_without_composite_state": (
        "History states [H] or [H*] should only be used inside composite states."
    ),
    "nested_initial_transition": (
        "When modeling nested behavior, avoid unnecessary extra [*] transitions "
        "inside composite states; connect the parent state to the first child "
        "state when appropriate."
    ),
}


ISSUE_ALIASES = {
    "invalid_[*]_to_[*]": "invalid_initial_to_final_transition",
    "invalid_\\[\\*\\]_to_\\[\\*\\]": "invalid_initial_to_final_transition",
    "choice_nodes_without_outgoing_transitions": "choice_without_outgoing",
    "choice_nodes_without_guarded_transitions": "choice_without_guard",
    "fork_join_misuse": "fork_without_multiple_outgoing",
    "history_state_without_composite": "history_state_used_without_composite_state",
}


LLM_LABELS = {
    "qwen25_7b_instruct": "Qwen 2.5 7B Instruct",
    "gemma3_12b": "Gemma 3 12B",
    "mistral": "Mistral",
    "deepseek_r1_14b": "DeepSeek R1 14B",
    "llama31_8b_instruct": "Llama 3.1 8B Instruct",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def parse_run_id(run_id: str) -> dict[str, str]:
    parts = run_id.split("__")
    model_tag = parts[1] if len(parts) > 1 else ""
    strategy = parts[2] if len(parts) > 2 else ""
    repair_variant = parts[3] if len(parts) > 3 else "baseline"

    method = strategy
    marker = "_validation_generator_critic_repair"
    if marker in method:
        method = method.replace(marker, "")

    return {
        "source_llm": LLM_LABELS.get(model_tag, model_tag),
        "source_llm_tag": model_tag,
        "source_method": method,
        "source_repair_variant": repair_variant,
    }


def normalize_issue(issue: str) -> str:
    issue = issue.strip()
    if issue.lower().startswith("plantuml_syntax_error"):
        return "plantuml_syntax_error"
    issue = re.sub(r"\s*\(.*?\)\s*$", "", issue)
    issue = issue.replace(" ", "_").lower()
    if issue.startswith("orphan"):
        return "orphan_state"
    if issue.startswith("unreachable"):
        return "unreachable_state"
    if issue.startswith("duplicate"):
        return "duplicate_transitions_detected"
    if "[*]" in issue and "[*]" in issue.replace("[*]", "", 1):
        return "invalid_initial_to_final_transition"
    if "missing_initial" in issue:
        return "missing_initial_state_transition"
    if "missing_final" in issue:
        return "missing_final_state_transition"
    if "multiple_initial" in issue:
        return "multiple_initial_state_transitions"
    if "choice" in issue and "outgoing" in issue:
        return "choice_without_outgoing"
    if "choice" in issue and "guard" in issue:
        return "choice_without_guard"
    if "fork" in issue:
        return "fork_without_multiple_outgoing"
    if "join" in issue:
        return "join_without_multiple_incoming"
    if "history" in issue:
        return "history_state_used_without_composite_state"
    return ISSUE_ALIASES.get(issue, issue)


def issue_names_from_validation(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return []
    raw_issues: list[str] = []
    for key in ("issues", "errors", "warnings"):
        values = validation.get(key) or []
        if isinstance(values, list):
            raw_issues.extend(str(value) for value in values)
    seen: set[str] = set()
    issues: list[str] = []
    for issue in raw_issues:
        name = normalize_issue(issue)
        if name and name not in seen:
            seen.add(name)
            issues.append(name)
    return issues


def local_artifact_path(case_dir: Path, artifact: dict[str, Any]) -> Path | None:
    raw_path = artifact.get("path")
    if not raw_path:
        return None
    filename = Path(str(raw_path).replace("\\", "/")).name
    candidate = case_dir / filename
    return candidate if candidate.exists() else None


def first_invalid_artifact(meta: dict[str, Any], case_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    for artifact in meta.get("attempt_artifacts") or []:
        validation = artifact.get("validation") or {}
        strict_valid = bool(artifact.get("strict_state_diagram_valid"))
        issues = issue_names_from_validation({"issues": artifact.get("strict_issues") or []})
        if not issues:
            issues = issue_names_from_validation(validation)
        path = local_artifact_path(case_dir, artifact)
        if path and (not strict_valid or issues):
            return path, {"validation": validation, "issues": issues}

    initial_path = case_dir / "run_01.initial.puml"
    if initial_path.exists():
        steps = meta.get("processing_steps") or []
        first_step = steps[0] if steps else {}
        issues = issue_names_from_validation({"issues": first_step.get("strict_issues") or []})
        issues.extend(
            issue
            for issue in issue_names_from_validation(
                {"errors": first_step.get("errors") or [], "warnings": first_step.get("warnings") or []}
            )
            if issue not in issues
        )
        return initial_path, {"validation": {}, "issues": issues}
    return None


def artifact_issues(artifact: dict[str, Any]) -> list[str]:
    issues = issue_names_from_validation({"issues": artifact.get("strict_issues") or []})
    validation = artifact.get("validation") or {}
    for issue in issue_names_from_validation(validation):
        if issue not in issues:
            issues.append(issue)
    return issues


def artifact_sequence(meta: dict[str, Any], case_dir: Path) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    for artifact in meta.get("attempt_artifacts") or []:
        path = local_artifact_path(case_dir, artifact)
        if not path:
            continue
        sequence.append(
            {
                "stage": artifact.get("stage"),
                "attempt": artifact.get("attempt"),
                "path": path,
                "issues": artifact_issues(artifact),
                "strict_valid": bool(artifact.get("strict_state_diagram_valid")),
            }
        )

    final_path = final_repaired_path(case_dir)
    if final_path and not any(item["path"] == final_path for item in sequence):
        final_issues = issue_names_from_validation(meta.get("strict_validation") or {})
        for issue in issue_names_from_validation(meta.get("validation") or {}):
            if issue not in final_issues:
                final_issues.append(issue)
        sequence.append(
            {
                "stage": "final",
                "attempt": None,
                "path": final_path,
                "issues": final_issues,
                "strict_valid": bool((meta.get("strict_validation") or {}).get("valid")),
            }
        )
    return sequence


def final_repaired_path(case_dir: Path) -> Path | None:
    final_path = case_dir / "run_01.puml"
    return final_path if final_path.exists() else None


def requirement_text(dataset_root: Path, case_id: str, meta: dict[str, Any]) -> str:
    if meta.get("requirement_used"):
        return str(meta["requirement_used"]).strip()

    structured = dataset_root / case_id / "structured_requirement.txt"
    raw = dataset_root / case_id / "raw_requirement.txt"
    for path in (structured, raw):
        if path.exists():
            return read_text(path)
    return ""


def relevant_rules(issues: list[str]) -> str:
    lines: list[str] = []
    for issue in issues:
        rule = RULES_BY_ISSUE.get(issue)
        if rule:
            lines.append(f"- {issue}: {rule}")
        else:
            lines.append(f"- {issue}: Repair this structural violation while preserving the requirement.")
    return "\n".join(lines) if lines else "- No specific issue name was available; repair structural validity."


def build_input(requirement: str, invalid_puml: str, issues: list[str]) -> str:
    issue_lines = "\n".join(f"- {issue}" for issue in issues) if issues else "- unknown_structural_violation"
    return (
        f"Requirement:\n{requirement.strip()}\n\n"
        f"Invalid PlantUML:\n{invalid_puml.strip()}\n\n"
        f"Validation Errors:\n{issue_lines}\n\n"
        f"Relevant Rule:\n{relevant_rules(issues)}"
    ).strip()


def iter_examples(
    dataset_root: Path,
    results_root: Path,
    run_ids: list[str],
    require_final_valid: bool,
    granularity: str,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for run_id in run_ids:
        run_dir = results_root / "runs" / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run folder not found: {run_dir}")

        for case_dir in sorted(p for p in run_dir.glob("case_*") if p.is_dir()):
            meta_path = case_dir / "run_01.meta.json"
            if not meta_path.exists():
                continue
            meta = json.loads(read_text(meta_path))
            strict_validation = meta.get("strict_validation") or {}
            if granularity == "full_case" and require_final_valid and not strict_validation.get("valid"):
                continue

            case_id = case_dir.name
            requirement = requirement_text(dataset_root, case_id, meta)
            source_meta = parse_run_id(run_id)

            if granularity == "full_case":
                invalid = first_invalid_artifact(meta, case_dir)
                repaired_path = final_repaired_path(case_dir)
                if not invalid or not repaired_path:
                    continue

                invalid_path, invalid_meta = invalid
                invalid_puml = read_text(invalid_path)
                repaired_puml = read_text(repaired_path)
                if invalid_puml == repaired_puml:
                    continue

                issues = invalid_meta.get("issues") or []
                examples.append(
                    {
                        "instruction": INSTRUCTION,
                        "input": build_input(requirement, invalid_puml, issues),
                        "output": repaired_puml,
                        "metadata": {
                            "run_id": run_id,
                            **source_meta,
                            "case_id": case_id,
                            "source_invalid_file": str(invalid_path),
                            "source_repaired_file": str(repaired_path),
                            "violation_types": issues,
                            "granularity": "full_case",
                        },
                    }
                )
                continue

            sequence = artifact_sequence(meta, case_dir)
            for before, after in zip(sequence, sequence[1:]):
                before_issues = set(before["issues"])
                after_issues = set(after["issues"])
                solved_issues = sorted(before_issues - after_issues)
                if not solved_issues:
                    continue
                invalid_puml = read_text(before["path"])
                repaired_puml = read_text(after["path"])
                if invalid_puml == repaired_puml:
                    continue
                for issue in solved_issues:
                    examples.append(
                        {
                            "instruction": INSTRUCTION,
                            "input": build_input(requirement, invalid_puml, [issue]),
                            "output": repaired_puml,
                            "metadata": {
                            "run_id": run_id,
                            **source_meta,
                            "case_id": case_id,
                                "source_invalid_file": str(before["path"]),
                                "source_repaired_file": str(after["path"]),
                                "violation_types": [issue],
                                "remaining_violations_after_repair": sorted(after_issues),
                                "granularity": "solved_violation",
                            },
                        }
                    )
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build violation-specific PlantUML repair SFT examples from repair run folders."
    )
    parser.add_argument("--dataset-root", default="dataset", type=Path)
    parser.add_argument("--results-root", default="results/plantuml_pipeline", type=Path)
    parser.add_argument(
        "--run-id",
        action="append",
        dest="run_ids",
        help="Repair run ID to export. Repeat this flag to combine multiple runs.",
    )
    parser.add_argument(
        "--all-repair-runs",
        action="store_true",
        help="Export every run folder whose run ID contains 'repair'.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--format",
        choices=("jsonl", "json"),
        default="jsonl",
        help="jsonl is convenient for inspection; json array is convenient for LLaMA-Factory Alpaca datasets.",
    )
    parser.add_argument(
        "--include-invalid-final",
        action="store_true",
        help="Include examples even if the final repaired diagram is still structurally invalid.",
    )
    parser.add_argument(
        "--granularity",
        choices=("full_case", "solved_violation"),
        default="full_case",
        help=(
            "full_case exports initial invalid diagram plus all initial violations to final valid repair. "
            "solved_violation exports one row per violation removed between repair steps."
        ),
    )
    args = parser.parse_args()
    run_ids = args.run_ids or []
    if args.all_repair_runs:
        runs_root = args.results_root / "runs"
        run_ids = sorted(p.name for p in runs_root.glob("*repair*") if p.is_dir())
    if not run_ids:
        parser.error("Provide at least one --run-id or use --all-repair-runs.")

    examples = iter_examples(
        dataset_root=args.dataset_root,
        results_root=args.results_root,
        run_ids=run_ids,
        require_final_valid=not args.include_invalid_final,
        granularity=args.granularity,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "json":
        args.output.write_text(json.dumps(examples, indent=2), encoding="utf-8")
    else:
        with args.output.open("w", encoding="utf-8") as handle:
            for example in examples:
                handle.write(json.dumps(example, ensure_ascii=False) + "\n")

    by_issue: dict[str, int] = {}
    for example in examples:
        for issue in example["metadata"]["violation_types"] or ["unknown_structural_violation"]:
            by_issue[issue] = by_issue.get(issue, 0) + 1

    print(f"Wrote {len(examples)} examples to {args.output}")
    for issue, count in sorted(by_issue.items(), key=lambda item: (-item[1], item[0])):
        print(f"{issue}: {count}")


if __name__ == "__main__":
    main()
