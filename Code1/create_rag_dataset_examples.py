#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from plantuml_pipeline.constants import PROJECT_ROOT
from plantuml_pipeline.dataset import load_cases


DEFAULT_SPLIT = PROJECT_ROOT / "data" / "processed" / "experiments" / "split_35_seed42.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "rag_corpus" / "dataset_examples"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "rag_corpus" / "dataset_examples_manifest.csv"


def title_from_requirement(requirement: str, case_id: str) -> str:
    for line in requirement.splitlines():
        clean = line.strip()
        if clean:
            return clean
    return case_id


def domain_from_title(title: str, case_id: str) -> str:
    text = title
    if "—" in text:
        text = text.split("—", 1)[0]
    elif "-" in text:
        text = text.split("-", 1)[0]
    text = text.replace("Polished Requirement Specification", "").strip()
    if text:
        return text
    words = re.sub(r"^case_\d+_", "", case_id).replace("_", " ")
    return words.title()


def format_dataset_doc(case) -> str:
    title = title_from_requirement(case.structured_requirement, case.case_id)
    domain = domain_from_title(title, case.case_id)
    return (
        "---\n"
        "source_type: dataset_example\n"
        f"case_id: {case.case_id}\n"
        f"domain: {domain}\n"
        f"complexity: {case.complexity}\n"
        "split_role: rag_train\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Requirement\n\n"
        f"{case.structured_requirement.strip()}\n\n"
        "## Reference PlantUML\n\n"
        "```plantuml\n"
        f"{case.gold_puml.strip()}\n"
        "\n```\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create RAG dataset-example documents from train/RAG split cases only."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=PROJECT_ROOT / "dataset",
        help="Dataset folder containing case_* directories.",
    )
    parser.add_argument(
        "--split-file",
        type=Path,
        default=DEFAULT_SPLIT,
        help="JSON split file containing rag_case_ids and test_case_ids.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output folder for generated RAG dataset-example markdown files.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="CSV manifest for generated RAG dataset-example docs.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing generated .md files in output-dir before writing.",
    )
    args = parser.parse_args()

    split = json.loads(args.split_file.read_text(encoding="utf-8"))
    rag_ids = list(split.get("rag_case_ids", []))
    test_ids = set(split.get("test_case_ids", []))
    overlap = sorted(set(rag_ids) & test_ids)
    if overlap:
        raise ValueError(f"Split leakage detected; cases are both test and RAG: {overlap}")

    cases = {case.case_id: case for case in load_cases(args.dataset_root)}
    missing = sorted(case_id for case_id in rag_ids if case_id not in cases)
    if missing:
        raise FileNotFoundError(f"RAG cases missing from dataset folder: {missing}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    if args.clean:
        for old_doc in args.output_dir.glob("*.md"):
            old_doc.unlink()

    rows: list[dict[str, str]] = []
    for case_id in rag_ids:
        case = cases[case_id]
        title = title_from_requirement(case.structured_requirement, case.case_id)
        domain = domain_from_title(title, case.case_id)
        output_path = args.output_dir / f"{case.case_id}.md"
        output_path.write_text(format_dataset_doc(case), encoding="utf-8")
        rows.append(
            {
                "case_id": case.case_id,
                "domain": domain,
                "complexity": case.complexity,
                "source_type": "dataset_example",
                "split_role": "rag_train",
                "path": str(output_path),
            }
        )

    with args.manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "domain",
                "complexity",
                "source_type",
                "split_role",
                "path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created {len(rows)} RAG dataset-example docs in {args.output_dir}")
    print(f"Manifest written to {args.manifest}")
    print(f"Test cases excluded: {len(test_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
