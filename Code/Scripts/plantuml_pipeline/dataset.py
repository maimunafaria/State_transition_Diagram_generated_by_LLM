from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from .io_utils import read_text
from .metrics import complexity_bucket
from .models import Case, ExperimentConfig
from .parser import normalize_puml_text, parse_and_validate_puml_text


def prompt_requirement_from_structured(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""

    lines = stripped.splitlines()
    title = next((line.strip() for line in lines if line.strip()), "")
    functional_start = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "functional requirements":
            functional_start = index
            break

    if functional_start is None:
        return stripped

    functional_block = "\n".join(lines[functional_start:]).strip()
    if title:
        return f"{title}\n\n{functional_block}".strip()
    return functional_block


def load_cases(dataset_root: Path) -> list[Case]:
    case_dirs = sorted(
        [p for p in dataset_root.glob("case_*") if p.is_dir()],
        key=lambda p: p.name,
    )
    if not case_dirs:
        raise FileNotFoundError(f"No case directories found under {dataset_root}")

    cases: list[Case] = []
    for case_dir in case_dirs:
        raw_path = case_dir / "raw_requirement.txt"
        structured_path = case_dir / "structured_requirement.txt"
        gold_path = case_dir / "diagram.puml"
        if not raw_path.exists() or not structured_path.exists() or not gold_path.exists():
            raise FileNotFoundError(
                f"Missing required files in {case_dir}: "
                "raw_requirement.txt, structured_requirement.txt, diagram.puml"
            )
        raw_req = read_text(raw_path).strip()
        structured_req = prompt_requirement_from_structured(read_text(structured_path))
        gold_puml = normalize_puml_text(read_text(gold_path))
        gold_graph, gold_validation = parse_and_validate_puml_text(gold_puml)
        complexity = complexity_bucket(len(gold_graph.states))
        cases.append(
            Case(
                case_id=case_dir.name,
                path=case_dir,
                raw_requirement=raw_req,
                structured_requirement=structured_req,
                gold_puml=gold_puml,
                gold_graph=gold_graph,
                gold_validation=gold_validation,
                complexity=complexity,
            )
        )
    return cases


def balanced_subset(cases: list[Case], target_size: int, seed: int) -> list[Case]:
    if target_size <= 0:
        return []
    if len(cases) <= target_size:
        return list(cases)

    grouped: dict[str, list[Case]] = {"simple": [], "medium": [], "complex": []}
    for case in cases:
        grouped.setdefault(case.complexity, []).append(case)

    rng = random.Random(seed)
    for key in grouped:
        rng.shuffle(grouped[key])

    chosen: list[Case] = []
    while len(chosen) < target_size:
        made_progress = False
        for key in ("simple", "medium", "complex"):
            bucket = grouped.get(key, [])
            if bucket:
                chosen.append(bucket.pop())
                made_progress = True
                if len(chosen) == target_size:
                    break
        if not made_progress:
            break
    return chosen


def stratified_split_cases(
    cases: list[Case],
    test_size: float,
    seed: int,
) -> tuple[list[Case], list[Case], dict[str, Any]]:
    if not 0 < test_size <= 1:
        raise ValueError("--test-size must be greater than 0 and at most 1")

    grouped: dict[str, list[Case]] = {"simple": [], "medium": [], "complex": []}
    for case in cases:
        grouped.setdefault(case.complexity, []).append(case)

    rng = random.Random(seed)
    test_cases: list[Case] = []
    rag_cases: list[Case] = []
    by_complexity: dict[str, dict[str, Any]] = {}

    for complexity in ("simple", "medium", "complex"):
        bucket = list(grouped.get(complexity, []))
        rng.shuffle(bucket)
        test_count = round(len(bucket) * test_size)
        if bucket and test_count == 0:
            test_count = 1
        if test_size < 1 and test_count >= len(bucket) and len(bucket) > 1:
            test_count = len(bucket) - 1

        bucket_test = sorted(bucket[:test_count], key=lambda c: c.case_id)
        bucket_rag = sorted(bucket[test_count:], key=lambda c: c.case_id)
        test_cases.extend(bucket_test)
        rag_cases.extend(bucket_rag)
        by_complexity[complexity] = {
            "total": len(bucket),
            "test": len(bucket_test),
            "rag": len(bucket_rag),
        }

    test_cases = sorted(test_cases, key=lambda c: c.case_id)
    rag_cases = sorted(rag_cases, key=lambda c: c.case_id)
    split_meta = {
        "strategy": "stratified_by_complexity",
        "test_size": test_size,
        "seed": seed,
        "total_cases": len(cases),
        "test_count": len(test_cases),
        "rag_count": len(rag_cases),
        "by_complexity": by_complexity,
        "test_case_ids": [case.case_id for case in test_cases],
        "rag_case_ids": [case.case_id for case in rag_cases],
    }
    return test_cases, rag_cases, split_meta


def build_experiment_configs(
    gpt_model: str,
    qwen_model: str,
    llama_model: str,
    deepseek_model: str,
) -> list[ExperimentConfig]:
    configs: list[ExperimentConfig] = [
        ExperimentConfig(
            run_id="proprietary_baseline__gpt4o__zero_shot",
            model_group="proprietary_baseline",
            model_label="GPT-4o",
            model_name=gpt_model,
            strategy="zero_shot",
            use_rag=False,
            use_structural_validation=False,
            use_ensemble=False,
            baseline_subset_only=True,
        )
    ]

    open_models = [
        ("Qwen2.5-7B-Instruct", qwen_model, "qwen25_7b_instruct"),
        ("Llama 3.1-8B-Instruct", llama_model, "llama31_8b_instruct"),
        ("DeepSeek-R1-8B", deepseek_model, "deepseek_r1_8b"),
    ]
    strategies = [
        ("zero_shot", False, False, False),
        ("few_shot", False, False, False),
        ("rag", True, False, False),
        ("rag_structural_validation", True, True, False),
        ("rag_validation_generator_critic_repair", True, True, True),
    ]

    for model_label, model_name, model_tag in open_models:
        for strategy, use_rag, use_validation, use_ensemble in strategies:
            configs.append(
                ExperimentConfig(
                    run_id=f"open_source__{model_tag}__{strategy}",
                    model_group="open_source",
                    model_label=model_label,
                    model_name=model_name,
                    strategy=strategy,
                    use_rag=use_rag,
                    use_structural_validation=use_validation,
                    use_ensemble=use_ensemble,
                    baseline_subset_only=False,
                )
            )
    return configs
