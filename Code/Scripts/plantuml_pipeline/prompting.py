from __future__ import annotations

from pathlib import Path

from .constants import WORD_RE
from .io_utils import read_text
from .models import Case, ExperimentConfig, ValidationResult


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
