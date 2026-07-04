from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_repair_sft_dataset import (
    INSTRUCTION,
    build_input,
    normalize_issue,
)
from plantuml_pipeline.parser import parse_and_validate_puml_text


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_training_case_ids(path: Path) -> set[str]:
    case_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            case_id = str(row.get("metadata", {}).get("case_id", "")).strip()
            if not case_id:
                raise ValueError(
                    f"Missing metadata.case_id in training row {line_number}"
                )
            case_ids.add(case_id)
    return case_ids


def normalized_issues(errors: list[str], warnings: list[str]) -> list[str]:
    result: list[str] = []
    for raw_issue in [*errors, *warnings]:
        issue = normalize_issue(str(raw_issue))
        if issue and issue not in result:
            result.append(issue)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the disjoint 18-case Qwen repair test bundle."
    )
    parser.add_argument(
        "--raw-run-dir",
        type=Path,
        default=Path(
            "results/plantuml_pipeline_qwen_train53/runs/"
            "open_source__qwen25_7b_instruct__rag"
        ),
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=Path(
            "data/processed/experiments/qwen_train53_split_35_seed42.json"
        ),
    )
    parser.add_argument(
        "--training-data",
        type=Path,
        default=Path(
            "data/sft/all_llm_violation_repair_sft.cleaned.jsonl"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("kaggle_test_qwen_repair/qwen18_repair_test.jsonl"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    split = read_json(args.split)
    test_case_ids = [str(value) for value in split["test_case_ids"]]
    if len(test_case_ids) != 18 or len(set(test_case_ids)) != 18:
        raise ValueError("The external test split must contain 18 unique cases.")

    training_case_ids = read_training_case_ids(args.training_data)
    overlap = sorted(training_case_ids & set(test_case_ids))
    if overlap:
        raise ValueError(f"Training/test case leakage detected: {overlap}")

    rows: list[dict[str, Any]] = []
    for case_id in test_case_ids:
        case_dir = args.raw_run_dir / case_id
        puml_path = case_dir / "run_01.puml"
        meta_path = case_dir / "run_01.meta.json"
        if not puml_path.is_file() or not meta_path.is_file():
            raise FileNotFoundError(f"Missing frozen run files for {case_id}")

        invalid_puml = puml_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
        meta = read_json(meta_path)
        requirement = str(meta.get("requirement_used", "")).strip()
        if not requirement:
            raise ValueError(f"Missing requirement_used for {case_id}")

        _, validation = parse_and_validate_puml_text(invalid_puml)
        issues = normalized_issues(validation.errors, validation.warnings)
        if not issues:
            raise ValueError(
                f"{case_id} has no current validation issues; "
                "it is not a repair test case."
            )

        rows.append(
            {
                "case_id": case_id,
                "instruction": INSTRUCTION,
                "input": build_input(requirement, invalid_puml, issues),
                "invalid_puml": invalid_puml,
                "violation_types": issues,
                "source_run_id": str(meta.get("run_id", "")),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "source_run_dir": str(args.raw_run_dir),
        "source_split": str(args.split),
        "training_data": str(args.training_data),
        "test_case_count": len(rows),
        "test_case_ids": [row["case_id"] for row in rows],
        "training_case_count": len(training_case_ids),
        "training_test_overlap": overlap,
        "ground_truth_included": False,
    }
    manifest_path = args.output.with_name("qwen18_test_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
