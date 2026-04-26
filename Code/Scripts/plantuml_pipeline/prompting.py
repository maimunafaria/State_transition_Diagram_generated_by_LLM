from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any

from .constants import WORD_RE
from .io_utils import read_text
from .models import Case, ExperimentConfig, ValidationResult

DOMAIN_TOKEN_HINTS = {
    "accounts",
    "admin",
    "inventory",
    "logistic",
    "logistics",
    "order",
    "payment",
    "authentication",
    "employee",
    "employees",
    "customer",
    "customers",
    "healthcare",
    "covid",
    "textile",
    "marketplace",
    "device",
    "recommendation",
}


def tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in WORD_RE.finditer(text)}


def _filename_tokens(name: str) -> set[str]:
    stem = Path(name).stem
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", stem)
    return tokenize(normalized)


def _extract_domain_from_name(name: str) -> set[str]:
    stem = Path(name).stem.lower()
    domains: set[str] = set()
    match = re.match(r"domain_(.+?)_rules$", stem)
    if match:
        core = match.group(1).strip()
        if core:
            domains.add(core)
    return domains


def _rag_doc_source_type(name: str, content: str) -> str:
    normalized_name = name.replace("\\", "/")
    if normalized_name.startswith("dataset_examples/"):
        return "dataset_example"
    if normalized_name.startswith("plantuml_rules/"):
        return "plantuml_rule"
    if normalized_name.startswith("state_diagram_theory/"):
        return "state_diagram_theory"

    match = re.search(r"^source_type:\s*([A-Za-z0-9_\-/]+)\s*$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "reference"


def infer_query_domains(query: str, explicit_hints: set[str] | None = None) -> set[str]:
    domains = {tok for tok in tokenize(query) if tok in DOMAIN_TOKEN_HINTS}
    if explicit_hints:
        for hint in explicit_hints:
            clean = hint.strip().lower()
            if clean:
                domains.add(clean)
    return domains


def load_rag_docs(rag_docs_dir: Path) -> list[tuple[str, str, set[str]]]:
    if not rag_docs_dir.exists():
        return []
    docs: list[tuple[str, str, set[str]]] = []
    for path in sorted(rag_docs_dir.rglob("*.md")):
        if not path.is_file():
            continue
        if path.name.lower().endswith(("_manifest.md", "manifest.md")):
            continue
        content = read_text(path)
        name = str(path.relative_to(rag_docs_dir))
        docs.append((name, content, tokenize(content)))
    return docs


def retrieve_rag_context(
    query: str,
    docs: list[tuple[str, str, set[str]]],
    top_k: int,
    max_chars_per_doc: int = 1200,
    query_domain_hints: set[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if top_k <= 0 or not docs:
        return "", []

    query_tokens = tokenize(query)
    query_domains = infer_query_domains(query, explicit_hints=query_domain_hints)

    scored: list[dict[str, Any]] = []
    for name, content, tokens in docs:
        name_tokens = _filename_tokens(name)
        doc_domains = set(_extract_domain_from_name(name))
        doc_domains.update(tok for tok in tokens if tok in DOMAIN_TOKEN_HINTS)
        lexical_overlap = len(query_tokens & tokens)
        title_overlap = len(query_tokens & name_tokens)
        domain_overlap = len(query_domains & doc_domains)

        score = lexical_overlap + (2 * title_overlap) + (3 * domain_overlap)
        scored.append(
            {
                "name": name,
                "content": content,
                "token_count": len(tokens),
                "score": score,
                "lexical_overlap": lexical_overlap,
                "title_overlap": title_overlap,
                "domain_overlap": domain_overlap,
                "doc_domains": sorted(doc_domains),
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["domain_overlap"],
            item["title_overlap"],
            item["lexical_overlap"],
            item["token_count"],
        ),
        reverse=True,
    )

    for item in scored:
        item["source_type"] = _rag_doc_source_type(item["name"], item["content"])

    source_types = {item["source_type"] for item in scored}
    if {"dataset_example", "plantuml_rule", "state_diagram_theory"} & source_types:
        chosen: list[dict[str, Any]] = []
        category_limits = [
            ("plantuml_rule", 2),
            ("state_diagram_theory", 2),
            ("dataset_example", top_k),
        ]
        seen: set[str] = set()
        for source_type, limit in category_limits:
            category_items = [item for item in scored if item["source_type"] == source_type]
            positive_items = [item for item in category_items if item["score"] > 0]
            for item in (positive_items or category_items)[:limit]:
                if item["name"] not in seen:
                    chosen.append(item)
                    seen.add(item["name"])
        if not chosen:
            chosen = scored[:top_k]
    else:
        chosen = [item for item in scored if item["score"] > 0][:top_k]
        if not chosen:
            chosen = scored[:top_k]

    sections: list[str] = []
    trace: list[dict[str, Any]] = []
    for item in chosen:
        clipped = item["content"][:max_chars_per_doc].strip()
        source_type = item.get("source_type") or _rag_doc_source_type(item["name"], item["content"])
        sections.append(f"[{source_type}: {item['name']}]\n{clipped}")
        trace.append(
            {
                "name": item["name"],
                "source_type": source_type,
                "score": item["score"],
                "lexical_overlap": item["lexical_overlap"],
                "title_overlap": item["title_overlap"],
                "domain_overlap": item["domain_overlap"],
                "doc_domains": item["doc_domains"],
                "clipped_chars": len(clipped),
            }
        )

    return "\n\n".join(sections), trace


def retrieve_vector_rag_context(
    query: str,
    top_k: int,
    max_chars_per_doc: int,
    rag_db_dir: Path,
    rag_collection_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    if top_k <= 0:
        return "", []
    if not rag_db_dir.exists():
        raise FileNotFoundError(
            f"RAG vector database not found: {rag_db_dir}. Build it with Code/Scripts/build_rag_index.py"
        )

    try:
        import chromadb  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "chromadb is not installed. Install it before using --rag-mode vector."
        ) from exc

    try:
        client = chromadb.PersistentClient(path=str(rag_db_dir))
    except AttributeError as exc:
        raise RuntimeError(
            "This project expects a Chroma version with PersistentClient support."
        ) from exc

    try:
        collection = client.get_collection(rag_collection_name)
    except AttributeError:
        collection = client.get_or_create_collection(rag_collection_name)
    except Exception as exc:  # noqa: BLE001 - backend compatibility varies
        raise RuntimeError(
            f"Chroma collection '{rag_collection_name}' is not available in {rag_db_dir}"
        ) from exc

    def query_collection(
        n_results: int,
        source_type: str | None = None,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if source_type:
            kwargs["where"] = {"source_type": source_type}
        try:
            result = collection.query(**kwargs)
        except Exception:
            if source_type:
                return []
            raise

        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        rows: list[dict[str, Any]] = []
        for idx, doc_text in enumerate(docs):
            if not doc_text:
                continue
            doc_id = str(ids[idx]) if idx < len(ids) else f"doc_{idx + 1}"
            metadata = metadatas[idx] if idx < len(metadatas) and metadatas[idx] else {}
            distance = float(distances[idx]) if idx < len(distances) else None
            rows.append(
                {
                    "name": doc_id,
                    "content": str(doc_text),
                    "source_type": str(
                        metadata.get("source_type")
                        or _rag_doc_source_type(doc_id, str(doc_text))
                    ),
                    "vector_distance": distance,
                }
            )
        return rows

    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_type, limit in [
        ("plantuml_rule", 2),
        ("state_diagram_theory", 2),
        ("dataset_example", top_k),
    ]:
        for item in query_collection(limit, source_type=source_type):
            if item["name"] not in seen:
                chosen.append(item)
                seen.add(item["name"])

    if not chosen:
        chosen = query_collection(top_k)

    sections: list[str] = []
    trace: list[dict[str, Any]] = []
    for item in chosen:
        clipped = item["content"][:max_chars_per_doc].strip()
        sections.append(f"[{item['source_type']}: {item['name']}]\n{clipped}")
        trace.append(
            {
                "name": item["name"],
                "source_type": item["source_type"],
                "vector_distance": item["vector_distance"],
                "clipped_chars": len(clipped),
            }
        )

    return "\n\n".join(sections), trace


def resolve_rag_context(
    query: str,
    docs: list[tuple[str, str, set[str]]],
    top_k: int,
    max_chars_per_doc: int = 1200,
    query_domain_hints: set[str] | None = None,
    rag_mode: str = "lexical",
    rag_db_dir: Path | None = None,
    rag_collection_name: str = "uml_docs",
) -> tuple[str, list[dict[str, Any]]]:
    mode = rag_mode.strip().lower()
    if mode == "vector":
        if rag_db_dir is None:
            raise ValueError("rag_db_dir is required when rag_mode='vector'")
        return retrieve_vector_rag_context(
            query=query,
            top_k=top_k,
            max_chars_per_doc=max_chars_per_doc,
            rag_db_dir=rag_db_dir,
            rag_collection_name=rag_collection_name,
        )
    return retrieve_rag_context(
        query=query,
        docs=docs,
        top_k=top_k,
        max_chars_per_doc=max_chars_per_doc,
        query_domain_hints=query_domain_hints,
    )


def select_fewshot_examples(
    cases: list[Case],
    current_case_id: str,
    max_examples: int = 3,
    rng: random.Random | None = None,
) -> list[Case]:
    rng = rng or random.Random(0)
    by_complexity: dict[str, list[Case]] = {"simple": [], "medium": [], "complex": []}
    for case in cases:
        if case.case_id == current_case_id:
            continue
        by_complexity.setdefault(case.complexity, []).append(case)

    selected: list[Case] = []
    for bucket in ("simple", "medium", "complex"):
        bucket_cases = by_complexity.get(bucket, [])
        if bucket_cases:
            selected.append(rng.choice(bucket_cases))
            if len(selected) >= max_examples:
                return selected

    if len(selected) < max_examples:
        remainder = [c for c in cases if c.case_id != current_case_id and c not in selected]
        rng.shuffle(remainder)
        for case in remainder:
            selected.append(case)
            if len(selected) >= max_examples:
                break
    return selected


def build_zero_shot_prompt(requirement: str) -> str:
    return (
        "Act as a software requirements analyst and UML modeling expert.\n\n"
        "Your task is to generate a UML state transition diagram in PlantUML format "
        "from the given natural language requirement.\n\n"
        "Follow these steps before producing the final output:\n\n"
        "1. Identify all possible system states mentioned or implied in the requirement.\n"
        "2. Identify events or conditions that trigger transitions between states.\n"
        "3. Define transitions clearly using appropriate labels.\n"
        "4. Ensure logical consistency (no unreachable or isolated states).\n"
        "5. Identify exactly one initial state and at least one final state.\n\n"
        "Output Rules:\n"
        "- Generate ONLY valid PlantUML code.\n"
        "- Include initial and final states.\n"
        "- Use clear transition labels.\n"
        "- Maintain correct UML state diagram syntax.\n"
        "- Do not include explanations or extra text.\n\n"
        "Requirement:\n"
        f"{requirement}\n"
    )


def build_generation_prompt(
    case: Case,
    cfg: ExperimentConfig,
    all_cases: list[Case],
    rag_docs: list[tuple[str, str, set[str]]],
    requirement_source: str,
    top_k_rag: int,
    rag_max_chars_per_doc: int = 1200,
    rag_domain_hints: set[str] | None = None,
    rag_mode: str = "lexical",
    rag_db_dir: Path | None = None,
    rag_collection_name: str = "uml_docs",
    few_shot_seed: int = 42,
    run_index: int = 1,
) -> tuple[str, dict[str, Any]]:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    prompt_meta: dict[str, Any] = {
        "requirement_source": requirement_source,
        "few_shot_case_ids": [],
        "rag": {
            "enabled": bool(cfg.use_rag),
            "mode": rag_mode,
            "top_k": top_k_rag,
            "max_chars_per_doc": rag_max_chars_per_doc,
            "query_domains": sorted(
                infer_query_domains(requirement, explicit_hints=rag_domain_hints)
            ),
            "retrieved_docs": [],
        },
    }

    if cfg.strategy == "zero_shot":
        return build_zero_shot_prompt(requirement), prompt_meta

    if cfg.strategy == "few_shot":
        rng = random.Random(f"{few_shot_seed}:{cfg.run_id}:{case.case_id}:{run_index}")
        examples = select_fewshot_examples(all_cases, case.case_id, max_examples=3, rng=rng)
        prompt_meta["few_shot_case_ids"] = [ex.case_id for ex in examples]
        prompt_meta["few_shot_seed"] = few_shot_seed
        prompt_meta["few_shot_run_index"] = run_index
        example_texts: list[str] = []
        if examples:
            for idx, ex in enumerate(examples, start=1):
                ex_req = ex.structured_requirement.strip() or ex.raw_requirement.strip()
                ex_puml = ex.gold_puml.strip()
                example_texts.append(
                    f"Example {idx} Requirement:\n{ex_req}\n\nExample {idx} PlantUML:\n{ex_puml}"
                )
        few_shot_examples = "\n\n".join(example_texts) if example_texts else "[No examples available]"
        parts = [
            "Act as a software requirements analyst and UML modeling expert.",
            "",
            "Your task is to generate a UML state transition diagram in PlantUML format "
            "from the given natural language requirement.",
            "",
            "Follow the structure demonstrated in the examples below.",
            "",
            "--- Examples ---",
            few_shot_examples,
            "",
            "--- Process ---",
            "1. Identify all system states.",
            "2. Identify events/conditions triggering transitions.",
            "3. Define transitions clearly between states.",
            "4. Ensure logical consistency (no unreachable states).",
            "5. Identify one initial state and at least one final state.",
            "",
            "--- Output Rules ---",
            "- Generate ONLY valid PlantUML code.",
            "- Include initial and final states.",
            "- Use proper UML state diagram syntax.",
            "- Do not include explanations or extra text.",
            "",
            "--- Task ---",
            "Requirement:",
            requirement,
        ]
    else:
        parts = [
            "You convert natural language software requirements into UML state machine diagrams in PlantUML format.",
            "Rules:",
            "- Output ONLY PlantUML code.",
            "- Start with @startuml and end with @enduml.",
            "- Use [*] for exactly one initial transition.",
            "- Use --> for transitions.",
            "- Include transition labels when requirement evidence exists.",
            "- Do not add explanations or markdown fences.",
        ]

    if cfg.use_rag:
        rag_context, rag_trace = resolve_rag_context(
            query=requirement,
            docs=rag_docs,
            top_k=top_k_rag,
            max_chars_per_doc=rag_max_chars_per_doc,
            query_domain_hints=rag_domain_hints,
            rag_mode=rag_mode,
            rag_db_dir=rag_db_dir,
            rag_collection_name=rag_collection_name,
        )
        prompt_meta["rag"]["retrieved_docs"] = rag_trace
        if rag_context:
            parts.append("Reference context (support only, not mandatory):")
            parts.append(rag_context)

    if cfg.strategy != "few_shot":
        parts.append("Target requirement:")
        parts.append(requirement)
        parts.append("Now return only the final PlantUML.")
    return "\n\n".join(parts).strip() + "\n", prompt_meta


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
