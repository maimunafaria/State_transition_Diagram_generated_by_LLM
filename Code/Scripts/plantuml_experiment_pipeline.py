#!/usr/bin/env python3
"""
All-in-one PlantUML experiment pipeline.

This script provides:
1) PlantUML parser + validator
2) Metrics calculator (semantic + structural)
3) Batch runner for 11 methodology configurations

Usage examples:
  python3 Code/Scripts/plantuml_experiment_pipeline.py validate --puml dataset/case_01_healthcare_portal/diagram.puml
  python3 Code/Scripts/plantuml_experiment_pipeline.py run --runs 3
  python3 Code/Scripts/plantuml_experiment_pipeline.py metrics
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib import error, request


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "plantuml_pipeline"
DEFAULT_RAG_DOCS_DIR = PROJECT_ROOT / "data" / "raw" / "rag_docs"


STATE_ALIAS_RE = re.compile(
    r'^\s*state\s+"(?P<label>[^"]+)"\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*$'
)
STATE_DECL_RE = re.compile(
    r'^\s*state\s+(?P<name>"[^"]+"|[A-Za-z_][A-Za-z0-9_\-\.]*)\s*$'
)
TRANSITION_RE = re.compile(
    r'^\s*(?P<src>\[\*\]|"[^"]+"|[^\s:]+)\s*-[^>]*->\s*(?P<dst>\[\*\]|"[^"]+"|[^\s:]+)(?:\s*:\s*(?P<event>.*))?\s*$'
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")


@dataclass
class Case:
    case_id: str
    path: Path
    raw_requirement: str
    structured_requirement: str
    gold_puml: str
    gold_graph: "DiagramGraph"
    gold_validation: "ValidationResult"
    complexity: str


@dataclass
class DiagramGraph:
    states: set[str]
    transitions: list[tuple[str, str, str]]
    initial_targets: list[str]
    final_states: set[str]
    aliases: dict[str, str]
    parse_errors: list[str]

    def transition_set(self) -> set[tuple[str, str, str]]:
        return set(self.transitions)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    initial_state: str | None
    duplicate_transition_count: int
    unreachable_states: list[str]
    state_count: int
    transition_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "initial_state": self.initial_state,
            "duplicate_transition_count": self.duplicate_transition_count,
            "unreachable_states": list(self.unreachable_states),
            "state_count": self.state_count,
            "transition_count": self.transition_count,
        }


@dataclass
class ExperimentConfig:
    run_id: str
    model_group: str
    model_label: str
    model_name: str
    strategy: str
    use_rag: bool
    use_structural_validation: bool
    use_ensemble: bool
    baseline_subset_only: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "model_group": self.model_group,
            "model_label": self.model_label,
            "model_name": self.model_name,
            "strategy": self.strategy,
            "use_rag": self.use_rag,
            "use_structural_validation": self.use_structural_validation,
            "use_ensemble": self.use_ensemble,
            "baseline_subset_only": self.baseline_subset_only,
        }


def sanitize_name(name: str) -> str:
    name = name.strip()
    if name.startswith('"') and name.endswith('"') and len(name) >= 2:
        name = name[1:-1]
    return " ".join(name.split())


def sanitize_event(event: str | None) -> str:
    if not event:
        return ""
    return " ".join(event.strip().split())


def normalize_puml_text(text: str) -> str:
    extracted = extract_plantuml_block(text)
    if extracted:
        return extracted
    clean = text.strip()
    if not clean:
        return "@startuml\n@enduml\n"
    return "@startuml\n" + clean + "\n@enduml\n"


def extract_plantuml_block(text: str) -> str:
    if not text:
        return ""
    start = text.find("@startuml")
    end = text.rfind("@enduml")
    if start != -1 and end != -1 and end >= start:
        return text[start : end + len("@enduml")].strip() + "\n"
    return ""


def strip_inline_comment(line: str) -> str:
    # PlantUML uses single quote for inline comments.
    if "'" in line:
        return line.split("'", 1)[0]
    return line


def parse_plantuml(puml_text: str) -> DiagramGraph:
    text = normalize_puml_text(puml_text)
    aliases: dict[str, str] = {}
    states: set[str] = set()
    transitions: list[tuple[str, str, str]] = []
    initial_targets: list[str] = []
    final_states: set[str] = set()
    parse_errors: list[str] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_inline_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("@"):
            continue
        if line.startswith("skinparam") or line.startswith("hide") or line.startswith("title"):
            continue

        alias_match = STATE_ALIAS_RE.match(line)
        if alias_match:
            label = sanitize_name(alias_match.group("label"))
            alias = alias_match.group("alias").strip()
            aliases[alias] = label
            states.add(label)
            continue

        state_match = STATE_DECL_RE.match(line)
        if state_match:
            state_name = sanitize_name(state_match.group("name"))
            if state_name and state_name != "[*]":
                states.add(state_name)
            continue

        trans_match = TRANSITION_RE.match(line)
        if trans_match:
            src_raw = sanitize_name(trans_match.group("src"))
            dst_raw = sanitize_name(trans_match.group("dst"))
            src = aliases.get(src_raw, src_raw)
            dst = aliases.get(dst_raw, dst_raw)
            event = sanitize_event(trans_match.group("event"))

            if src == "[*]" and dst != "[*]":
                initial_targets.append(dst)
                states.add(dst)
                continue

            if dst == "[*]" and src != "[*]":
                final_states.add(src)
                states.add(src)
                continue

            if src == "[*]" and dst == "[*]":
                parse_errors.append(f"line_{line_no}: invalid [*] -> [*] transition")
                continue

            if src:
                states.add(src)
            if dst:
                states.add(dst)
            if src and dst:
                transitions.append((src, event, dst))
            else:
                parse_errors.append(f"line_{line_no}: empty src/dst in transition")
            continue

    return DiagramGraph(
        states=states,
        transitions=transitions,
        initial_targets=initial_targets,
        final_states=final_states,
        aliases=aliases,
        parse_errors=parse_errors,
    )


def validate_graph(graph: DiagramGraph) -> ValidationResult:
    errors = list(graph.parse_errors)
    warnings: list[str] = []

    initial_candidates = sorted(set(graph.initial_targets))
    if not initial_candidates:
        errors.append("missing_initial_state_transition ([*] --> state)")
        initial_state = None
    elif len(initial_candidates) > 1:
        errors.append(f"multiple_initial_state_targets ({', '.join(initial_candidates)})")
        initial_state = None
    else:
        initial_state = initial_candidates[0]

    dup_count = len(graph.transitions) - len(set(graph.transitions))
    if dup_count > 0:
        errors.append(f"duplicate_transitions_detected ({dup_count})")

    unreachable: list[str] = []
    if initial_state:
        adjacency: dict[str, set[str]] = {s: set() for s in graph.states}
        for src, _, dst in graph.transitions:
            adjacency.setdefault(src, set()).add(dst)
            adjacency.setdefault(dst, set())

        visited: set[str] = set()
        stack = [initial_state]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            stack.extend(sorted(adjacency.get(node, set()) - visited))

        unreachable = sorted(graph.states - visited)
        if unreachable:
            errors.append("unreachable_states_detected")
            warnings.append("unreachable: " + ", ".join(unreachable))

    return ValidationResult(
        valid=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
        initial_state=initial_state,
        duplicate_transition_count=dup_count,
        unreachable_states=unreachable,
        state_count=len(graph.states),
        transition_count=len(set(graph.transitions)),
    )


def parse_and_validate_puml_text(puml_text: str) -> tuple[DiagramGraph, ValidationResult]:
    graph = parse_plantuml(puml_text)
    validation = validate_graph(graph)
    return graph, validation


def _to_set(items: Iterable[Any]) -> set[Any]:
    return set(items)


def prf(pred: set[Any], gold: set[Any]) -> tuple[float, float, float, int, int, int]:
    tp = len(pred & gold)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1, tp, fp, fn


def complexity_bucket(state_count: int) -> str:
    if state_count <= 3:
        return "simple"
    if state_count <= 7:
        return "medium"
    return "complex"


def compute_metrics(
    pred_graph: DiagramGraph,
    pred_validation: ValidationResult,
    gold_graph: DiagramGraph,
) -> dict[str, Any]:
    pred_states = _to_set(pred_graph.states)
    gold_states = _to_set(gold_graph.states)
    pred_transitions = _to_set(pred_graph.transitions)
    gold_transitions = _to_set(gold_graph.transitions)

    s_p, s_r, s_f1, s_tp, s_fp, s_fn = prf(pred_states, gold_states)
    t_p, t_r, t_f1, t_tp, t_fp, t_fn = prf(pred_transitions, gold_transitions)

    unsupported_states = len(pred_states - gold_states)
    unsupported_transitions = len(pred_transitions - gold_transitions)
    hallucination_states_rate = unsupported_states / len(pred_states) if pred_states else 0.0
    hallucination_transitions_rate = (
        unsupported_transitions / len(pred_transitions) if pred_transitions else 0.0
    )
    missing_transition_rate = t_fn / len(gold_transitions) if gold_transitions else 0.0
    overall_f1 = (s_f1 + t_f1) / 2.0

    return {
        "state_precision": s_p,
        "state_recall": s_r,
        "state_f1": s_f1,
        "state_tp": s_tp,
        "state_fp": s_fp,
        "state_fn": s_fn,
        "transition_precision": t_p,
        "transition_recall": t_r,
        "transition_f1": t_f1,
        "transition_tp": t_tp,
        "transition_fp": t_fp,
        "transition_fn": t_fn,
        "structural_valid": pred_validation.valid,
        "structural_errors": list(pred_validation.errors),
        "structural_warnings": list(pred_validation.warnings),
        "hallucination_state_rate": hallucination_states_rate,
        "hallucination_transition_rate": hallucination_transitions_rate,
        "missing_transition_rate": missing_transition_rate,
        "overall_f1": overall_f1,
    }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in WORD_RE.finditer(text)}


def load_rag_docs(rag_docs_dir: Path) -> list[tuple[str, str, set[str]]]:
    if not rag_docs_dir.exists():
        return []
    docs: list[tuple[str, str, set[str]]] = []
    for path in sorted(rag_docs_dir.iterdir()):
        if not path.is_file():
            continue
        content = read_text(path)
        docs.append((path.name, content, tokenize(content)))
    return docs


def retrieve_rag_context(
    query: str,
    docs: list[tuple[str, str, set[str]]],
    top_k: int,
    max_chars_per_doc: int = 1200,
) -> str:
    if top_k <= 0 or not docs:
        return ""
    query_tokens = tokenize(query)
    scored: list[tuple[int, int, str, str]] = []
    for name, content, tokens in docs:
        overlap = len(query_tokens & tokens)
        scored.append((overlap, len(tokens), name, content))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    chosen = [item for item in scored if item[0] > 0][:top_k]
    if not chosen:
        chosen = scored[:top_k]
    sections: list[str] = []
    for _, _, name, content in chosen:
        clipped = content[:max_chars_per_doc].strip()
        sections.append(f"[{name}]\n{clipped}")
    return "\n\n".join(sections)


def select_fewshot_examples(cases: list[Case], current_case_id: str, max_examples: int = 3) -> list[Case]:
    by_complexity: dict[str, list[Case]] = {"simple": [], "medium": [], "complex": []}
    for case in cases:
        if case.case_id == current_case_id:
            continue
        by_complexity.setdefault(case.complexity, []).append(case)

    selected: list[Case] = []
    for bucket in ("simple", "medium", "complex"):
        if by_complexity.get(bucket):
            selected.append(by_complexity[bucket][0])
            if len(selected) >= max_examples:
                return selected

    if len(selected) < max_examples:
        remainder = [c for c in cases if c.case_id != current_case_id and c not in selected]
        for case in remainder:
            selected.append(case)
            if len(selected) >= max_examples:
                break
    return selected


def build_generation_prompt(
    case: Case,
    cfg: ExperimentConfig,
    all_cases: list[Case],
    rag_docs: list[tuple[str, str, set[str]]],
    requirement_source: str,
    top_k_rag: int,
) -> str:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    parts: list[str] = [
        "You convert natural language software requirements into UML state machine diagrams in PlantUML format.",
        "Rules:",
        "- Output ONLY PlantUML code.",
        "- Start with @startuml and end with @enduml.",
        "- Use [*] for exactly one initial transition.",
        "- Use --> for transitions.",
        "- Include transition labels when requirement evidence exists.",
        "- Do not add explanations or markdown fences.",
    ]

    if cfg.strategy == "few_shot":
        examples = select_fewshot_examples(all_cases, case.case_id, max_examples=3)
        if examples:
            example_texts: list[str] = []
            for idx, ex in enumerate(examples, start=1):
                ex_req = ex.structured_requirement.strip() or ex.raw_requirement.strip()
                if len(ex_req) > 1200:
                    ex_req = ex_req[:1200].rstrip() + "..."
                ex_puml = ex.gold_puml.strip()
                if len(ex_puml) > 1800:
                    ex_puml = ex_puml[:1800].rstrip() + "\n@enduml"
                example_texts.append(
                    f"Example {idx} Requirement:\n{ex_req}\n\nExample {idx} PlantUML:\n{ex_puml}"
                )
            parts.append("Few-shot examples:")
            parts.append("\n\n".join(example_texts))

    if cfg.use_rag:
        rag_context = retrieve_rag_context(requirement, rag_docs, top_k=top_k_rag)
        if rag_context:
            parts.append("Reference context (support only, not mandatory):")
            parts.append(rag_context)

    parts.append("Target requirement:")
    parts.append(requirement)
    parts.append("Now return only the final PlantUML.")
    return "\n\n".join(parts).strip() + "\n"


def json_post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {raw[:500]}") from exc


def call_ollama(
    model: str,
    prompt: str,
    host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        },
    }
    data = json_post(
        url=f"{host.rstrip('/')}/api/generate",
        payload=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    return (data.get("response") or "").strip()


def call_openai_chat(
    model: str,
    prompt: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    data = json_post(
        url="https://api.openai.com/v1/chat/completions",
        payload=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=timeout,
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenAI returned no choices: {data}")
    content = choices[0].get("message", {}).get("content", "")
    return (content or "").strip()


def call_model(
    model_name: str,
    prompt: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    lower = model_name.lower()
    if lower.startswith("gpt-"):
        return call_openai_chat(
            model=model_name,
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    return call_ollama(
        model=model_name,
        prompt=prompt,
        host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def build_critic_prompt(requirement: str, candidate_puml: str, validation: ValidationResult) -> str:
    return (
        "You are a strict UML critic.\n"
        "Given a requirement and candidate PlantUML, identify structural and semantic issues.\n"
        "Do not rewrite the diagram. Return concise numbered issues only.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation errors:\n"
        + ("\n".join(f"- {err}" for err in validation.errors) if validation.errors else "- none")
    )


def build_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    feedback_block = critic_feedback.strip() or "No critic feedback provided."
    return (
        "You are a UML repair assistant.\n"
        "Repair the candidate PlantUML to satisfy the requirement and structural constraints.\n"
        "Output ONLY corrected PlantUML. No explanations.\n\n"
        "Constraints:\n"
        "- Include @startuml and @enduml\n"
        "- Exactly one initial transition [*] --> state\n"
        "- No duplicate transitions\n"
        "- All states should be reachable from the initial state when possible\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation errors:\n"
        + ("\n".join(f"- {err}" for err in validation.errors) if validation.errors else "- none")
        + "\n\nCritic feedback:\n"
        + feedback_block
    )


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
) -> tuple[str, ValidationResult, str, str, list[dict[str, Any]]]:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    steps: list[dict[str, Any]] = []
    prompt = build_generation_prompt(
        case=case,
        cfg=cfg,
        all_cases=all_cases,
        rag_docs=rag_docs,
        requirement_source=requirement_source,
        top_k_rag=top_k_rag,
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
    graph, validation = parse_and_validate_puml_text(generated_puml)
    steps.append({"stage": "generator", "valid": validation.valid, "errors": list(validation.errors)})

    final_puml = generated_puml
    final_validation = validation
    final_graph = graph

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
        repaired_graph, repaired_validation = parse_and_validate_puml_text(repaired_puml)
        final_puml = repaired_puml
        final_validation = repaired_validation
        final_graph = repaired_graph
        steps.append(
            {
                "stage": "repair",
                "valid": final_validation.valid,
                "errors": list(final_validation.errors),
            }
        )

    return final_puml, final_validation, prompt, requirement, steps


def summarize_metrics(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_config: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_config.setdefault(row["run_id"], []).append(row)

    summary_config: list[dict[str, Any]] = []
    summary_complexity: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []

    for run_id, group in sorted(by_config.items()):
        def mean(key: str) -> float:
            vals = [float(item.get(key, 0.0)) for item in group]
            return sum(vals) / len(vals) if vals else 0.0

        pass_rate = sum(1 for item in group if item.get("structural_valid")) / len(group)
        summary_config.append(
            {
                "run_id": run_id,
                "samples": len(group),
                "state_f1_mean": mean("state_f1"),
                "transition_f1_mean": mean("transition_f1"),
                "overall_f1_mean": mean("overall_f1"),
                "structural_valid_rate": pass_rate,
                "hallucination_state_rate_mean": mean("hallucination_state_rate"),
                "hallucination_transition_rate_mean": mean("hallucination_transition_rate"),
                "missing_transition_rate_mean": mean("missing_transition_rate"),
            }
        )

        by_complexity: dict[str, list[dict[str, Any]]] = {}
        for item in group:
            by_complexity.setdefault(item["complexity"], []).append(item)
        for complexity, cgroup in sorted(by_complexity.items()):
            summary_complexity.append(
                {
                    "run_id": run_id,
                    "complexity": complexity,
                    "samples": len(cgroup),
                    "state_f1_mean": sum(float(x["state_f1"]) for x in cgroup) / len(cgroup),
                    "transition_f1_mean": sum(float(x["transition_f1"]) for x in cgroup) / len(cgroup),
                    "overall_f1_mean": sum(float(x["overall_f1"]) for x in cgroup) / len(cgroup),
                    "structural_valid_rate": sum(1 for x in cgroup if x["structural_valid"]) / len(cgroup),
                }
            )

        # Stability: std-dev of overall_f1 across repeated runs for each case, then averaged.
        by_case: dict[str, list[dict[str, Any]]] = {}
        for item in group:
            by_case.setdefault(item["case_id"], []).append(item)
        stds: list[float] = []
        for case_id, crows in sorted(by_case.items()):
            vals = [float(x["overall_f1"]) for x in sorted(crows, key=lambda r: int(r["run_index"]))]
            std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            stds.append(std)
            stability_rows.append(
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "runs": len(vals),
                    "overall_f1_stddev": std,
                }
            )
        config_stability = sum(stds) / len(stds) if stds else 0.0
        for rec in summary_config:
            if rec["run_id"] == run_id:
                rec["stability_overall_f1_stddev_mean"] = config_stability
                break

    return summary_config, summary_complexity, stability_rows


def command_validate(args: argparse.Namespace) -> int:
    puml_path = Path(args.puml)
    if not puml_path.is_absolute():
        puml_path = (PROJECT_ROOT / puml_path).resolve()
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
    dataset_root = Path(args.dataset_root)
    if not dataset_root.is_absolute():
        dataset_root = (PROJECT_ROOT / dataset_root).resolve()
    results_root = Path(args.results_root)
    if not results_root.is_absolute():
        results_root = (PROJECT_ROOT / results_root).resolve()
    rag_docs_dir = Path(args.rag_docs_dir)
    if not rag_docs_dir.is_absolute():
        rag_docs_dir = (PROJECT_ROOT / rag_docs_dir).resolve()

    cases = load_cases(dataset_root)
    for case in cases:
        if not case.gold_validation.valid:
            print(
                f"Warning: gold diagram in {case.case_id} failed validation: "
                f"{'; '.join(case.gold_validation.errors)}",
                file=sys.stderr,
            )

    baseline_cases = balanced_subset(cases, target_size=args.baseline_subset_size, seed=args.seed)
    rag_docs = load_rag_docs(rag_docs_dir)

    configs = build_experiment_configs(
        gpt_model=args.gpt_model,
        qwen_model=args.qwen_model,
        llama_model=args.llama_model,
    )
    # Allow running open-source experiments without requiring OpenAI credentials.
    if args.skip_gpt_baseline:
        configs = [cfg for cfg in configs if cfg.model_group != "proprietary_baseline"]
    elif not os.getenv("OPENAI_API_KEY", "").strip():
        configs = [cfg for cfg in configs if cfg.model_group != "proprietary_baseline"]
        print(
            "[info] OPENAI_API_KEY not set, skipping GPT-4o baseline. "
            "Use --gpt-model with key configured to include it.",
            file=sys.stderr,
        )

    if args.only_run_id:
        wanted = set(args.only_run_id)
        configs = [cfg for cfg in configs if cfg.run_id in wanted]
        if not configs:
            print("No configurations matched --only-run-id", file=sys.stderr)
            return 1

    manifest = {
        "generated_at_epoch": time.time(),
        "dataset_root": str(dataset_root),
        "results_root": str(results_root),
        "rag_docs_dir": str(rag_docs_dir),
        "runs_per_case": args.runs,
        "baseline_subset_size_target": args.baseline_subset_size,
        "baseline_subset_size_actual": len(baseline_cases),
        "baseline_subset_case_ids": [c.case_id for c in baseline_cases],
        "configs": [cfg.to_dict() for cfg in configs],
    }
    write_json(results_root / "manifest.json", manifest)

    metrics_rows: list[dict[str, Any]] = []

    for cfg in configs:
        selected_cases = baseline_cases if cfg.baseline_subset_only else cases
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
                final_puml = ""
                final_validation: ValidationResult | None = None

                try:
                    final_puml, final_validation, prompt_text, requirement_used, processing_steps = (
                        run_single_generation(
                            case=case,
                            cfg=cfg,
                            all_cases=cases,
                            rag_docs=rag_docs,
                            requirement_source=args.requirement_source,
                            top_k_rag=args.top_k_rag,
                            ollama_host=args.ollama_host,
                            temperature=args.temperature,
                            top_p=args.top_p,
                            max_tokens=args.max_tokens,
                            timeout=args.timeout,
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

                metrics = compute_metrics(
                    pred_graph=final_graph,
                    pred_validation=final_validation,
                    gold_graph=case.gold_graph,
                )
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
                    "processing_steps": processing_steps,
                    "metrics": metrics,
                }
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
    dataset_root = Path(args.dataset_root)
    if not dataset_root.is_absolute():
        dataset_root = (PROJECT_ROOT / dataset_root).resolve()
    results_root = Path(args.results_root)
    if not results_root.is_absolute():
        results_root = (PROJECT_ROOT / results_root).resolve()

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
    results_root = Path(args.results_root)
    if not results_root.is_absolute():
        results_root = (PROJECT_ROOT / results_root).resolve()

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

    if args.run_id:
        rows = [row for row in rows if str(row.get("run_id", "")) in set(args.run_id)]

    if args.source == "summary":
        default_columns = [
            "run_id",
            "samples",
            "overall_f1_mean",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="All-in-one PlantUML validator/parser + metrics + 11-config batch runner"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate and parse a PlantUML file")
    p_validate.add_argument("--puml", required=True, help="Path to .puml file")
    p_validate.add_argument("--json", action="store_true", help="Print JSON output")
    p_validate.set_defaults(func=command_validate)

    p_run = sub.add_parser("run", help="Run full 11-configuration experiment batch")
    p_run.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_run.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Output root for run artifacts and metrics",
    )
    p_run.add_argument(
        "--rag-docs-dir",
        default=str(DEFAULT_RAG_DOCS_DIR),
        help="RAG documents directory",
    )
    p_run.add_argument("--runs", type=int, default=3, help="Runs per case/config")
    p_run.add_argument(
        "--baseline-subset-size",
        type=int,
        default=30,
        help="Target balanced subset size for GPT-4o baseline",
    )
    p_run.add_argument(
        "--requirement-source",
        choices=["raw", "structured"],
        default="structured",
        help="Requirement text source used in prompts",
    )
    p_run.add_argument("--top-k-rag", type=int, default=3, help="Top-k RAG docs")
    p_run.add_argument("--seed", type=int, default=42, help="Random seed")
    p_run.add_argument("--temperature", type=float, default=0.2)
    p_run.add_argument("--top-p", type=float, default=0.9)
    p_run.add_argument("--max-tokens", type=int, default=1024)
    p_run.add_argument("--timeout", type=int, default=300, help="Model call timeout (seconds)")
    p_run.add_argument(
        "--ollama-host",
        default="http://127.0.0.1:11434",
        help="Ollama host for open-source model calls",
    )
    p_run.add_argument("--gpt-model", default="gpt-4o", help="GPT baseline model id")
    p_run.add_argument("--qwen-model", default="qwen2.5:7b-instruct", help="Qwen model id")
    p_run.add_argument("--llama-model", default="llama3.1:8b-instruct", help="Llama model id")
    p_run.add_argument(
        "--skip-gpt-baseline",
        action="store_true",
        help="Skip proprietary GPT-4o baseline and run open-source configs only",
    )
    p_run.add_argument(
        "--only-run-id",
        action="append",
        help="Run only selected run_id (repeatable)",
    )
    p_run.add_argument("--skip-existing", action="store_true", help="Skip existing run files")
    p_run.add_argument("--save-prompts", action="store_true", help="Store prompts in .meta.json")
    p_run.set_defaults(func=command_run)

    p_metrics = sub.add_parser(
        "metrics", help="Recompute metrics from generated run files under results"
    )
    p_metrics.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_metrics.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Results root containing runs/",
    )
    p_metrics.set_defaults(func=command_metrics)

    p_table = sub.add_parser("table", help="Show metrics as a terminal table")
    p_table.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Results root containing metrics/",
    )
    p_table.add_argument(
        "--source",
        choices=["summary", "complexity", "per-run"],
        default="summary",
        help="Which metrics source to render as a table",
    )
    p_table.add_argument(
        "--columns",
        default="",
        help="Comma-separated columns to display (default depends on source)",
    )
    p_table.add_argument(
        "--sort-by",
        default="",
        help="Column to sort by (default depends on source)",
    )
    p_table.add_argument(
        "--asc",
        action="store_true",
        help="Sort ascending (default is descending)",
    )
    p_table.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit rows (0 = all rows)",
    )
    p_table.add_argument(
        "--run-id",
        action="append",
        help="Filter by run_id (repeatable)",
    )
    p_table.set_defaults(func=command_table)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
