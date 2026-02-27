from __future__ import annotations

from typing import Any

from .model_client import call_model
from .models import Case, ExperimentConfig, ValidationResult
from .parser import normalize_puml_text, parse_and_validate_puml_text
from .prompting import build_critic_prompt, build_generation_prompt, build_repair_prompt


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
) -> tuple[str, ValidationResult, str, str, list[dict[str, Any]]]:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    steps: list[dict[str, Any]] = []
    prompt, prompt_meta = build_generation_prompt(
        case=case,
        cfg=cfg,
        all_cases=all_cases,
        rag_docs=rag_docs,
        requirement_source=requirement_source,
        top_k_rag=top_k_rag,
        rag_max_chars_per_doc=rag_max_chars_per_doc,
        rag_domain_hints=rag_domain_hints,
    )
    if prompt_meta.get("few_shot_case_ids"):
        steps.append(
            {
                "stage": "few_shot_selection",
                "case_ids": list(prompt_meta["few_shot_case_ids"]),
            }
        )
    rag_meta = prompt_meta.get("rag", {})
    if rag_meta.get("enabled"):
        steps.append(
            {
                "stage": "rag_retrieval",
                "top_k": int(rag_meta.get("top_k", 0)),
                "query_domains": list(rag_meta.get("query_domains", [])),
                "retrieved_docs": list(rag_meta.get("retrieved_docs", [])),
            }
        )

    generated = call_model(
        model_name=cfg.model_name,
        prompt=prompt,
        ollama_host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    generated_puml = normalize_puml_text(generated)
    _, validation = parse_and_validate_puml_text(generated_puml)
    steps.append({"stage": "generator", "valid": validation.valid, "errors": list(validation.errors)})

    final_puml = generated_puml
    final_validation = validation

    if cfg.use_structural_validation and not final_validation.valid:
        if cfg.use_ensemble:
            critic_prompt = build_critic_prompt(requirement, final_puml, final_validation)
            critic_feedback = call_model(
                model_name=cfg.model_name,
                prompt=critic_prompt,
                ollama_host=ollama_host,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            steps.append({"stage": "critic", "output": critic_feedback[:2000]})
        else:
            critic_feedback = ""

        repair_prompt = build_repair_prompt(requirement, final_puml, final_validation, critic_feedback)
        repaired = call_model(
            model_name=cfg.model_name,
            prompt=repair_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        repaired_puml = normalize_puml_text(repaired)
        _, repaired_validation = parse_and_validate_puml_text(repaired_puml)
        final_puml = repaired_puml
        final_validation = repaired_validation
        steps.append(
            {
                "stage": "repair",
                "valid": final_validation.valid,
                "errors": list(final_validation.errors),
            }
        )
    return final_puml, final_validation, prompt, requirement, steps
