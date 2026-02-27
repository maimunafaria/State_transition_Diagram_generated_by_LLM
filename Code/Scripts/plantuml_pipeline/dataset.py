from __future__ import annotations

import random
from pathlib import Path

from .io_utils import read_text
from .metrics import complexity_bucket
from .models import Case, ExperimentConfig
from .parser import normalize_puml_text, parse_and_validate_puml_text


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
        structured_req = read_text(structured_path).strip()
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


def build_experiment_configs(
    gpt_model: str,
    qwen_model: str,
    llama_model: str,
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
