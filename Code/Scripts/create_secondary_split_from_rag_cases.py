from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from plantuml_pipeline.dataset import load_cases, stratified_split_cases


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a secondary stratified split from the original rag/train cases, "
            "leaving the original final test cases untouched."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--base-split",
        type=Path,
        default=Path("data/processed/experiments/split_35_seed42.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/experiments/qwen_train53_split_35_seed42.json"),
    )
    parser.add_argument("--test-size", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    base_split = json.loads(args.base_split.read_text(encoding="utf-8"))
    source_case_ids = set(base_split["rag_case_ids"])
    final_test_case_ids = set(base_split["test_case_ids"])

    cases = [case for case in load_cases(args.dataset_root) if case.case_id in source_case_ids]
    test_cases, rag_cases, secondary = stratified_split_cases(
        cases,
        test_size=args.test_size,
        seed=args.seed,
    )

    secondary.update(
        {
            "purpose": "qwen_finetuning_secondary_split_from_original_53_train_rag_cases",
            "base_split": str(args.base_split),
            "source_case_pool": "base_split.rag_case_ids",
            "source_case_count": len(source_case_ids),
            "excluded_final_test_case_count": len(final_test_case_ids),
            "excluded_final_test_case_ids": sorted(final_test_case_ids),
            "no_overlap_with_final_test": not (
                set(case.case_id for case in test_cases)
                | set(case.case_id for case in rag_cases)
            ).intersection(final_test_case_ids),
            "secondary_test_usage": "qwen_validation_or_internal_test_only",
            "secondary_rag_usage": "qwen_rag_examples_or_repair_sft_source_only",
        }
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(secondary, indent=2), encoding="utf-8")

    print(f"Wrote {args.output}")
    print(
        f"source={secondary['source_case_count']}, "
        f"test={secondary['test_count']}, rag={secondary['rag_count']}, "
        f"no_final_test_overlap={secondary['no_overlap_with_final_test']}"
    )


if __name__ == "__main__":
    main()
