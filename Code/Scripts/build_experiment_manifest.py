#!/usr/bin/env python3
import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DATASET_DIR = DATA_DIR / "processed" / "dataset"
EXPERIMENTS_DIR = DATA_DIR / "processed" / "experiments"
SUBSETS_DIR = DATASET_DIR / "subsets"


def resolve_default_dataset() -> Path:
    dated_files = sorted(DATASET_DIR.glob("dataset_*.jsonl"))
    if dated_files:
        return dated_files[-1]
    return DATASET_DIR / "dataset.jsonl"


def to_project_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_no} in {path}: {exc}"
                ) from exc
    return rows


def balanced_subset(
    records: list[dict], sample_size: int, seed: int, balance_key: str = "domain"
) -> list[dict]:
    if sample_size <= 0 or not records:
        return []

    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in records:
        key = str(item.get(balance_key) or "unknown")
        grouped[key].append(item)

    rng = random.Random(seed)
    keys = sorted(grouped.keys())
    for key in keys:
        rng.shuffle(grouped[key])

    target = min(sample_size, len(records))
    chosen: list[dict] = []

    # Round-robin pick to keep category counts as even as possible.
    while len(chosen) < target:
        any_left = False
        for key in keys:
            bucket = grouped[key]
            if not bucket:
                continue
            any_left = True
            chosen.append(bucket.pop())
            if len(chosen) == target:
                break
        if not any_left:
            break

    return chosen


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_run_manifest(
    dataset_path: str,
    baseline_subset_path: str,
    baseline_sample_count: int,
    baseline_target_count: int,
) -> list[dict]:
    open_models = [
        "Qwen2.5-7B-Instruct",
        "Llama 3.1-8B-Instruct",
    ]
    open_strategies = [
        ("zero_shot", False, False, False),
        ("few_shot", False, False, False),
        ("rag", True, False, False),
        ("rag_structural_validation", True, True, False),
        ("rag_validation_generator_critic_repair", True, True, True),
    ]

    runs = [
        {
            "run_id": "proprietary_baseline__gpt-4o__zero_shot",
            "model_group": "proprietary_baseline",
            "model": "GPT-4o",
            "strategy": "zero_shot",
            "use_rag": False,
            "use_structural_validation": False,
            "use_generator_critic_repair_ensemble": False,
            "dataset_path": baseline_subset_path,
            "sample_policy": "balanced_subset_by_domain",
            "sample_count": baseline_sample_count,
            "target_sample_count": baseline_target_count,
        }
    ]

    for model in open_models:
        for strategy, use_rag, use_structural_validation, use_ensemble in open_strategies:
            run_id = (
                f"open_source__{model.lower().replace(' ', '_').replace('.', '')}"
                f"__{strategy}"
            )
            runs.append(
                {
                    "run_id": run_id,
                    "model_group": "open_source",
                    "model": model,
                    "strategy": strategy,
                    "use_rag": use_rag,
                    "use_structural_validation": use_structural_validation,
                    "use_generator_critic_repair_ensemble": use_ensemble,
                    "dataset_path": dataset_path,
                    "sample_policy": "full_dataset",
                    "sample_count": None,
                    "target_sample_count": None,
                }
            )

    return runs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build Section 3.4 experiment artifacts: GPT-4o balanced subset and "
            "11-configuration run manifest."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=resolve_default_dataset(),
        help="Input dataset JSONL",
    )
    parser.add_argument(
        "--baseline-sample-size",
        type=int,
        default=30,
        help="Target sample count for GPT-4o baseline subset",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic subset sampling",
    )
    parser.add_argument(
        "--subset-output",
        type=Path,
        default=SUBSETS_DIR / "gpt4o_balanced_30.jsonl",
        help="Output JSONL path for GPT-4o balanced subset",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=EXPERIMENTS_DIR / "run_manifest_3_4.jsonl",
        help="Output JSONL path for experiment run manifest",
    )
    parser.add_argument(
        "--design-output",
        type=Path,
        default=EXPERIMENTS_DIR / "experimental_design_3_4.json",
        help="Output JSON path for design summary",
    )

    args = parser.parse_args()
    records = load_jsonl(args.dataset)
    subset = balanced_subset(
        records=records,
        sample_size=args.baseline_sample_size,
        seed=args.seed,
        balance_key="domain",
    )

    write_jsonl(args.subset_output, subset)

    rel_dataset = to_project_relative(args.dataset)
    rel_subset = to_project_relative(args.subset_output)
    runs = build_run_manifest(
        dataset_path=rel_dataset,
        baseline_subset_path=rel_subset,
        baseline_sample_count=len(subset),
        baseline_target_count=args.baseline_sample_size,
    )
    write_jsonl(args.manifest_output, runs)

    design = {
        "section": "3.4 Experimental Design",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_source": rel_dataset,
        "total_configurations": len(runs),
        "model_groups": {
            "proprietary_baseline": {
                "model": "GPT-4o",
                "configurations": ["zero_shot"],
                "evaluation_subset": {
                    "policy": "balanced_subset_by_domain",
                    "target_samples": args.baseline_sample_size,
                    "actual_samples": len(subset),
                    "path": rel_subset,
                },
            },
            "open_source_models": [
                {
                    "model": "Qwen2.5-7B-Instruct",
                    "configurations": [
                        "zero_shot",
                        "few_shot",
                        "rag",
                        "rag_structural_validation",
                        "rag_validation_generator_critic_repair",
                    ],
                },
                {
                    "model": "Llama 3.1-8B-Instruct",
                    "configurations": [
                        "zero_shot",
                        "few_shot",
                        "rag",
                        "rag_structural_validation",
                        "rag_validation_generator_critic_repair",
                    ],
                },
            ],
        },
    }
    args.design_output.parent.mkdir(parents=True, exist_ok=True)
    args.design_output.write_text(
        json.dumps(design, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Loaded {len(records)} dataset rows from {args.dataset}")
    print(f"Wrote baseline subset ({len(subset)} rows) -> {args.subset_output}")
    print(f"Wrote run manifest ({len(runs)} rows) -> {args.manifest_output}")
    print(f"Wrote design summary -> {args.design_output}")


if __name__ == "__main__":
    main()
