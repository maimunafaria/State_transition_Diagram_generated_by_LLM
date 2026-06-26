from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from .model_client import call_model
from .models import Case, ExperimentConfig, ValidationResult
from .parser import normalize_puml_text, parse_and_validate_puml_text
from .constants import TRANSITION_RE
from .prompting import (
    _prioritized_repair_issues,
    build_chain_of_thought_analysis_prompt,
    build_chain_of_thought_generation_prompt,
    build_compiler_guided_syntax_repair_prompt,
    build_issue_routed_sequential_repair_prompt,
    build_constrained_validator_repair_prompt,
    build_diagnostic_syntax_grounded_repair_prompt,
    build_example_guided_repair_prompt,
    build_full_pattern_repair_prompt,
    build_generation_prompt,
    build_hybrid_issue_guided_repair_prompt,
    build_repair_prompt,
    build_sequential_baseline_repair_prompt,
    build_sequential_example_guided_repair_prompt,
    build_sequential_syntax_grounded_pattern_rules_repair_prompt,
    build_syntax_grounded_no_rules_repair_prompt,
    build_syntax_grounded_repair_prompt,
    build_syntax_grounded_pattern_rules_repair_prompt,
    build_targeted_repair_prompt,
    build_transition_patch_repair_prompt,
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


_TRANSITION_LINE_RE = re.compile(
    r"^(.+?)\s*[-.]+(?:right|left|up|down)?(?:\[[^\]]+\])?>\s*(.+?)(?:\s*:\s*(.*))?$"
)


def _deterministic_validator_repair(puml_text: str, validation: ValidationResult) -> str:
    issues = strict_state_diagram_issues(validation)
    issue_text = "\n".join(issues).lower()
    if not issues:
        return puml_text

    lines = puml_text.splitlines()
    repaired: list[str] = []
    seen_transitions: set[str] = set()
    changed = False

    for raw_line in lines:
        stripped = raw_line.strip()
        low = stripped.lower()

        if low == "state":
            changed = True
            continue

        if "[*]" in stripped and "-->" in stripped and re.search(r"\[\*\]\s*[-.]+>\s*\[\*\]", stripped):
            changed = True
            continue

        transition_match = _TRANSITION_LINE_RE.match(stripped)
        if transition_match:
            normalized_transition = " ".join(stripped.split())
            if "duplicate_transitions" in issue_text and normalized_transition in seen_transitions:
                changed = True
                continue
            seen_transitions.add(normalized_transition)

        repaired.append(raw_line)

    if not changed:
        return puml_text
    return normalize_puml_text("\n".join(repaired))


def _has_plantuml_syntax_error(validation: ValidationResult) -> bool:
    return any("plantuml_syntax_error" in issue.lower() for issue in validation.errors)


def _repair_issue_key(issue: str) -> str:
    low = issue.lower()
    if "plantuml_syntax_error" in low:
        return "plantuml_syntax_error"
    if "missing_final_state_transition" in low:
        return "missing_final_state_transition"
    if "missing_initial_state_transition" in low:
        return "missing_initial_state_transition"
    if "multiple_initial_state_transitions" in low:
        return "multiple_initial_state_transitions"
    if "duplicate_transitions" in low:
        return "duplicate_transitions_detected"
    if "choice_node_without_guarded" in low:
        return "choice_node_without_guarded_outgoing_transitions"
    if "choice_node_without_outgoing" in low:
        return "choice_node_without_outgoing_transitions"
    if "invalid [*]" in low:
        return "invalid_initial_to_final_transition"
    if "orphan" in low:
        return "orphan_states_detected"
    if "unreachable" in low:
        return "unreachable_states_detected"
    if "fork_" in low:
        return "fork_node_violation"
    if "join_" in low:
        return "join_node_violation"
    if "history_state" in low:
        return "history_state_violation"
    return re.sub(r"\s*\(.*$", "", issue.split(":", 1)[0].strip().lower())


def _validation_issue_keys(validation: ValidationResult) -> set[str]:
    return {
        _repair_issue_key(issue)
        for issue in strict_state_diagram_issues(validation)
    }


def _issue_repair_route(issue: str) -> str:
    key = _repair_issue_key(issue)
    if key == "plantuml_syntax_error":
        return "compiler_guided"
    if key in {
        "missing_final_state_transition",
        "duplicate_transitions_detected",
        "choice_node_without_outgoing_transitions",
    }:
        return "baseline"
    return "syntax_grounded"


def _deterministic_syntax_repair(
    puml_text: str,
    validation: ValidationResult | None = None,
) -> str:
    lines = normalize_puml_text(puml_text).splitlines()
    repaired: list[str] = []
    changed = False
    failing_line_number = 0
    if validation is not None:
        for issue in validation.errors:
            match = re.search(r"plantuml_syntax_error:\s*line\s+(\d+)", issue, re.IGNORECASE)
            if match:
                failing_line_number = int(match.group(1))
                break
    bare_stereotype = re.compile(
        r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s+"
        r"<<(choice|fork|join|history|deepHistory)>>\s*$",
        re.IGNORECASE,
    )
    incomplete_stereotype = re.compile(
        r"^(\s*state\s+[A-Za-z_][A-Za-z0-9_]*\s+)"
        r"<<(choice|fork|join|history|deepHistory)\s*$",
        re.IGNORECASE,
    )
    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        is_failing_line = not failing_line_number or line_number == failing_line_number
        match = bare_stereotype.match(raw_line)
        incomplete_match = incomplete_stereotype.match(raw_line)
        if is_failing_line and match and not raw_line.lstrip().lower().startswith("state "):
            indent, state_name, stereotype = match.groups()
            repaired.append(f"{indent}state {state_name} <<{stereotype}>>")
            changed = True
        elif is_failing_line and incomplete_match:
            prefix, stereotype = incomplete_match.groups()
            repaired.append(f"{prefix}<<{stereotype}>>")
            changed = True
        elif is_failing_line and stripped.lower().startswith(
            ("here is ", "here's ", "below is ", "the plantuml code")
        ):
            changed = True
            continue
        elif is_failing_line and re.match(r"^.+[-.]+>\s*$", stripped):
            changed = True
            continue
        elif is_failing_line and "-->" in stripped and ":" in stripped:
            transition, label = raw_line.split(":", 1)
            if ";" in label:
                repaired.append(f"{transition}: {label.replace(';', ' and ').strip()}")
                changed = True
            else:
                repaired.append(raw_line)
        elif (
            is_failing_line
            and stripped
            and re.match(r"^[A-Za-z][A-Za-z0-9 ]+$", stripped)
            and not stripped.lower().startswith(
                ("state ", "title ", "note ", "legend ", "skinparam ")
            )
        ):
            repaired.append(f"title {stripped}")
            changed = True
        else:
            repaired.append(raw_line)
    return normalize_puml_text("\n".join(repaired)) if changed else puml_text


def _run_deterministic_syntax_repairs(
    puml_text: str,
    validation: ValidationResult,
    max_passes: int = 10,
) -> tuple[str, ValidationResult]:
    candidate = puml_text
    candidate_validation = validation
    for _ in range(max_passes):
        repaired = _deterministic_syntax_repair(candidate, candidate_validation)
        if repaired == candidate:
            break
        candidate = repaired
        _, candidate_validation = parse_and_validate_puml_text(candidate)
        if not _has_plantuml_syntax_error(candidate_validation):
            break
    return candidate, candidate_validation


def _extract_transition_patch_lines(text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("```") or stripped.startswith("'"):
            continue
        if stripped.lower() in {"@startuml", "@enduml"}:
            continue
        if TRANSITION_RE.match(stripped):
            normalized = " ".join(stripped.split())
            if normalized not in seen:
                lines.append(stripped)
                seen.add(normalized)
    return lines


def _apply_transition_patch(puml_text: str, patch_lines: list[str]) -> str:
    base = normalize_puml_text(puml_text)
    if not patch_lines:
        return base

    existing = {" ".join(line.strip().split()) for line in base.splitlines()}
    new_lines = [line for line in patch_lines if " ".join(line.strip().split()) not in existing]
    if not new_lines:
        return base

    lines = base.splitlines()
    insert_at = len(lines)
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip().lower() == "@enduml":
            insert_at = index
            break
    patched = lines[:insert_at] + new_lines + lines[insert_at:]
    return normalize_puml_text("\n".join(patched))


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
    repair_example_dataset: Path | None = None,
    repair_examples_per_issue: int = 2,
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
            target_issue = ""
            target_issue_key = ""
            repair_route = ""

            repair_mode_clean = repair_mode.strip().lower()
            if (
                repair_mode_clean in {
                    "compiler_guided_syntax",
                    "compiler_guided_issue_routed",
                }
                and _has_plantuml_syntax_error(final_validation)
            ):
                deterministic_puml, deterministic_validation = _run_deterministic_syntax_repairs(
                    final_puml,
                    final_validation,
                )
                if deterministic_puml != final_puml:
                    deterministic_issues = strict_state_diagram_issues(deterministic_validation)
                    current_score = validation_repair_score(final_validation)
                    deterministic_score = validation_repair_score(deterministic_validation)
                    accepted = (
                        not _has_plantuml_syntax_error(deterministic_validation)
                        and deterministic_score < current_score
                    )
                    attempt_artifacts.append(
                        {
                            "stage": "compiler_deterministic_repair",
                            "attempt": attempt,
                            "repair_mode": repair_mode_clean,
                            "puml": deterministic_puml,
                            "validation": deterministic_validation.to_dict(),
                            "strict_state_diagram_valid": not deterministic_issues,
                            "accepted": accepted,
                            "previous_score": current_score,
                            "repair_score": deterministic_score,
                        }
                    )
                    steps.append(
                        {
                            "stage": "compiler_deterministic_repair",
                            "attempt": attempt,
                            "accepted": accepted,
                            "repair_mode": repair_mode_clean,
                            "errors": list(deterministic_validation.errors),
                            "warnings": list(deterministic_validation.warnings),
                        }
                    )
                    if accepted:
                        final_puml = deterministic_puml
                        final_validation = deterministic_validation
                        current_issues = deterministic_issues
                        if not current_issues:
                            break

            if repair_mode_clean == "constrained_validator":
                deterministic_puml = _deterministic_validator_repair(final_puml, final_validation)
                if deterministic_puml != final_puml:
                    _, deterministic_validation = parse_and_validate_puml_text(deterministic_puml)
                    deterministic_issues = strict_state_diagram_issues(deterministic_validation)
                    current_score = validation_repair_score(final_validation)
                    deterministic_score = validation_repair_score(deterministic_validation)
                    accepted = deterministic_score < current_score
                    attempt_artifacts.append(
                        {
                            "stage": "deterministic_repair",
                            "attempt": attempt,
                            "repair_mode": repair_mode_clean,
                            "puml": deterministic_puml,
                            "validation": deterministic_validation.to_dict(),
                            "strict_state_diagram_valid": not deterministic_issues,
                            "accepted": accepted,
                            "previous_score": current_score,
                            "repair_score": deterministic_score,
                        }
                    )
                    steps.append(
                        {
                            "stage": "deterministic_repair",
                            "attempt": attempt,
                            "accepted": accepted,
                            "repair_mode": repair_mode_clean,
                            "previous_score": current_score,
                            "repair_score": deterministic_score,
                            "plantuml_valid": deterministic_validation.valid,
                            "strict_state_diagram_valid": not deterministic_issues,
                            "errors": list(deterministic_validation.errors),
                            "warnings": list(deterministic_validation.warnings),
                            "strict_issues": deterministic_issues,
                        }
                    )
                    if accepted:
                        final_puml = deterministic_puml
                        final_validation = deterministic_validation
                        current_issues = deterministic_issues
                        if not current_issues:
                            break

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
            elif repair_mode_clean == "syntax_grounded_no_rules":
                repair_prompt = build_syntax_grounded_no_rules_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "diagnostic_syntax_grounded":
                repair_prompt = build_diagnostic_syntax_grounded_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "compiler_guided_syntax":
                repair_prompt = build_compiler_guided_syntax_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "compiler_guided_issue_routed":
                prioritized_issues = _prioritized_repair_issues(final_validation)
                target_issue = prioritized_issues[0] if prioritized_issues else ""
                target_issue_key = _repair_issue_key(target_issue) if target_issue else ""
                repair_route = _issue_repair_route(target_issue) if target_issue else ""
                repair_prompt = build_issue_routed_sequential_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                    route=repair_route,
                )
            elif repair_mode_clean == "constrained_validator":
                repair_prompt = build_constrained_validator_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "transition_patch":
                repair_prompt = build_transition_patch_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "hybrid_issue_guided":
                repair_prompt = build_hybrid_issue_guided_repair_prompt(
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
            elif repair_mode_clean == "example_guided":
                repair_prompt = build_example_guided_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                    repair_example_dataset=repair_example_dataset,
                    examples_per_issue=repair_examples_per_issue,
                    exclude_example_case_id=case.case_id,
                )
            elif repair_mode_clean == "sequential_example_guided":
                repair_prompt = build_sequential_example_guided_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                    repair_example_dataset=repair_example_dataset,
                    examples_per_issue=repair_examples_per_issue,
                    exclude_example_case_id=case.case_id,
                )
            elif repair_mode_clean == "sequential_baseline":
                repair_prompt = build_sequential_baseline_repair_prompt(
                    requirement,
                    final_puml,
                    final_validation,
                    critic_feedback,
                )
            elif repair_mode_clean == "sequential_syntax_grounded_pattern_rules":
                repair_prompt = build_sequential_syntax_grounded_pattern_rules_repair_prompt(
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
            patch_lines: list[str] = []
            if repair_mode_clean == "transition_patch":
                patch_lines = _extract_transition_patch_lines(repaired)
                repaired_puml = _apply_transition_patch(final_puml, patch_lines)
            else:
                repaired_puml = normalize_puml_text(repaired)
            _, repaired_validation = parse_and_validate_puml_text(repaired_puml)
            repaired_issues = strict_state_diagram_issues(repaired_validation)
            current_score = validation_repair_score(final_validation)
            repaired_score = validation_repair_score(repaired_validation)
            preserves_shape, preservation_meta = repair_preserves_graph_shape(final_puml, repaired_puml)
            syntax_was_invalid = _has_plantuml_syntax_error(final_validation)
            compiler_acceptance = not (
                repair_mode_clean in {
                    "compiler_guided_syntax",
                    "compiler_guided_issue_routed",
                }
                and syntax_was_invalid
                and _has_plantuml_syntax_error(repaired_validation)
            )
            routed_acceptance = True
            if repair_mode_clean == "compiler_guided_issue_routed":
                current_keys = _validation_issue_keys(final_validation)
                repaired_keys = _validation_issue_keys(repaired_validation)
                target_solved = bool(target_issue_key) and target_issue_key not in repaired_keys
                introduced_keys = repaired_keys - current_keys
                routed_acceptance = target_solved and not introduced_keys
            accepted = compiler_acceptance and routed_acceptance and repaired_score < current_score and (
                repair_mode_clean != "targeted" or preserves_shape or repaired_score == 0
            )
            attempt_artifacts.append(
                {
                    "stage": "repair",
                    "attempt": attempt,
                    "repair_mode": repair_mode_clean,
                    "repair_model_name": repair_model_name.strip() or cfg.model_name,
                    "target_issue": target_issue,
                    "target_issue_key": target_issue_key,
                    "repair_route": repair_route,
                    "repair_prompt": repair_prompt,
                    "transition_patch_lines": patch_lines,
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
                    "target_issue": target_issue,
                    "target_issue_key": target_issue_key,
                    "repair_route": repair_route,
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
