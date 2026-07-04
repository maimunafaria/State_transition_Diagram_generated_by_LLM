from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_repair_sft_dataset import normalize_issue
from plantuml_pipeline.parser import parse_and_validate_puml_text


def issue_types(errors: list[str], warnings: list[str]) -> list[str]:
    result: list[str] = []
    for raw_issue in [*errors, *warnings]:
        issue = normalize_issue(str(raw_issue))
        if issue and issue not in result:
            result.append(issue)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freshly evaluate external fine-tuned repair predictions."
    )
    parser.add_argument("--predictions-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir or args.predictions_root / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)

    case_dirs = sorted(args.predictions_root.glob("case_*"))
    if not case_dirs:
        raise ValueError(f"No case folders found under {args.predictions_root}")

    rows: list[dict[str, Any]] = []
    initial_counts: Counter[str] = Counter()
    solved_counts: Counter[str] = Counter()
    remaining_counts: Counter[str] = Counter()
    introduced_counts: Counter[str] = Counter()

    for case_dir in case_dirs:
        invalid_path = case_dir / "invalid.puml"
        repaired_path = case_dir / "repaired.puml"
        if not invalid_path.is_file() or not repaired_path.is_file():
            raise FileNotFoundError(f"Missing PlantUML files in {case_dir}")

        invalid_puml = invalid_path.read_text(encoding="utf-8", errors="replace")
        repaired_puml = repaired_path.read_text(encoding="utf-8", errors="replace")
        _, before = parse_and_validate_puml_text(invalid_puml)
        _, after = parse_and_validate_puml_text(repaired_puml)

        before_types = issue_types(before.errors, before.warnings)
        after_types = issue_types(after.errors, after.warnings)
        solved = sorted(set(before_types) - set(after_types))
        remaining = sorted(set(before_types) & set(after_types))
        introduced = sorted(set(after_types) - set(before_types))

        initial_counts.update(before_types)
        solved_counts.update(solved)
        remaining_counts.update(remaining)
        introduced_counts.update(introduced)

        rows.append(
            {
                "case_id": case_dir.name,
                "before_syntax_valid": not before.errors,
                "after_syntax_valid": not after.errors,
                "before_strict_valid": not before.errors and not before.warnings,
                "after_strict_valid": not after.errors and not after.warnings,
                "before_issue_types": "|".join(before_types),
                "after_issue_types": "|".join(after_types),
                "solved_issue_types": "|".join(solved),
                "remaining_issue_types": "|".join(remaining),
                "introduced_issue_types": "|".join(introduced),
                "after_raw_errors": " | ".join(after.errors),
                "after_raw_warnings": " | ".join(after.warnings),
            }
        )

    fields = list(rows[0])
    with (output_dir / "evaluation_cases.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    violation_rows: list[dict[str, Any]] = []
    for issue in sorted(initial_counts):
        initial = initial_counts[issue]
        solved = solved_counts[issue]
        violation_rows.append(
            {
                "violation_type": issue,
                "initial_case_count": initial,
                "solved_case_count": solved,
                "resolution_percent": round(100.0 * solved / initial, 2),
                "remaining_case_count": remaining_counts[issue],
                "introduced_case_count": introduced_counts[issue],
            }
        )
    for issue in sorted(set(introduced_counts) - set(initial_counts)):
        violation_rows.append(
            {
                "violation_type": issue,
                "initial_case_count": 0,
                "solved_case_count": 0,
                "resolution_percent": "",
                "remaining_case_count": 0,
                "introduced_case_count": introduced_counts[issue],
            }
        )

    with (output_dir / "violation_resolution.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "violation_type",
                "initial_case_count",
                "solved_case_count",
                "resolution_percent",
                "remaining_case_count",
                "introduced_case_count",
            ],
        )
        writer.writeheader()
        writer.writerows(violation_rows)

    case_count = len(rows)
    before_syntax = sum(bool(row["before_syntax_valid"]) for row in rows)
    after_syntax = sum(bool(row["after_syntax_valid"]) for row in rows)
    before_strict = sum(bool(row["before_strict_valid"]) for row in rows)
    after_strict = sum(bool(row["after_strict_valid"]) for row in rows)
    initial_total = sum(initial_counts.values())
    solved_total = sum(solved_counts.values())

    summary = {
        "case_count": case_count,
        "before_syntax_valid_count": before_syntax,
        "before_syntax_valid_percent": round(100.0 * before_syntax / case_count, 2),
        "after_syntax_valid_count": after_syntax,
        "after_syntax_valid_percent": round(100.0 * after_syntax / case_count, 2),
        "before_strict_valid_count": before_strict,
        "before_strict_valid_percent": round(100.0 * before_strict / case_count, 2),
        "after_strict_valid_count": after_strict,
        "after_strict_valid_percent": round(100.0 * after_strict / case_count, 2),
        "initial_case_violation_occurrences": initial_total,
        "solved_case_violation_occurrences": solved_total,
        "error_resolution_percent": round(
            100.0 * solved_total / initial_total,
            2,
        ),
        "remaining_initial_violation_occurrences": sum(
            remaining_counts.values()
        ),
        "introduced_violation_occurrences": sum(introduced_counts.values()),
        "strictly_valid_case_ids": [
            str(row["case_id"]) for row in rows if row["after_strict_valid"]
        ],
        "failed_case_ids": [
            str(row["case_id"]) for row in rows if not row["after_strict_valid"]
        ],
    }
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
