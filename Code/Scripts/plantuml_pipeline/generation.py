from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from .model_client import call_model
from .models import Case, ExperimentConfig, ValidationResult
from .parser import normalize_puml_text, parse_and_validate_puml_text
from .prompting import (
    build_chain_of_thought_analysis_prompt,
    build_chain_of_thought_generation_prompt,
    build_full_pattern_repair_prompt,
    build_generation_prompt,
    build_repair_prompt,
    build_syntax_grounded_repair_prompt,
    build_syntax_grounded_pattern_rules_repair_prompt,
    build_targeted_repair_prompt,
    select_fewshot_examples,
)

DEFAULT_REPAIR_ATTEMPTS = 3


def strict_state_diagram_issues(validation: ValidationResult) -> list[str]:
    return list(validation.errors) + list(validation.warnings)


def is_strict_state_diagram_valid(validation: ValidationResult) -> bool:
    return not strict_state_diagram_issues(validation)


def validation_repair_score(validation: ValidationResult) -> int:
    return (1000 if not validation.valid else 0) + (100 * len(validation.errors)) + len(
        validation.warnings
    )


def repair_preserves_graph_shape(current_puml: str, repaired_puml: str) -> tuple[bool, dict[str, Any]]:
    current_graph, _ = parse_and_validate_puml_text(current_puml)
    repaired_graph, _ = parse_and_validate_puml_text(repaired_puml)
    current_states = len(current_graph.states)
    current_transitions = len(current_graph.transitions) + len(current_graph.final_states) + len(current_graph.initial_targets)
    repaired_states = len(repaired_graph.states)
    repaired_transitions = len(repaired_graph.transitions) + len(repaired_graph.final_states) + len(repaired_graph.initial_targets)

    if current_states <= 2:
        min_states = current_states
    else:
        min_states = max(2, int(current_states * 0.75))
    if current_transitions <= 2:
        min_transitions = current_transitions
    else:
        min_transitions = max(2, int(current_transitions * 0.70))

    dropped_states = sorted(current_graph.states - repaired_graph.states)
    added_states = sorted(repaired_graph.states - current_graph.states)
    meta = {
        "current_state_count": current_states,
        "repaired_state_count": repaired_states,
        "current_transition_count": current_transitions,
        "repaired_transition_count": repaired_transitions,
        "min_allowed_state_count": min_states,
        "min_allowed_transition_count": min_transitions,
        "dropped_states": dropped_states,
        "added_states": added_states,
    }
    return repaired_states >= min_states and repaired_transitions >= min_transitions, meta


def run_single_generation(
    case: Case,
    cfg: ExperimentConfig,
    all_cases: list[Case],
    rag_docs: list[tuple[str, str, set[str]]],
    requirement_source: str,
    top_k_rag: int,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
    rag_max_chars_per_doc: int = 1200,
    rag_domain_hints: set[str] | None = None,
    rag_mode: str = "lexical",
    rag_db_dir: Path | None = None,
    rag_collection_name: str = "uml_docs",
    rag_profile: str = "standard",
    few_shot_seed: int = 42,
    few_shot_count: int = 3,
    few_shot_prompt_structure: str = "original",
    run_index: int = 1,
    repair_attempts: int = DEFAULT_REPAIR_ATTEMPTS,
    repair_mode: str = "baseline",
    repair_model_name: str = "",
    initial_puml: str | None = None,
    initial_prompt: str = "",
    initial_source: str = "",
) -> tuple[str, ValidationResult, str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    steps: list[dict[str, Any]] = []
    if initial_puml is None:
        if cfg.strategy == "chain_of_thought":
            cot_prompt_structure = few_shot_prompt_structure.strip().lower() or "original"
            analysis_prompt = build_chain_of_thought_analysis_prompt(
                requirement,
                prompt_structure=cot_prompt_structure,
            )
            analysis = call_model(
                model_name=cfg.model_name,
                prompt=analysis_prompt,
                ollama_host=ollama_host,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            example_requirement = ""
            example_puml = ""
            example_case_id = ""
            if cot_prompt_structure == "plantuml_example":
                selection_run_id = cfg.run_id.replace("__prompt_plantuml_example", "")
                rng = random.Random(f"{few_shot_seed}:{selection_run_id}:{case.case_id}:{run_index}")
                examples = select_fewshot_examples(
                    all_cases,
                    case.case_id,
                    max_examples=1,
                    rng=rng,
                )
                if examples:
                    example = examples[0]
                    example_case_id = example.case_id
                    example_requirement = (
                        example.structured_requirement.strip()
                        or example.raw_requirement.strip()
                    )
                    example_puml = example.gold_puml.strip()

            generation_prompt = build_chain_of_thought_generation_prompt(
                requirement,
                analysis,
                prompt_structure=cot_prompt_structure,
                example_requirement=example_requirement,
                example_puml=example_puml,
            )
            prompt_meta = {
                "requirement_source": requirement_source,
                "few_shot_case_ids": [],
                "few_shot_prompt_structure": few_shot_prompt_structure,
                "rag": {
                    "enabled": False,
                    "mode": rag_mode,
                    "profile": rag_profile,
                    "top_k": top_k_rag,
                    "max_chars_per_doc": rag_max_chars_per_doc,
                    "query_domains": [],
                    "retrieved_docs": [],
                },
            }
            steps.append(
                {
                    "stage": "chain_of_thought_analysis",
                    "analysis_chars": len(analysis),
                    "prompt_structure": cot_prompt_structure,
                    "example_case_id": example_case_id,
                }
            )
            prompt = (
                "=== Chain-of-thought analysis prompt ===\n"
                f"{analysis_prompt.strip()}\n\n"
                "=== Chain-of-thought analysis response ===\n"
                f"{analysis.strip()}\n\n"
                "=== PlantUML generation prompt ===\n"
                f"{generation_prompt.strip()}\n"
            )
        else:
            generation_prompt, prompt_meta = build_generation_prompt(
                case=case,
                cfg=cfg,
                all_cases=all_cases,
                rag_docs=rag_docs,
                requirement_source=requirement_source,
                top_k_rag=top_k_rag,
                rag_max_chars_per_doc=rag_max_chars_per_doc,
                rag_domain_hints=rag_domain_hints,
                rag_mode=rag_mode,
                rag_db_dir=rag_db_dir,
                rag_collection_name=rag_collection_name,
                rag_profile=rag_profile,
                few_shot_seed=few_shot_seed,
                few_shot_count=few_shot_count,
                few_shot_prompt_structure=few_shot_prompt_structure,
                run_index=run_index,
            )
            prompt = generation_prompt
        if prompt_meta.get("few_shot_case_ids"):
            steps.append(
                {
                    "stage": "few_shot_selection",
                    "case_ids": list(prompt_meta["few_shot_case_ids"]),
                    "seed": prompt_meta.get("few_shot_seed"),
                    "run_index": prompt_meta.get("few_shot_run_index"),
                }
            )
        rag_meta = prompt_meta.get("rag", {})
        if rag_meta.get("enabled"):
            steps.append(
                {
                    "stage": "rag_retrieval",
                    "mode": str(rag_meta.get("mode", "lexical")),
                    "profile": str(rag_meta.get("profile", "standard")),
                    "top_k": int(rag_meta.get("top_k", 0)),
                    "query_domains": list(rag_meta.get("query_domains", [])),
                    "retrieved_docs": list(rag_meta.get("retrieved_docs", [])),
                }
            )

        generated = call_model(
            model_name=cfg.model_name,
            prompt=generation_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        generated_puml = normalize_puml_text(generated)
        _, validation = parse_and_validate_puml_text(generated_puml)
        strict_issues = strict_state_diagram_issues(validation)
        steps.append(
            {
                "stage": "generator",
                "plantuml_valid": validation.valid,
                "strict_state_diagram_valid": not strict_issues,
                "errors": list(validation.errors),
                "warnings": list(validation.warnings),
                "strict_issues": strict_issues,
            }
        )
    else:
        prompt = initial_prompt
        generated_puml = normalize_puml_text(initial_puml)
        _, validation = parse_and_validate_puml_text(generated_puml)
        strict_issues = strict_state_diagram_issues(validation)
        steps.append(
            {
                "stage": "generator_reused",
                "source": initial_source or "existing_base_run",
                "plantuml_valid": validation.valid,
                "strict_state_diagram_valid": not strict_issues,
                "errors": list(validation.errors),
                "warnings": list(validation.warnings),
                "strict_issues": strict_issues,
            }
        )

    final_puml = generated_puml
    final_validation = validation
    attempt_artifacts: list[dict[str, Any]] = [
        {
            "stage": "initial",
            "attempt": 0,
            "puml": generated_puml,
            "validation": validation.to_dict(),
            "strict_state_diagram_valid": is_strict_state_diagram_valid(validation),
        }
    ]

    if cfg.use_structural_validation:
        for attempt in range(1, max(0, repair_attempts) + 1):
            current_issues = strict_state_diagram_issues(final_validation)
            if not current_issues:
                break

            critic_prompt = ""
            critic_feedback = ""

            repair_mode_clean = repair_mode.strip().lower()
            if repair_mode_clean == "targeted":
                repair_prompt = build_targeted_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "syntax_grounded":
                repair_prompt = build_syntax_grounded_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "syntax_grounded_pattern_rules":
                repair_prompt = build_syntax_grounded_pattern_rules_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "full_patterns":
                repair_prompt = build_full_pattern_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            else:
                repair_prompt = build_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            repaired = call_model(
                model_name=repair_model_name.strip() or cfg.model_name,
                prompt=repair_prompt,
                ollama_host=ollama_host,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            repaired_puml = normalize_puml_text(repaired)
            _, repaired_validation = parse_and_validate_puml_text(repaired_puml)
            repaired_issues = strict_state_diagram_issues(repaired_validation)
            current_score = validation_repair_score(final_validation)
            repaired_score = validation_repair_score(repaired_validation)
            preserves_shape, preservation_meta = repair_preserves_graph_shape(final_puml, repaired_puml)
            accepted = repaired_score < current_score and (
                repair_mode_clean != "targeted" or preserves_shape or repaired_score == 0
            )
            attempt_artifacts.append(
                {
                    "stage": "repair",
                    "attempt": attempt,
                    "repair_mode": repair_mode_clean,
                    "repair_model_name": repair_model_name.strip() or cfg.model_name,
                    "repair_prompt": repair_prompt,
                    "puml": repaired_puml,
                    "validation": repaired_validation.to_dict(),
                    "strict_state_diagram_valid": not repaired_issues,
                    "accepted": accepted,
                    "previous_score": current_score,
                    "repair_score": repaired_score,
                    "preservation": preservation_meta,
                }
            )
            if accepted:
                final_puml = repaired_puml
                final_validation = repaired_validation
                current_issues_after_attempt = repaired_issues
            else:
                current_issues_after_attempt = current_issues
            steps.append(
                {
                    "stage": "repair",
                    "attempt": attempt,
                    "accepted": accepted,
                    "repair_mode": repair_mode_clean,
                    "repair_model_name": repair_model_name.strip() or cfg.model_name,
                    "previous_score": current_score,
                    "repair_score": repaired_score,
                    "preserves_graph_shape": preserves_shape,
                    "preservation": preservation_meta,
                    "plantuml_valid": repaired_validation.valid,
                    "strict_state_diagram_valid": not repaired_issues,
                    "errors": list(repaired_validation.errors),
                    "warnings": list(repaired_validation.warnings),
                    "strict_issues": repaired_issues,
                }
            )

            if not current_issues_after_attempt:
                break
            if not accepted:
                steps.append(
                    {
                        "stage": "repair_rejected",
                        "attempt": attempt,
                        "reason": "repair_did_not_improve_validation_score",
                        "kept_previous_issues": current_issues,
                        "action": "kept_best_diagram_and_continued",
                    }
                )

        final_issues = strict_state_diagram_issues(final_validation)
        steps.append(
            {
                "stage": "repair_loop_summary",
                "attempts": len(attempt_artifacts) - 1,
                "strict_state_diagram_valid": not final_issues,
                "remaining_issues": final_issues,
            }
        )

    return final_puml, final_validation, prompt, requirement, steps, attempt_artifacts
