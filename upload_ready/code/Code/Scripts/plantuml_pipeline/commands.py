from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

from .constants import PROJECT_ROOT
from .dataset import build_experiment_configs, load_cases, stratified_split_cases
from .ensemble import (
    build_puml_from_graph,
    collect_candidates_from_run_ids,
    collect_ensemble_candidates,
    majority_vote_graph,
    run_stacked_ensemble,
    safe_strategy_tag,
)
from .generation import run_single_generation
from .io_utils import read_text, write_json, write_jsonl, write_text
from .metrics import compute_metrics, summarize_metrics
from .models import ValidationResult
from .parser import parse_and_validate_puml_text
from .prompting import load_rag_docs, tokenize


def _resolve_root(path_arg: str, parent: Path | None = None) -> Path:
    path = Path(path_arg)
    if path.is_absolute():
        return path
    if parent is None:
        return (PROJECT_ROOT / path).resolve()
    return (parent / path).resolve()


def _case_rag_docs(cases: list[Any]) -> list[tuple[str, str, set[str]]]:
    docs: list[tuple[str, str, set[str]]] = []
    for case in cases:
        content = (
            f"Case ID: {case.case_id}\n"
            f"Complexity: {case.complexity}\n\n"
            f"Requirement:\n{case.structured_requirement or case.raw_requirement}\n\n"
            f"Reference PlantUML:\n{case.gold_puml}\n"
        )
        name = f"{case.case_id}.txt"
        docs.append((name, content, tokenize(content)))
    return docs


def _existing_base_run_for_repair(
    results_root: Path,
    cfg: Any,
    case_id: str,
    run_index: int,
    few_shot_count: int,
) -> dict[str, str] | None:
    if not cfg.use_structural_validation:
        return None

    base_run_id = ""
    source_strategy = ""
    if cfg.strategy == "few_shot_validation_generator_critic_repair":
        if few_shot_count == 1:
            base_run_id = cfg.run_id.replace(
                "__one_shot_validation_generator_critic_repair",
                "__one_shot",
            )
            source_strategy = "one_shot"
        else:
            base_run_id = cfg.run_id.replace(
                "__few_shot_validation_generator_critic_repair",
                "__few_shot",
            )
            source_strategy = "few_shot"
    elif cfg.strategy == "rag_validation_generator_critic_repair":
        base_run_id = cfg.run_id.replace(
            "__rag_validation_generator_critic_repair",
            "__rag",
        )
        source_strategy = "rag"
    elif cfg.strategy == "zero_shot_validation_generator_critic_repair":
        base_run_id = cfg.run_id.replace(
            "__zero_shot_validation_generator_critic_repair",
            "__zero_shot",
        )
        source_strategy = "zero_shot"

    if not base_run_id:
        return None

    base_dir = results_root / "runs" / base_run_id / case_id
    puml_path = base_dir / f"run_{run_index:02d}.puml"
    if not puml_path.exists():
        return None

    prompt_path = base_dir / f"run_{run_index:02d}.prompt.txt"
    return {
        "run_id": base_run_id,
        "strategy": source_strategy,
        "puml_path": str(puml_path),
        "prompt_path": str(prompt_path) if prompt_path.exists() else "",
    }


def command_split(args: argparse.Namespace) -> int:
    dataset_root = _resolve_root(args.dataset_root)
    output_path = _resolve_root(args.output)
    cases = load_cases(dataset_root)
    _, _, split_meta = stratified_split_cases(
        cases=cases,
        test_size=args.test_size,
        seed=args.seed,
    )
    write_json(output_path, split_meta)
    print(
        f"Wrote split: {output_path} "
        f"(test={split_meta['test_count']}, rag={split_meta['rag_count']})"
    )
    return 0


def command_ensemble(args: argparse.Namespace) -> int:
    dataset_root = _resolve_root(args.dataset_root)
    results_root = _resolve_root(args.results_root)
    ensemble_root = _resolve_root(args.ensemble_root, parent=results_root)
    ensemble_method = str(args.ensemble_method).strip().lower()
    stack_rag_mode = str(args.stack_rag_mode).strip().lower()
    stack_rag_domain_hints = {
        s.strip().lower() for s in (args.stack_rag_domain_hint or []) if s.strip()
    }
    stack_rag_docs_dir = _resolve_root(args.stack_rag_docs_dir)
    stack_rag_db_dir = _resolve_root(args.stack_rag_db_dir)
    stack_rag_docs: list[tuple[str, str, set[str]]] = []

    cases = load_cases(dataset_root)
    case_by_id = {c.case_id: c for c in cases}
    default_pool_strategies = [
        "zero_shot",
        "one_shot",
        "few_shot",
        "rag",
        "rag_validation_generator_critic_repair",
    ]
    candidate_run_ids = [s.strip() for s in (args.candidate_run_id or []) if s.strip()]
    if not candidate_run_ids and not args.strategy:
        candidate_run_ids = [
            f"{prefix}__{strategy}"
            for prefix in [
                args.qwen_run_prefix,
                args.llama_run_prefix,
                args.deepseek_run_prefix,
            ]
            for strategy in default_pool_strategies
        ]
    strategies = (
        ["candidate_pool"]
        if candidate_run_ids
        else (
            args.strategy
            if args.strategy
            else default_pool_strategies
        )
    )
    strategies = [safe_strategy_tag(s) for s in strategies]

    metrics_rows: list[dict[str, Any]] = []
    produced_runs = 0
    skipped_cases = 0

    for strategy in strategies:
        method_tag = ensemble_method
        if ensemble_method == "stacked_llm" and args.stack_use_rag:
            method_tag = "stacked_llm_rag"
        source_tag = "all_methods" if candidate_run_ids else "by_strategy"
        run_id = f"ensemble__{source_tag}__{strategy}__{method_tag}"
        for case_id in sorted(case_by_id.keys()):
            case = case_by_id[case_id]
            if candidate_run_ids:
                candidates = collect_candidates_from_run_ids(
                    results_root=results_root,
                    case_id=case_id,
                    run_ids=candidate_run_ids,
                )
            else:
                candidates = collect_ensemble_candidates(
                    results_root=results_root,
                    case_id=case_id,
                    strategy=strategy,
                    qwen_prefix=args.qwen_run_prefix,
                    llama_prefix=args.llama_run_prefix,
                    deepseek_prefix=args.deepseek_run_prefix,
                )
            if len(candidates) < args.min_candidates:
                skipped_cases += 1
                continue

            model_set = {str(c["model"]) for c in candidates}
            if (
                not candidate_run_ids
                and args.require_both_models
                and not {"qwen", "llama"}.issubset(model_set)
            ):
                skipped_cases += 1
                continue

            status = "ok"
            error_message = ""
            stack_meta: dict[str, Any] = {}
            vote_meta: dict[str, Any] = {}

            try:
                if ensemble_method == "stacked_llm":
                    ensemble_puml, stack_meta = run_stacked_ensemble(
                        case=case,
                        candidates=candidates,
                        model_name=args.stack_model,
                        requirement_source=args.stack_requirement_source,
                        ollama_host=args.stack_ollama_host,
                        temperature=args.stack_temperature,
                        top_p=args.stack_top_p,
                        max_tokens=args.stack_max_tokens,
                        timeout=args.stack_timeout,
                        max_candidates=args.stack_max_candidates,
                        rag_docs=stack_rag_docs,
                        top_k_rag=args.stack_top_k_rag,
                        rag_max_chars_per_doc=args.stack_rag_max_chars_per_doc,
                        rag_domain_hints=stack_rag_domain_hints,
                        rag_mode=stack_rag_mode,
                        rag_db_dir=stack_rag_db_dir,
                        rag_collection_name=args.stack_rag_collection_name,
                    )
                else:
                    states, transitions, initial_state, final_states, vote_meta = majority_vote_graph(
                        candidates=candidates,
                        min_votes_override=args.min_votes,
                    )
                    ensemble_puml = build_puml_from_graph(
                        states=states,
                        transitions=transitions,
                        initial_state=initial_state,
                        final_states=final_states,
                    )
            except Exception as exc:  # noqa: BLE001 - keep per-case robustness
                if ensemble_method == "stacked_llm" and args.stack_fallback_majority:
                    error_message = str(exc)
                    status = "ok_fallback_majority"
                    states, transitions, initial_state, final_states, vote_meta = majority_vote_graph(
                        candidates=candidates,
                        min_votes_override=args.min_votes,
                    )
                    ensemble_puml = build_puml_from_graph(
                        states=states,
                        transitions=transitions,
                        initial_state=initial_state,
                        final_states=final_states,
                    )
                    stack_meta = {
                        "fallback_reason": error_message,
                        "fallback_used": "majority_vote",
                    }
                else:
                    status = "error"
                    error_message = str(exc)
                    ensemble_puml = "@startuml\n' ensemble generation error\n@enduml\n"

            ensemble_graph, ensemble_validation = parse_and_validate_puml_text(ensemble_puml)
            metrics = compute_metrics(
                pred_graph=ensemble_graph,
                pred_validation=ensemble_validation,
                gold_graph=case.gold_graph,
            )

            out_dir = ensemble_root / "runs" / run_id / case_id
            out_puml = out_dir / "ensemble.puml"
            out_meta = out_dir / "ensemble.meta.json"
            out_prompt = out_dir / "ensemble.prompt.txt"
            out_dir.mkdir(parents=True, exist_ok=True)
            write_text(out_puml, ensemble_puml)
            stack_prompt = str(stack_meta.get("prompt", "")) if stack_meta else ""
            if stack_prompt:
                write_text(out_prompt, stack_prompt)
                stack_meta["prompt_path"] = str(out_prompt)
                stack_meta.pop("prompt", None)

            metrics_row = {
                "run_id": run_id,
                "model_group": "ensemble",
                "model_label": (
                    f"Qwen+LLaMA+DeepSeek Stacked LLM ({args.stack_model})"
                    if ensemble_method == "stacked_llm"
                    else "Qwen+LLaMA+DeepSeek Majority Vote"
                ),
                "model_name": args.stack_model if ensemble_method == "stacked_llm" else "majority_vote",
                "strategy": strategy,
                "case_id": case_id,
                "complexity": case.complexity,
                "run_index": 1,
                "status": status,
                "error_message": error_message,
                "ensemble_method": ensemble_method,
                "candidate_count": len(candidates),
                "vote_threshold": vote_meta.get("vote_threshold"),
                **metrics,
            }
            metrics_rows.append(metrics_row)
            produced_runs += 1

            meta = {
                "run_id": run_id,
                "case_id": case_id,
                "status": status,
                "error_message": error_message,
                "ensemble_method": ensemble_method,
                "candidate_count": len(candidates),
                "source_runs": [
                    {"run_id": c["run_id"], "model": c["model"], "puml_path": c["puml_path"]}
                    for c in candidates
                ],
                "validation": ensemble_validation.to_dict(),
                "metrics": metrics,
                "puml_path": str(out_puml),
            }
            if vote_meta:
                meta["vote_meta"] = vote_meta
            if stack_meta:
                meta["stack_meta"] = stack_meta
            write_json(out_meta, meta)

    metrics_dir = ensemble_root / "metrics"
    write_jsonl(metrics_dir / "per_run_metrics.jsonl", metrics_rows)
    summary_cfg, summary_cmp, stability_rows = summarize_metrics(metrics_rows)
    write_json(metrics_dir / "summary_by_config.json", summary_cfg)
    write_json(metrics_dir / "summary_by_config_and_complexity.json", summary_cmp)
    write_jsonl(metrics_dir / "stability_by_case.jsonl", stability_rows)

    manifest = {
        "dataset_root": str(dataset_root),
        "results_root": str(results_root),
        "ensemble_root": str(ensemble_root),
        "strategies": strategies,
        "qwen_run_prefix": args.qwen_run_prefix,
        "llama_run_prefix": args.llama_run_prefix,
        "deepseek_run_prefix": args.deepseek_run_prefix,
        "candidate_run_ids": candidate_run_ids,
        "ensemble_method": ensemble_method,
        "min_candidates": args.min_candidates,
        "min_votes": args.min_votes,
        "require_both_models": args.require_both_models,
        "stack_model": args.stack_model if ensemble_method == "stacked_llm" else "",
        "stack_requirement_source": args.stack_requirement_source,
        "stack_use_rag": args.stack_use_rag,
        "stack_rag_mode": stack_rag_mode,
        "stack_rag_docs_dir": str(stack_rag_docs_dir),
        "stack_rag_db_dir": str(stack_rag_db_dir),
        "stack_rag_collection_name": args.stack_rag_collection_name,
        "stack_rag_doc_count": len(stack_rag_docs),
        "stack_top_k_rag": args.stack_top_k_rag,
        "stack_rag_max_chars_per_doc": args.stack_rag_max_chars_per_doc,
        "stack_rag_domain_hints": sorted(stack_rag_domain_hints),
        "stack_max_candidates": args.stack_max_candidates,
        "stack_temperature": args.stack_temperature,
        "stack_top_p": args.stack_top_p,
        "stack_max_tokens": args.stack_max_tokens,
        "stack_timeout": args.stack_timeout,
        "stack_ollama_host": args.stack_ollama_host,
        "stack_fallback_majority": args.stack_fallback_majority,
        "produced_case_runs": produced_runs,
        "skipped_case_runs": skipped_cases,
        "generated_at_epoch": time.time(),
    }
    write_json(ensemble_root / "manifest.json", manifest)
    print(
        f"Ensemble complete ({ensemble_method}): produced={produced_runs}, skipped={skipped_cases}, "
        f"metrics={metrics_dir / 'summary_by_config.json'}"
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    puml_path = _resolve_root(args.puml)
    if not puml_path.exists():
        print(f"File not found: {puml_path}", file=sys.stderr)
        return 1

    text = read_text(puml_path)
    graph, validation = parse_and_validate_puml_text(text)
    payload = {
        "file": str(puml_path),
        "validation": validation.to_dict(),
        "graph": {
            "states": sorted(graph.states),
            "transitions": sorted(list(set(graph.transitions))),
            "initial_targets": sorted(set(graph.initial_targets)),
            "final_states": sorted(graph.final_states),
            "aliases": graph.aliases,
        },
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"File: {payload['file']}")
        print(f"Valid: {payload['validation']['valid']}")
        print(f"States ({len(payload['graph']['states'])}): {', '.join(payload['graph']['states'])}")
        print(f"Transitions ({len(payload['graph']['transitions'])})")
        if payload["validation"]["errors"]:
            print("Errors:")
            for err in payload["validation"]["errors"]:
                print(f"  - {err}")
        if payload["validation"]["warnings"]:
            print("Warnings:")
            for warn in payload["validation"]["warnings"]:
                print(f"  - {warn}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    dataset_root = _resolve_root(args.dataset_root)
    results_root = _resolve_root(args.results_root)
    rag_docs_dir = _resolve_root(args.rag_docs_dir)
    rag_db_dir = _resolve_root(args.rag_db_dir)
    split_output = _resolve_root(args.split_output)
    rag_mode = str(args.rag_mode).strip().lower()
    rag_domain_hints = {s.strip().lower() for s in (args.rag_domain_hint or []) if s.strip()}

    cases = load_cases(dataset_root)
    for case in cases:
        if not case.gold_validation.valid:
            print(
                f"Warning: gold diagram in {case.case_id} failed validation: "
                f"{'; '.join(case.gold_validation.errors)}",
                file=sys.stderr,
            )

    test_cases, rag_cases, split_meta = stratified_split_cases(
        cases=cases,
        test_size=args.test_size,
        seed=args.seed,
    )
    write_json(split_output, split_meta)

    rag_docs: list[tuple[str, str, set[str]]] = []

    configs = build_experiment_configs(
        qwen_model=args.qwen_model,
        qwen14_model=args.qwen14_model,
        mistral_model=args.mistral_model,
        llama_model=args.llama_model,
        llama70_model=args.llama70_model,
        deepseek_model=args.deepseek_model,
        deepseek14_model=args.deepseek14_model,
        rag_ablation_tag=args.rag_ablation_tag,
    )

    if args.few_shot_count == 1:
        for cfg in configs:
            if cfg.strategy == "few_shot":
                cfg.run_id = cfg.run_id.replace("__few_shot", "__one_shot")
            elif cfg.strategy == "few_shot_validation_generator_critic_repair":
                cfg.run_id = cfg.run_id.replace(
                    "__few_shot_validation_generator_critic_repair",
                    "__one_shot_validation_generator_critic_repair",
                )

    if args.only_run_id:
        wanted = set(args.only_run_id)
        if args.few_shot_count == 1:
            wanted |= {run_id.replace("__few_shot", "__one_shot") for run_id in wanted}
            wanted |= {
                run_id.replace(
                    "__few_shot_validation_generator_critic_repair",
                    "__one_shot_validation_generator_critic_repair",
                )
                for run_id in wanted
            }
        configs = [cfg for cfg in configs if cfg.run_id in wanted]
        if not configs:
            print("No configurations matched --only-run-id", file=sys.stderr)
            return 1

    if args.only_case_id:
        wanted_cases = set(args.only_case_id)
        test_cases = [case for case in test_cases if case.case_id in wanted_cases]
        missing_cases = sorted(wanted_cases - {case.case_id for case in test_cases})
        if missing_cases:
            print(
                "No test-split cases matched --only-case-id: " + ", ".join(missing_cases),
                file=sys.stderr,
            )
            return 1

    manifest = {
        "generated_at_epoch": time.time(),
        "dataset_root": str(dataset_root),
        "results_root": str(results_root),
        "rag_docs_dir": str(rag_docs_dir),
        "rag_mode": rag_mode,
        "rag_db_dir": str(rag_db_dir),
        "rag_collection_name": args.rag_collection_name,
        "rag_doc_count": len(rag_docs),
        "split_output": str(split_output),
        "test_size": args.test_size,
        "test_case_count": len(test_cases),
        "rag_case_count": len(rag_cases),
        "test_case_ids": [c.case_id for c in test_cases],
        "rag_case_ids": [c.case_id for c in rag_cases],
        "use_case_rag": bool(args.use_case_rag),
        "rag_top_k": args.top_k_rag,
        "rag_max_chars_per_doc": args.rag_max_chars_per_doc,
        "rag_domain_hints": sorted(rag_domain_hints),
        "runs_per_case": args.runs,
        "few_shot_count": args.few_shot_count,
        "repair_attempts": args.repair_attempts,
        "configs": [cfg.to_dict() for cfg in configs],
    }
    write_json(results_root / "manifest.json", manifest)

    metrics_rows: list[dict[str, Any]] = []

    for cfg in configs:
        selected_cases = test_cases
        print(f"[run] {cfg.run_id} | cases={len(selected_cases)}")
        for case in selected_cases:
            for run_index in range(1, args.runs + 1):
                run_dir = results_root / "runs" / cfg.run_id / case.case_id
                puml_path = run_dir / f"run_{run_index:02d}.puml"
                meta_path = run_dir / f"run_{run_index:02d}.meta.json"
                if args.skip_existing and puml_path.exists() and meta_path.exists():
                    print(f"  skip existing {cfg.run_id}/{case.case_id}/run_{run_index:02d}")
                    continue

                status = "ok"
                error_message = ""
                prompt_text = ""
                requirement_used = ""
                processing_steps: list[dict[str, Any]] = []
                attempt_artifacts: list[dict[str, Any]] = []
                final_puml = ""
                final_validation: ValidationResult | None = None
                reused_base: dict[str, str] | None = None

                try:
                    reused_base = _existing_base_run_for_repair(
                        results_root=results_root,
                        cfg=cfg,
                        case_id=case.case_id,
                        run_index=run_index,
                        few_shot_count=args.few_shot_count,
                    )
                    (
                        final_puml,
                        final_validation,
                        prompt_text,
                        requirement_used,
                        processing_steps,
                        attempt_artifacts,
                    ) = (
                        run_single_generation(
                            case=case,
                            cfg=cfg,
                            all_cases=rag_cases,
                            rag_docs=rag_docs,
                            requirement_source=args.requirement_source,
                            top_k_rag=args.top_k_rag,
                            ollama_host=args.ollama_host,
                            temperature=args.temperature,
                            top_p=args.top_p,
                            max_tokens=args.max_tokens,
                            timeout=args.timeout,
                            rag_max_chars_per_doc=args.rag_max_chars_per_doc,
                            rag_domain_hints=rag_domain_hints,
                            rag_mode=rag_mode,
                            rag_db_dir=rag_db_dir,
                            rag_collection_name=args.rag_collection_name,
                            few_shot_seed=args.few_shot_seed,
                            few_shot_count=args.few_shot_count,
                            run_index=run_index,
                            repair_attempts=args.repair_attempts,
                            initial_puml=read_text(Path(reused_base["puml_path"]))
                            if reused_base
                            else None,
                            initial_prompt=read_text(Path(reused_base["prompt_path"]))
                            if reused_base and reused_base.get("prompt_path")
                            else "",
                            initial_source=reused_base["run_id"] if reused_base else "",
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - preserve all run errors
                    status = "error"
                    error_message = str(exc)
                    final_puml = "@startuml\n' generation error\n@enduml\n"
                    final_graph, final_validation = parse_and_validate_puml_text(final_puml)
                    processing_steps.append({"stage": "error", "message": error_message})
                else:
                    final_graph, final_validation = parse_and_validate_puml_text(final_puml)

                run_dir.mkdir(parents=True, exist_ok=True)
                write_text(puml_path, final_puml)
                if args.save_prompts and prompt_text:
                    prompt_path = run_dir / f"run_{run_index:02d}.prompt.txt"
                    write_text(prompt_path, prompt_text)
                for artifact in attempt_artifacts:
                    artifact_stage = str(artifact.get("stage", "attempt"))
                    artifact_attempt = int(artifact.get("attempt", 0))
                    if artifact_stage == "initial":
                        artifact_path = run_dir / f"run_{run_index:02d}.initial.puml"
                    else:
                        artifact_path = run_dir / f"run_{run_index:02d}.{artifact_stage}_{artifact_attempt:02d}.puml"
                    write_text(artifact_path, str(artifact.get("puml", "")))
                    artifact["path"] = str(artifact_path)
                    artifact.pop("puml", None)
                    critic_prompt = str(artifact.get("critic_prompt", ""))
                    if args.save_prompts and critic_prompt:
                        critic_prompt_path = (
                            run_dir / f"run_{run_index:02d}.critic_{artifact_attempt:02d}.prompt.txt"
                        )
                        write_text(critic_prompt_path, critic_prompt)
                        artifact["critic_prompt_path"] = str(critic_prompt_path)
                    artifact.pop("critic_prompt", None)
                    repair_prompt = str(artifact.get("repair_prompt", ""))
                    if args.save_prompts and repair_prompt:
                        repair_prompt_path = (
                            run_dir / f"run_{run_index:02d}.repair_{artifact_attempt:02d}.prompt.txt"
                        )
                        write_text(repair_prompt_path, repair_prompt)
                        artifact["repair_prompt_path"] = str(repair_prompt_path)
                    artifact.pop("repair_prompt", None)

                metrics = compute_metrics(
                    pred_graph=final_graph,
                    pred_validation=final_validation,
                    gold_graph=case.gold_graph,
                )
                strict_issues = list(final_validation.errors) + list(final_validation.warnings)
                metrics["strict_state_diagram_valid"] = not strict_issues
                metrics["strict_state_diagram_issues"] = strict_issues
                metrics_row = {
                    "run_id": cfg.run_id,
                    "model_group": cfg.model_group,
                    "model_label": cfg.model_label,
                    "model_name": cfg.model_name,
                    "strategy": cfg.strategy,
                    "case_id": case.case_id,
                    "complexity": case.complexity,
                    "run_index": run_index,
                    "status": status,
                    "error_message": error_message,
                    **metrics,
                }
                metrics_rows.append(metrics_row)

                meta = {
                    "run_id": cfg.run_id,
                    "case_id": case.case_id,
                    "run_index": run_index,
                    "status": status,
                    "error_message": error_message,
                    "prompt": prompt_text if args.save_prompts else "",
                    "requirement_used": requirement_used if args.save_prompts else "",
                    "puml_path": str(puml_path),
                    "validation": final_validation.to_dict(),
                    "strict_validation": {
                        "valid": not strict_issues,
                        "issues": strict_issues,
                    },
                    "processing_steps": processing_steps,
                    "attempt_artifacts": attempt_artifacts,
                    "metrics": metrics,
                }
                if reused_base:
                    meta["reused_base_run"] = reused_base
                write_json(meta_path, meta)
                print(
                    f"  {case.case_id}/run_{run_index:02d} "
                    f"status={status} valid={metrics['structural_valid']} "
                    f"overall_f1={metrics['overall_f1']:.4f}"
                )

    metrics_dir = results_root / "metrics"
    write_jsonl(metrics_dir / "per_run_metrics.jsonl", metrics_rows)
    summary_cfg, summary_cmp, stability_rows = summarize_metrics(metrics_rows)
    write_json(metrics_dir / "summary_by_config.json", summary_cfg)
    write_json(metrics_dir / "summary_by_config_and_complexity.json", summary_cmp)
    write_jsonl(metrics_dir / "stability_by_case.jsonl", stability_rows)

    print(f"Wrote metrics: {metrics_dir / 'per_run_metrics.jsonl'} ({len(metrics_rows)} rows)")
    return 0


def command_metrics(args: argparse.Namespace) -> int:
    dataset_root = _resolve_root(args.dataset_root)
    results_root = _resolve_root(args.results_root)

    cases = {case.case_id: case for case in load_cases(dataset_root)}
    runs_root = results_root / "runs"
    if not runs_root.exists():
        print(f"No runs directory found at: {runs_root}", file=sys.stderr)
        return 1

    metrics_rows: list[dict[str, Any]] = []
    for puml_path in sorted(runs_root.glob("*/*/run_*.puml")):
        run_id = puml_path.parent.parent.name
        case_id = puml_path.parent.name
        run_match = re.search(r"run_(\d+)\.puml$", puml_path.name)
        run_index = int(run_match.group(1)) if run_match else 0

        case = cases.get(case_id)
        if case is None:
            continue
        pred_puml = read_text(puml_path)
        pred_graph, pred_validation = parse_and_validate_puml_text(pred_puml)
        metrics = compute_metrics(pred_graph, pred_validation, case.gold_graph)
        metrics_rows.append(
            {
                "run_id": run_id,
                "case_id": case_id,
                "complexity": case.complexity,
                "run_index": run_index,
                **metrics,
            }
        )

    metrics_dir = results_root / "metrics"
    write_jsonl(metrics_dir / "per_run_metrics.jsonl", metrics_rows)
    summary_cfg, summary_cmp, stability_rows = summarize_metrics(metrics_rows)
    write_json(metrics_dir / "summary_by_config.json", summary_cfg)
    write_json(metrics_dir / "summary_by_config_and_complexity.json", summary_cmp)
    write_jsonl(metrics_dir / "stability_by_case.jsonl", stability_rows)
    print(f"Recomputed metrics for {len(metrics_rows)} run files")
    return 0


def _format_table_value(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return f"{value:.4f}"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("No rows to display.")
        return

    widths: dict[str, int] = {col: len(col) for col in columns}
    rendered_rows: list[dict[str, str]] = []
    for row in rows:
        rendered: dict[str, str] = {}
        for col in columns:
            text = _format_table_value(row.get(col, ""))
            rendered[col] = text
            widths[col] = max(widths[col], len(text))
        rendered_rows.append(rendered)

    header = " | ".join(col.ljust(widths[col]) for col in columns)
    sep = "-+-".join("-" * widths[col] for col in columns)
    print(header)
    print(sep)
    for row in rendered_rows:
        print(" | ".join(row[col].ljust(widths[col]) for col in columns))


def _sort_rows(
    rows: list[dict[str, Any]],
    sort_by: str,
    descending: bool,
) -> list[dict[str, Any]]:
    def key_fn(item: dict[str, Any]) -> tuple[int, Any]:
        value = item.get(sort_by)
        if value is None:
            return (1, "")
        return (0, value)

    return sorted(rows, key=key_fn, reverse=descending)


def command_table(args: argparse.Namespace) -> int:
    results_root = _resolve_root(args.results_root)

    metrics_dir = results_root / "metrics"
    source_map = {
        "summary": "summary_by_config.json",
        "complexity": "summary_by_config_and_complexity.json",
        "per-run": "per_run_metrics.jsonl",
    }
    source_file = metrics_dir / source_map[args.source]
    if not source_file.exists():
        print(
            f"Metrics source not found: {source_file}\n"
            "Run `metrics` first or complete a `run` execution.",
            file=sys.stderr,
        )
        return 1

    rows: list[dict[str, Any]] = []
    if source_file.suffix == ".jsonl":
        with source_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    else:
        rows = json.loads(source_file.read_text(encoding="utf-8"))

    # Add a derived percentage field for convenient reporting.
    for row in rows:
        if "structural_valid_rate" in row:
            try:
                row["structural_valid_percentage"] = float(row["structural_valid_rate"]) * 100.0
            except Exception:
                row["structural_valid_percentage"] = None
        elif "structural_valid" in row:
            row["structural_valid_percentage"] = 100.0 if bool(row["structural_valid"]) else 0.0

    if args.model_family != "all":
        family_patterns = {
            "qwen": "qwen25_7b_instruct",
            "llama": "llama31_8b_instruct",
            "ensemble": "ensemble__",
        }
        pattern = family_patterns.get(args.model_family, "")
        rows = [row for row in rows if pattern in str(row.get("run_id", ""))]

    if args.run_id:
        rows = [row for row in rows if str(row.get("run_id", "")) in set(args.run_id)]

    if args.source == "summary":
        default_columns = [
            "run_id",
            "samples",
            "overall_f1_mean",
            "overall_f1_relaxed_mean",
            "weighted_f1_relaxed_70_30_mean",
            "state_f1_mean",
            "transition_f1_mean",
            "structural_valid_rate",
            "stability_overall_f1_stddev_mean",
        ]
        default_sort = "overall_f1_mean"
    elif args.source == "complexity":
        default_columns = [
            "run_id",
            "complexity",
            "samples",
            "overall_f1_mean",
            "overall_f1_relaxed_mean",
            "weighted_f1_relaxed_70_30_mean",
            "state_f1_mean",
            "transition_f1_mean",
            "structural_valid_rate",
        ]
        default_sort = "overall_f1_mean"
    else:
        default_columns = [
            "run_id",
            "case_id",
            "run_index",
            "status",
            "overall_f1",
            "state_f1",
            "transition_f1",
            "structural_valid",
        ]
        default_sort = "overall_f1"

    if args.structural_only:
        if args.source == "summary":
            default_columns = ["run_id", "samples", "structural_valid_percentage"]
        elif args.source == "complexity":
            default_columns = ["run_id", "complexity", "samples", "structural_valid_percentage"]
        else:
            default_columns = [
                "run_id",
                "case_id",
                "run_index",
                "status",
                "structural_valid_percentage",
            ]
        default_sort = "structural_valid_percentage"

    columns = args.columns.split(",") if args.columns else default_columns
    columns = [col.strip() for col in columns if col.strip()]
    if not columns:
        print("No columns selected.", file=sys.stderr)
        return 1

    sort_by = args.sort_by or default_sort
    rows = _sort_rows(rows, sort_by=sort_by, descending=not args.asc)
    if args.limit > 0:
        rows = rows[: args.limit]

    if not rows:
        print("No rows matched filters.")
        return 0

    _print_table(rows, columns)
    print(f"\nRows shown: {len(rows)} | Source: {source_file}")
    return 0
