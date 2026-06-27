from __future__ import annotations

import random
import json
import re
from pathlib import Path
from typing import Any

from .constants import WORD_RE
from .io_utils import read_text
from .models import Case, ExperimentConfig, ValidationResult
from .parser import parse_plantuml
from .repair_patterns import (
    format_all_structural_validation_patterns,
    format_hybrid_issue_repair_blocks,
    format_syntax_patterns,
)

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


def _strip_frontmatter(content: str) -> str:
    text = content.strip()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text


def _extract_section(content: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    lines = content.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(pattern, line.strip(), re.IGNORECASE):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _extract_plantuml_code(content: str) -> str:
    match = re.search(r"```plantuml\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    start = content.find("@startuml")
    end = content.rfind("@enduml")
    if start != -1 and end != -1 and end >= start:
        return content[start : end + len("@enduml")].strip()
    return ""


def _bucket_count(value: int, low: int, high: int) -> str:
    if value <= low:
        return "low"
    if value <= high:
        return "medium"
    return "high"


def _behavior_profile_from_text(text: str) -> dict[str, Any]:
    tokens = tokenize(text)
    lower = text.lower()
    branching_terms = {
        "if",
        "else",
        "invalid",
        "valid",
        "fail",
        "failure",
        "success",
        "cancel",
        "reject",
        "approve",
        "retry",
        "timeout",
        "error",
        "choice",
    }
    terminal_terms = {
        "complete",
        "completed",
        "finish",
        "finished",
        "end",
        "logout",
        "close",
        "cancel",
        "submit",
        "approved",
        "rejected",
    }
    lifecycle_terms = {
        "create",
        "register",
        "login",
        "search",
        "view",
        "update",
        "delete",
        "pay",
        "payment",
        "order",
        "approve",
        "reject",
        "upload",
        "download",
    }
    action_count = len(tokens & lifecycle_terms)
    branch_count = len(tokens & branching_terms)
    terminal_count = len(tokens & terminal_terms)
    bullet_count = len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", text))
    sentence_count = len(re.findall(r"[.!?]\s+", text))
    complexity_seed = action_count + branch_count + max(bullet_count, sentence_count // 2)
    return {
        "domains": infer_query_domains(text),
        "branching": _bucket_count(branch_count, 1, 3),
        "terminal": _bucket_count(terminal_count, 1, 3),
        "complexity": _bucket_count(complexity_seed, 5, 12),
        "tokens": tokens,
    }


def _behavior_profile_from_doc(name: str, content: str, tokens: set[str]) -> dict[str, Any]:
    source_type = _rag_doc_source_type(name, content)
    puml = _extract_plantuml_code(content)
    profile_text = content
    transition_count = 0
    state_count = 0
    if puml:
        profile_text = puml
        transition_count = len(re.findall(r"-->|->", puml))
        state_names = set()
        for match in re.finditer(r"(?m)^\s*(?:state\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(?:-->|->|:|\\{|$)", puml):
            state_names.add(match.group(1))
        state_count = len(state_names)

    profile = _behavior_profile_from_text(profile_text)
    doc_domains = set(_extract_domain_from_name(name))
    doc_domains.update(tok for tok in tokens if tok in DOMAIN_TOKEN_HINTS)
    profile["domains"] = doc_domains
    if transition_count:
        profile["transition_count"] = transition_count
        profile["complexity"] = _bucket_count(state_count or transition_count, 6, 14)
    profile["source_type"] = source_type
    return profile


def _behavior_similarity(query_profile: dict[str, Any], doc_profile: dict[str, Any]) -> int:
    score = 0
    score += 4 * len(set(query_profile.get("domains", set())) & set(doc_profile.get("domains", set())))
    for key in ("complexity", "branching", "terminal"):
        if query_profile.get(key) == doc_profile.get(key):
            score += 2
    query_tokens = set(query_profile.get("tokens", set()))
    doc_tokens = set(doc_profile.get("tokens", set()))
    score += min(len(query_tokens & doc_tokens), 10)
    return score


def _count_guarded_transitions(puml: str) -> int:
    return len(re.findall(r"--?>\s+[^:]+:\s*\[[^\]]+\]", puml))


def _graph_features_from_puml(puml: str) -> dict[str, Any]:
    if not puml.strip():
        return {}
    graph = parse_plantuml(puml)
    loop_count = sum(1 for src, _, dst in graph.transitions if src == dst)
    choice_count = sum(
        1
        for stereotypes in graph.stereotypes.values()
        if any("choice" in stereo for stereo in stereotypes)
    )
    guarded_count = _count_guarded_transitions(puml)
    return {
        "state_count": len(graph.states),
        "transition_count": len(graph.transitions) + len(graph.final_states) + len(graph.initial_targets),
        "final_count": len(graph.final_states),
        "initial_count": len(graph.initial_targets),
        "loop_count": loop_count,
        "choice_count": choice_count,
        "guarded_count": guarded_count,
        "state_bucket": _bucket_count(len(graph.states), 6, 14),
        "transition_bucket": _bucket_count(
            len(graph.transitions) + len(graph.final_states) + len(graph.initial_targets),
            8,
            20,
        ),
        "branching_bucket": _bucket_count(choice_count + guarded_count, 1, 4),
        "loop_bucket": _bucket_count(loop_count, 0, 2),
    }


def _estimated_graph_features_from_requirement(requirement: str) -> dict[str, Any]:
    profile = _behavior_profile_from_text(requirement)
    tokens = set(profile.get("tokens", set()))
    action_terms = {
        "register",
        "login",
        "view",
        "search",
        "select",
        "upload",
        "download",
        "apply",
        "approve",
        "reject",
        "pay",
        "cancel",
        "submit",
        "verify",
        "validate",
        "process",
        "send",
        "receive",
        "update",
        "delete",
        "logout",
    }
    branch_terms = {
        "if",
        "valid",
        "invalid",
        "correct",
        "incorrect",
        "success",
        "failure",
        "approved",
        "rejected",
        "paid",
        "unpaid",
        "cancel",
        "retry",
        "multiple",
    }
    loop_terms = {"again", "continue", "multiple", "retry", "repeat", "another"}
    action_count = len(tokens & action_terms)
    branch_count = len(tokens & branch_terms)
    loop_count = len(tokens & loop_terms)
    estimated_states = max(3, action_count + branch_count + 2)
    estimated_transitions = max(estimated_states + 1, action_count + (2 * branch_count) + loop_count + 2)
    return {
        "state_count": estimated_states,
        "transition_count": estimated_transitions,
        "final_count": 1,
        "initial_count": 1,
        "loop_count": loop_count,
        "choice_count": branch_count,
        "guarded_count": branch_count,
        "state_bucket": _bucket_count(estimated_states, 6, 14),
        "transition_bucket": _bucket_count(estimated_transitions, 8, 20),
        "branching_bucket": _bucket_count(branch_count, 1, 4),
        "loop_bucket": _bucket_count(loop_count, 0, 2),
    }


def _graph_similarity_score(query_features: dict[str, Any], doc_features: dict[str, Any]) -> int:
    if not doc_features:
        return 0
    score = 0
    for key in ("state_bucket", "transition_bucket", "branching_bucket", "loop_bucket"):
        if query_features.get(key) == doc_features.get(key):
            score += 4
    for key in ("state_count", "transition_count", "loop_count", "choice_count", "guarded_count"):
        q_value = int(query_features.get(key, 0) or 0)
        d_value = int(doc_features.get(key, 0) or 0)
        distance = abs(q_value - d_value)
        score += max(0, 5 - min(distance, 5))
    if int(doc_features.get("initial_count", 0) or 0) == 1:
        score += 2
    if int(doc_features.get("final_count", 0) or 0) >= 1:
        score += 2
    return score


def _clip_at_line(text: str, max_chars: int) -> str:
    clean = text.strip()
    if len(clean) <= max_chars:
        return clean
    clipped = clean[:max_chars].rsplit("\n", 1)[0].strip()
    return clipped or clean[:max_chars].strip()


def _format_rag_doc_for_prompt(name: str, content: str, max_chars: int) -> str:
    source_type = _rag_doc_source_type(name, content)
    body = _strip_frontmatter(content)

    if source_type == "dataset_example":
        requirement = _extract_section(body, "Requirement")
        puml = _extract_plantuml_code(body)
        requirement = _clip_at_line(requirement, min(650, max_chars // 3))
        puml_label = "Reference PlantUML"
        if len(puml) > 5000:
            puml = _clip_at_line(puml, 5000)
            puml_label = "Reference PlantUML excerpt"
        return (
            f"Example requirement:\n{requirement}\n\n"
            f"{puml_label}:\n"
            "```plantuml\n"
            f"{puml}\n"
            "```"
        ).strip()

    if source_type == "plantuml_rule":
        return _clip_at_line(body, min(max_chars, 800))

    if source_type == "state_diagram_theory":
        return _clip_at_line(body, min(max_chars, 800))

    return _clip_at_line(body, max_chars)


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
    rag_profile: str = "standard",
) -> tuple[str, list[dict[str, Any]]]:
    if top_k <= 0 or not docs:
        return "", []

    query_tokens = tokenize(query)
    query_domains = infer_query_domains(query, explicit_hints=query_domain_hints)

    behavior_profile = _behavior_profile_from_text(query)
    if query_domain_hints:
        behavior_profile["domains"] = set(behavior_profile.get("domains", set())) | set(query_domains)

    scored: list[dict[str, Any]] = []
    for name, content, tokens in docs:
        name_tokens = _filename_tokens(name)
        doc_domains = set(_extract_domain_from_name(name))
        doc_domains.update(tok for tok in tokens if tok in DOMAIN_TOKEN_HINTS)
        lexical_overlap = len(query_tokens & tokens)
        title_overlap = len(query_tokens & name_tokens)
        domain_overlap = len(query_domains & doc_domains)

        source_type = _rag_doc_source_type(name, content)
        doc_behavior_profile = _behavior_profile_from_doc(name, content, tokens)
        behavior_score = _behavior_similarity(behavior_profile, doc_behavior_profile)
        score = lexical_overlap + (2 * title_overlap) + (3 * domain_overlap)
        scored.append(
            {
                "name": name,
                "content": content,
                "token_count": len(tokens),
                "source_type": source_type,
                "score": score,
                "behavior_score": behavior_score,
                "lexical_overlap": lexical_overlap,
                "title_overlap": title_overlap,
                "domain_overlap": domain_overlap,
                "doc_domains": sorted(doc_domains),
                "behavior_profile": {
                    key: value
                    for key, value in doc_behavior_profile.items()
                    if key not in {"tokens"}
                },
            }
        )

    profile = rag_profile.strip().lower()
    if profile == "behavior_aware":
        for item in scored:
            source_bonus = 0
            if item["source_type"] == "plantuml_rule":
                source_bonus = 8
            elif item["source_type"] == "dataset_example":
                source_bonus = 4
            elif item["source_type"] == "state_diagram_theory":
                source_bonus = -6
            item["score"] = item["score"] + item["behavior_score"] + source_bonus

    scored.sort(
        key=lambda item: (
            item["score"],
            item["behavior_score"],
            item["domain_overlap"],
            item["title_overlap"],
            item["lexical_overlap"],
            item["token_count"],
        ),
        reverse=True,
    )

    source_types = {item["source_type"] for item in scored}
    if profile == "behavior_aware" and {"dataset_example", "plantuml_rule"} & source_types:
        chosen = []
        seen = set()
        for source_type, limit in [
            ("plantuml_rule", 2),
            ("dataset_example", top_k),
        ]:
            category_items = [item for item in scored if item["source_type"] == source_type]
            positive_items = [item for item in category_items if item["score"] > 0]
            for item in (positive_items or category_items)[:limit]:
                if item["name"] not in seen:
                    chosen.append(item)
                    seen.add(item["name"])
        if not chosen:
            chosen = scored[:top_k]
    elif {"dataset_example", "plantuml_rule", "state_diagram_theory"} & source_types:
        chosen: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source_type, limit in [
            ("plantuml_rule", 2),
            ("state_diagram_theory", 2),
            ("dataset_example", top_k),
        ]:
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
        source_type = item.get("source_type") or _rag_doc_source_type(item["name"], item["content"])
        clipped = _format_rag_doc_for_prompt(
            item["name"],
            item["content"],
            max_chars_per_doc,
        )
        sections.append(clipped)
        trace.append(
            {
                "name": item["name"],
                "source_type": source_type,
                "score": item["score"],
                "behavior_score": item.get("behavior_score", 0),
                "lexical_overlap": item["lexical_overlap"],
                "title_overlap": item["title_overlap"],
                "domain_overlap": item["domain_overlap"],
                "doc_domains": item["doc_domains"],
                "behavior_profile": item.get("behavior_profile", {}),
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
        clipped = _format_rag_doc_for_prompt(
            item["name"],
            item["content"],
            max_chars_per_doc,
        )
        sections.append(clipped)
        trace.append(
            {
                "name": item["name"],
                "source_type": item["source_type"],
                "vector_distance": item["vector_distance"],
                "clipped_chars": len(clipped),
            }
        )

    return "\n\n".join(sections), trace


def retrieve_graph_rag_context(
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
    query_graph_features = _estimated_graph_features_from_requirement(query)

    scored: list[dict[str, Any]] = []
    for name, content, tokens in docs:
        source_type = _rag_doc_source_type(name, content)
        name_tokens = _filename_tokens(name)
        doc_domains = set(_extract_domain_from_name(name))
        doc_domains.update(tok for tok in tokens if tok in DOMAIN_TOKEN_HINTS)
        lexical_overlap = len(query_tokens & tokens)
        title_overlap = len(query_tokens & name_tokens)
        domain_overlap = len(query_domains & doc_domains)
        puml = _extract_plantuml_code(content)
        graph_features = _graph_features_from_puml(puml) if source_type == "dataset_example" else {}
        graph_score = _graph_similarity_score(query_graph_features, graph_features)
        source_bonus = 8 if source_type == "plantuml_rule" else 4 if source_type == "dataset_example" else -4
        score = graph_score + lexical_overlap + (2 * title_overlap) + (3 * domain_overlap) + source_bonus
        scored.append(
            {
                "name": name,
                "content": content,
                "source_type": source_type,
                "score": score,
                "graph_score": graph_score,
                "lexical_overlap": lexical_overlap,
                "title_overlap": title_overlap,
                "domain_overlap": domain_overlap,
                "doc_domains": sorted(doc_domains),
                "graph_features": graph_features,
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["graph_score"],
            item["domain_overlap"],
            item["title_overlap"],
            item["lexical_overlap"],
        ),
        reverse=True,
    )

    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_type, limit in [
        ("plantuml_rule", 2),
        ("dataset_example", top_k),
    ]:
        category_items = [item for item in scored if item["source_type"] == source_type]
        positive_items = [item for item in category_items if item["score"] > 0]
        for item in (positive_items or category_items)[:limit]:
            if item["name"] not in seen:
                chosen.append(item)
                seen.add(item["name"])
    if not chosen:
        chosen = scored[:top_k]

    sections: list[str] = []
    trace: list[dict[str, Any]] = []
    for item in chosen:
        clipped = _format_rag_doc_for_prompt(
            item["name"],
            item["content"],
            max_chars_per_doc,
        )
        sections.append(clipped)
        trace.append(
            {
                "name": item["name"],
                "source_type": item["source_type"],
                "score": item["score"],
                "graph_score": item["graph_score"],
                "lexical_overlap": item["lexical_overlap"],
                "title_overlap": item["title_overlap"],
                "domain_overlap": item["domain_overlap"],
                "doc_domains": item["doc_domains"],
                "query_graph_features": query_graph_features,
                "doc_graph_features": item["graph_features"],
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
    rag_profile: str = "standard",
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
    if mode == "graph":
        return retrieve_graph_rag_context(
            query=query,
            docs=docs,
            top_k=top_k,
            max_chars_per_doc=max_chars_per_doc,
            query_domain_hints=query_domain_hints,
        )
    return retrieve_rag_context(
        query=query,
        docs=docs,
        top_k=top_k,
        max_chars_per_doc=max_chars_per_doc,
        query_domain_hints=query_domain_hints,
        rag_profile=rag_profile,
    )


def select_fewshot_examples(
    cases: list[Case],
    current_case_id: str,
    max_examples: int = 3,
    rng: random.Random | None = None,
) -> list[Case]:
    rng = rng or random.Random(0)
    if max_examples <= 0:
        return []

    available_cases = [case for case in cases if case.case_id != current_case_id]
    if not available_cases:
        return []

    if max_examples == 1:
        return [rng.choice(available_cases)]

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


def build_chain_of_thought_analysis_prompt(
    requirement: str,
    prompt_structure: str = "original",
) -> str:
    parts = [
        "You are a software requirements analyst preparing a UML state machine model.",
        "",
        "Analyze the requirement and extract only the modeling facts needed for a state "
        "transition diagram. Keep the analysis concise and evidence-based.",
        "",
    ]
    if prompt_structure.strip().lower() == "uml_elements":
        parts.extend(
            [
                "--- UML State Transition Diagram Elements ---",
                *[f"- {element}" for element in _uml_elements_for_generation_prompt()],
                "",
            ]
        )
    parts.extend(
        [
            "Return the analysis using exactly these headings:",
            "States:",
            "Initial state:",
            "Final states:",
            "Events or conditions:",
            "Transitions:",
            "Missing or ambiguous details:",
            "",
            "Do not write PlantUML in this step.",
            "",
            "Requirement:",
            requirement,
        ]
    )
    return "\n".join(parts).strip() + "\n"


def build_chain_of_thought_generation_prompt(
    requirement: str,
    analysis: str,
    prompt_structure: str = "original",
    example_requirement: str = "",
    example_puml: str = "",
) -> str:
    parts = [
        "You are a UML modeling expert.",
        "",
        "Convert the requirement and the structured analysis into one UML state transition "
        "diagram in PlantUML format.",
        "",
    ]
    prompt_structure = prompt_structure.strip().lower() or "original"
    if prompt_structure in {"uml_elements", "uml_elements_structural_validation"}:
        parts.extend(
            [
                "--- UML State Transition Diagram Elements ---",
                *[f"- {element}" for element in _uml_elements_for_generation_prompt()],
                "",
            ]
        )
    if prompt_structure in {"structural_validation", "uml_elements_structural_validation"}:
        parts.extend(
            [
                "--- Structural Validation Rules ---",
                *[f"- {rule}" for rule in _repair_rules_for_generation_prompt()],
                "",
            ]
        )
    if prompt_structure == "structural_validation_patterns":
        parts.extend(
            [
                format_all_structural_validation_patterns(),
                "",
            ]
        )
    if prompt_structure == "plantuml_example" and example_requirement.strip() and example_puml.strip():
        parts.extend(
            [
                "--- Example PlantUML Structure ---",
                "Use this training example only to understand PlantUML state diagram structure. "
                "Do not copy its domain states or transitions into the target answer.",
                "",
                "Example requirement:",
                example_requirement.strip(),
                "",
                "Example PlantUML:",
                example_puml.strip(),
                "",
                "--- Target Task ---",
            ]
        )
    parts.extend(
        [
            "Output Rules:",
            "- Generate ONLY valid PlantUML code.",
            "- Start with @startuml and end with @enduml.",
            "- Use [*] for exactly one initial transition.",
            "- Include at least one final transition to [*].",
            "- Use clear transition labels when requirement evidence exists.",
            "- Do not include explanations, analysis, or markdown fences.",
            "",
            "Requirement:",
            requirement,
            "",
            "Structured analysis from step 1:",
            analysis.strip(),
            "",
            "Now return only the final PlantUML.",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def _repair_rules_for_generation_prompt() -> list[str]:
    return [
        "Avoid invalid [*] --> [*] transitions: use a real terminal state before [*].",
        "Avoid multiple_initial_state_transitions: use exactly one clear top-level initial transition from [*] to the first lifecycle state.",
        "Avoid missing_initial_state_transition: always include one initial transition from [*] to the first lifecycle state.",
        "Avoid missing_final_state_transition: include at least one final transition from a natural terminal state to [*].",
        "Avoid orphan states: connect every supported state with reasonable incoming or outgoing transitions, or omit unsupported states.",
        "Avoid unreachable states: make sure every modeled state can be reached from the initial lifecycle path.",
        "Avoid duplicate transitions: remove duplicates or merge their labels into one transition.",
        "Avoid choice nodes without outgoing transitions: every choice node must have outgoing alternatives.",
        "Avoid choice nodes without guarded transitions: label choice-node outgoing transitions with guards such as [valid] and [invalid].",
        "Avoid fork nodes without multiple outgoing branches: use fork nodes only when splitting into multiple outgoing branches.",
        "Avoid join nodes without multiple incoming branches: use join nodes only when merging multiple incoming branches.",
        "Avoid history_state_used_without_composite_state: use [H] or [H*] only inside a composite state.",
        "If modeling nested behavior, do not add extra [*] transitions inside composite states; connect the parent state to its first child state instead.",
    ]


def _format_structural_validation_rules() -> str:
    return "\n".join(f"- {rule}" for rule in _repair_rules_for_generation_prompt())


def _uml_elements_for_generation_prompt() -> list[str]:
    return [
        "State transition diagram: models the lifecycle behavior of one reactive object, system, controller, process, class, subsystem, or use case as it changes state in response to events.",
        "Reactive object / context: the main object or system whose behavior is being modeled; it responds to events and has a lifecycle.",
        "State: a meaningful condition, mode, phase, or situation during the object's life that changes how it responds to events.",
        "Initial state: a pseudostate marking where the state machine begins; it points to the first real lifecycle state.",
        "Final state: marks completion or termination of the modeled lifecycle.",
        "Transition: a directed movement from one state to another caused by an event.",
        "Event / trigger: a noteworthy external or internal occurrence that may trigger a transition.",
        "Guard condition: a Boolean condition that must be true for a transition to occur.",
        "Action: instantaneous, uninterruptible behavior performed during a transition or inside a state.",
        "Activity / do behavior: behavior performed within a state that takes finite time and may be interrupted by an event.",
        "Entry behavior: an action performed immediately when a state is entered.",
        "Exit behavior: an action performed immediately before a state is exited.",
        "Internal transition: handles an event within the current state without moving to another state.",
        "Composite state: a state that contains one or more nested state machines and groups related substates.",
        "Substate: a state contained inside a composite state.",
        "Superstate: a parent state that contains substates and may define shared behavior.",
        "Sequential composite state: a composite state with one nested state machine where only one substate is active at a time.",
        "Concurrent composite state: a composite state with two or more nested state machines executing concurrently.",
        "Fork: a control point where execution splits into multiple concurrent paths.",
        "Join: a control point where multiple concurrent paths synchronize before continuing.",
        "History state: remembers the last active substate of a composite state so execution can resume there.",
        "Shallow history: remembers the last active substate only at the same nesting level.",
        "Deep history: remembers the last active substate across nested levels.",
        "Call event: a request to invoke an operation on the modeled object.",
        "Signal event: receipt of an asynchronous message.",
        "Change event: occurs when a Boolean condition becomes true.",
        "Time event: occurs at a specific time or after a specified interval.",
    ]


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
    rag_profile: str = "standard",
    few_shot_seed: int = 42,
    few_shot_count: int = 3,
    few_shot_prompt_structure: str = "original",
    run_index: int = 1,
) -> tuple[str, dict[str, Any]]:
    requirement = case.structured_requirement if requirement_source == "structured" else case.raw_requirement
    if not requirement.strip():
        requirement = case.raw_requirement or case.structured_requirement

    prompt_meta: dict[str, Any] = {
        "requirement_source": requirement_source,
        "few_shot_case_ids": [],
        "few_shot_prompt_structure": few_shot_prompt_structure,
        "rag": {
            "enabled": bool(cfg.use_rag),
            "mode": rag_mode,
            "profile": rag_profile,
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

    if cfg.strategy == "chain_of_thought":
        return build_chain_of_thought_generation_prompt(
            requirement,
            "",
            prompt_structure=few_shot_prompt_structure,
        ), prompt_meta

    if cfg.strategy == "few_shot":
        prompt_structure = few_shot_prompt_structure.strip().lower() or "original"
        selection_run_id = re.sub(r"__prompt_[a-z0-9_]+$", "", cfg.run_id)
        rng = random.Random(f"{few_shot_seed}:{selection_run_id}:{case.case_id}:{run_index}")
        examples = select_fewshot_examples(
            all_cases,
            case.case_id,
            max_examples=few_shot_count,
            rng=rng,
        )
        prompt_meta["few_shot_case_ids"] = [ex.case_id for ex in examples]
        prompt_meta["few_shot_seed"] = few_shot_seed
        prompt_meta["few_shot_count"] = few_shot_count
        prompt_meta["few_shot_selection_run_id"] = selection_run_id
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
        ]
        if prompt_structure in {"uml_elements", "uml_elements_structural_validation"}:
            parts.extend(
                [
                    "--- UML State Transition Diagram Elements ---",
                    *[f"- {element}" for element in _uml_elements_for_generation_prompt()],
                    "",
                ]
            )
        if prompt_structure in {"structural_validation", "uml_elements_structural_validation"}:
            parts.extend(
                [
                    "--- Structural Validation Rules ---",
                    *[f"- {rule}" for rule in _repair_rules_for_generation_prompt()],
                    "",
                ]
            )
        if prompt_structure == "structural_validation_patterns":
            parts.extend(
                [
                    format_all_structural_validation_patterns(),
                    "",
                ]
            )
        parts.extend(
            [
                "--- Task ---",
                "Requirement:",
                requirement,
            ]
        )
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

    target_requirement_added = False
    if cfg.use_rag:
        profile = rag_profile.strip().lower()
        rag_context, rag_trace = resolve_rag_context(
            query=requirement,
            docs=rag_docs,
            top_k=top_k_rag,
            max_chars_per_doc=rag_max_chars_per_doc,
            query_domain_hints=rag_domain_hints,
            rag_mode=rag_mode,
            rag_db_dir=rag_db_dir,
            rag_collection_name=rag_collection_name,
            rag_profile=rag_profile,
        )
        prompt_meta["rag"]["retrieved_docs"] = rag_trace
        if rag_context:
            if cfg.strategy != "few_shot":
                parts.append("Target requirement:")
                parts.append(requirement)
                target_requirement_added = True
            if profile == "behavior_aware":
                parts.extend(
                    [
                        "Retrieved validation checklist:",
                        "1. Include exactly one top-level initial transition: [*] --> State.",
                        "2. Include at least one final transition: State --> [*].",
                        "3. Every declared state must be reachable from the initial state.",
                        "4. Every transition source and target must exist.",
                        "5. Do not create multiple top-level initial transitions.",
                        "6. Do not add states or transitions not supported by the target requirement.",
                        "",
                        "Retrieved-context use policy:",
                        "- Use retrieved examples only for structural pattern guidance.",
                        "- Do not copy states, transitions, actors, or labels from examples unless directly supported by the target requirement.",
                        "- If a retrieved example contains behavior not mentioned in the target requirement, ignore that behavior.",
                        "",
                    ]
                )
            parts.append("Reference context (use as support; the target requirement above is primary):")
            parts.append(rag_context)

    if cfg.strategy != "few_shot" and not target_requirement_added:
        parts.append("Target requirement:")
        parts.append(requirement)
        parts.append("Now return only the final PlantUML.")
    elif cfg.strategy != "few_shot":
        parts.append("Now return only the final PlantUML.")
    return "\n\n".join(parts).strip() + "\n", prompt_meta


def _repair_guidance_for_issues(issues: list[str]) -> list[str]:
    guidance: list[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        if text not in seen:
            guidance.append(text)
            seen.add(text)

    for issue in issues:
        low = issue.lower()
        if "invalid [*]" in low:
            add(
                "For invalid [*] --> [*], replace it with a real final transition, "
                "for example Logout --> [*] : session ended."
            )
        if "multiple_initial_state_transitions" in low:
            add(
                "For multiple initial transitions, keep only the one top-level [*] --> State transition."
            )
            add(
                "If an extra [*] --> Child transition appears inside a composite state block, "
                "do not create a choice node. Replace only that line with Parent --> Child, "
                "where Parent is the enclosing state name. Example: inside state Login { [*] --> Checking } "
                "change it to Login --> Checking."
            )
            add(
                "Do not add new states to fix multiple initial transitions. Do not redesign the diagram. "
                "Usually this fix should only replace nested [*] arrows with normal arrows."
            )
        if "missing_initial_state_transition" in low:
            add("Add one clear initial transition from [*] to the first lifecycle state.")
        if "missing_final_state_transition" in low:
            add(
                "Add at least one final transition from a natural terminal state to [*], "
                "such as LoggedOut --> [*] or AccessEnded --> [*]."
            )
        if "orphan" in low:
            add(
                "For orphan states, either connect them with reasonable incoming/outgoing transitions "
                "based on the requirement, or remove them if they are unsupported."
            )
        if "unreachable" in low:
            add(
                "For unreachable states, add a path from the initial lifecycle to those states, "
                "usually through a decision/choice or a transition from the preceding activity."
            )
        if "duplicate_transitions" in low:
            add("Remove duplicate transitions or merge their labels into one transition.")
        if "choice_node_without_outgoing" in low:
            add("Give each choice node at least two outgoing alternatives when possible.")
        if "choice_node_without_guarded" in low:
            add("Label choice-node outgoing transitions with guard conditions like [valid] and [invalid].")
        if "fork_without_multiple_outgoing" in low:
            add("A fork node should split into multiple outgoing branches.")
        if "join_without_multiple_incoming" in low:
            add("A join node should merge multiple incoming branches.")
        if "history_state_used_without_composite_state" in low:
            add("Use [H] or [H*] only inside a composite state, or remove the history state.")
        if "plantuml_syntax_error" in low or "empty src/dst" in low:
            add("Fix PlantUML syntax first; return only valid PlantUML code with no markdown fences.")

    if not guidance:
        add("Fix each listed issue while preserving the requirement meaning.")
    return guidance


def _repair_issue_priority(issue: str) -> int:
    low = issue.lower()
    if "plantuml_syntax_error" in low or "empty src/dst" in low:
        return 1
    if "invalid [*]" in low:
        return 2
    if "missing_initial_state_transition" in low or "multiple_initial_state_transitions" in low:
        return 3
    if "missing_final_state_transition" in low:
        return 4
    if "duplicate_transitions" in low:
        return 6
    if "orphan" in low:
        return 7
    if "unreachable" in low:
        return 8
    if "choice_" in low or "fork_" in low or "join_" in low or "history_state" in low:
        return 9
    return 5


def _prioritized_repair_issues(validation: ValidationResult) -> list[str]:
    issues = list(validation.errors) + list(validation.warnings)
    return sorted(issues, key=lambda issue: (_repair_issue_priority(issue), issue))


def _normalize_repair_issue_name(issue: str) -> str:
    issue = issue.strip().lower()
    issue = re.sub(r"\s*\(.*?\)\s*$", "", issue)
    issue = issue.replace(" ", "_")
    if issue.startswith("orphan"):
        return "orphan_state"
    if issue.startswith("unreachable"):
        return "unreachable_state"
    if issue.startswith("duplicate"):
        return "duplicate_transitions_detected"
    if "missing_initial" in issue:
        return "missing_initial_state_transition"
    if "missing_final" in issue:
        return "missing_final_state_transition"
    if "multiple_initial" in issue:
        return "multiple_initial_state_transitions"
    if "[*]" in issue and "[*]" in issue.replace("[*]", "", 1):
        return "invalid_initial_to_final_transition"
    if "choice" in issue and "outgoing" in issue:
        return "choice_without_outgoing"
    if "choice" in issue and "guard" in issue:
        return "choice_without_guard"
    if "fork" in issue:
        return "fork_without_multiple_outgoing"
    if "join" in issue:
        return "join_without_multiple_incoming"
    if "history" in issue:
        return "history_state_used_without_composite_state"
    return issue


def _section_between(text: str, start_label: str, end_labels: list[str]) -> str:
    start = text.find(start_label)
    if start < 0:
        return ""
    start += len(start_label)
    end_positions = [text.find(label, start) for label in end_labels]
    end_positions = [pos for pos in end_positions if pos >= 0]
    end = min(end_positions) if end_positions else len(text)
    return text[start:end].strip()


def _load_repair_examples(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    examples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        metadata = row.get("metadata") or {}
        issue_names = [
            _normalize_repair_issue_name(str(issue))
            for issue in metadata.get("violation_types", [])
        ]
        if not issue_names:
            continue
        examples.append(
            {
                "issue_names": issue_names,
                "input": str(row.get("input", "")),
                "output": str(row.get("output", "")),
                "source_llm": metadata.get("source_llm", ""),
                "source_method": metadata.get("source_method", ""),
                "source_repair_variant": metadata.get("source_repair_variant", ""),
                "case_id": metadata.get("case_id", ""),
            }
        )
    return examples


def _select_repair_examples(
    repair_example_dataset: Path,
    issues: list[str],
    requirement: str,
    candidate_puml: str,
    examples_per_issue: int,
    exclude_case_id: str = "",
) -> list[dict[str, Any]]:
    examples = _load_repair_examples(repair_example_dataset)
    if not examples or examples_per_issue <= 0:
        return []

    query_tokens = tokenize(requirement + "\n" + candidate_puml)
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str]] = set()
    selected_issue_cases: set[tuple[str, str]] = set()

    for issue in issues:
        normalized_issue = _normalize_repair_issue_name(issue)
        candidates = [
            example
            for example in examples
            if normalized_issue in set(example["issue_names"])
            and str(example.get("case_id", "")) != exclude_case_id
        ]
        scored: list[tuple[int, str, dict[str, Any]]] = []
        for example in candidates:
            score = len(query_tokens & tokenize(example["input"]))
            scored.append((score, str(example.get("case_id", "")), example))
        scored.sort(key=lambda item: (-item[0], item[1]))
        taken = 0
        for _, _, example in scored:
            issue_case_key = (normalized_issue, str(example.get("case_id", "")))
            if issue_case_key in selected_issue_cases:
                continue
            key = (
                str(example.get("case_id", "")),
                str(example.get("source_llm", "")),
                str(example.get("output", ""))[:120],
            )
            if key in selected_keys:
                continue
            selected_keys.add(key)
            selected_issue_cases.add(issue_case_key)
            selected.append(example)
            taken += 1
            if taken >= examples_per_issue:
                break
    return selected


def _clip_section(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit("\n", 1)[0].strip() + "\n... [clipped]"


def _format_repair_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "[No matching historical repair examples were found.]"
    blocks: list[str] = []
    for index, example in enumerate(examples, start=1):
        source = ", ".join(
            part
            for part in [
                str(example.get("source_llm", "")),
                str(example.get("source_method", "")),
                str(example.get("source_repair_variant", "")),
                str(example.get("case_id", "")),
            ]
            if part
        )
        inp = example["input"]
        requirement = _section_between(inp, "Requirement:", ["Invalid PlantUML:"])
        invalid = _section_between(inp, "Invalid PlantUML:", ["Validation Errors:"])
        errors = _section_between(inp, "Validation Errors:", ["Relevant Rule:"])
        rule = _section_between(inp, "Relevant Rule:", [])
        repaired = str(example["output"]).strip()
        block = (
            f"Historical Repair Example {index}"
            + (f" ({source})" if source else "")
            + "\n"
            f"Violation type:\n{errors}\n\n"
            f"Example requirement summary:\n{_clip_section(requirement, 500)}\n\n"
            f"Example invalid PlantUML:\n{_clip_section(invalid, 900)}\n\n"
            f"Example repaired PlantUML:\n{_clip_section(repaired, 1400)}\n\n"
            f"Example rule:\n{_clip_section(rule, 350)}"
        ).strip()
        blocks.append(block)
    return "\n\n---\n\n".join(blocks)


def _format_compact_repair_examples(examples: list[dict[str, Any]]) -> str:
    if not examples:
        return "[No matching historical repair example was found.]"
    blocks: list[str] = []
    for index, example in enumerate(examples, start=1):
        inp = example["input"]
        invalid = _section_between(inp, "Invalid PlantUML:", ["Validation Errors:"])
        errors = _section_between(inp, "Validation Errors:", ["Relevant Rule:"])
        repaired = str(example["output"]).strip()
        blocks.append(
            (
                f"Historical repair example {index}\n"
                f"Violation:\n{errors}\n\n"
                f"Invalid PlantUML:\n{invalid.strip()}\n\n"
                f"Repaired PlantUML:\n{repaired.strip()}"
            ).strip()
        )
    return "\n\n---\n\n".join(blocks)


def _validation_issue_details(validation: ValidationResult) -> list[str]:
    details: list[str] = []
    if not validation.valid:
        details.append("PlantUML syntax is invalid. Repair syntax before changing structure.")
    if validation.initial_state:
        details.append(f"Current initial state: {validation.initial_state}")
    else:
        details.append("Current initial state: none or ambiguous")
    if validation.unreachable_states:
        details.append("Unreachable states: " + ", ".join(validation.unreachable_states))
    details.append(f"State count: {validation.state_count}")
    details.append(f"Transition count: {validation.transition_count}")
    if validation.duplicate_transition_count:
        details.append(f"Duplicate transition count: {validation.duplicate_transition_count}")
    return details


def _diagnostic_validation_issue_lines(
    candidate_puml: str,
    validation: ValidationResult,
) -> list[str]:
    graph = parse_plantuml(candidate_puml)
    issues = _prioritized_repair_issues(validation)
    lines: list[str] = []

    duplicate_counts: dict[tuple[str, str, str], int] = {}
    for transition in graph.transitions:
        duplicate_counts[transition] = duplicate_counts.get(transition, 0) + 1
    duplicate_details = [
        f"{src} --> {dst}" + (f" : {event}" if event else "")
        for (src, event, dst), count in sorted(duplicate_counts.items())
        if count > 1
    ]

    for issue in issues:
        low = issue.lower()
        detail = ""
        if "multiple_initial_state_transitions" in low:
            if graph.initial_targets:
                detail = "Problematic initial targets: " + ", ".join(graph.initial_targets)
        elif "missing_initial_state_transition" in low:
            detail = "No [*] --> first lifecycle state transition was detected."
        elif "missing_final_state_transition" in low:
            detail = "No terminal state --> [*] transition was detected."
        elif "duplicate_transitions" in low:
            if duplicate_details:
                detail = "Duplicate transitions: " + "; ".join(duplicate_details)
            else:
                detail = f"Duplicate transition count: {validation.duplicate_transition_count}"
        elif "unreachable" in low:
            if validation.unreachable_states:
                detail = "Unreachable states: " + ", ".join(validation.unreachable_states)
            elif issue.startswith("unreachable:"):
                detail = issue
        elif "orphan" in low:
            orphan_issues = [
                item
                for item in list(validation.errors) + list(validation.warnings)
                if item.startswith("orphan:")
            ]
            if orphan_issues:
                detail = "; ".join(orphan_issues)
        elif "choice_node_without_outgoing" in low or "choice_node_without_guarded" in low:
            detail = issue
        elif "invalid [*]" in low:
            detail = issue
        elif "plantuml_syntax_error" in low:
            detail = "Official PlantUML syntax check failed."

        lines.append(f"- {issue}" + (f" ({detail})" if detail else ""))

    return lines or ["- none"]


def build_targeted_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    repair_guidance = _repair_guidance_for_issues(validation_issues)
    issue_details = _validation_issue_details(validation)
    issue_count = len(validation_issues)
    if issue_count <= 2:
        severity_rule = "Use targeted repair: fix only the listed localized issue(s)."
    elif issue_count <= 5:
        severity_rule = "Use guided repair: fix issues in priority order while preserving all supported behavior."
    else:
        severity_rule = (
            "The diagram has many issues. Keep the existing diagram only as a draft and rebuild the smallest "
            "valid diagram supported by the requirement; do not copy unsupported draft behavior."
        )

    return (
        "You are a violation-specific UML repair assistant.\n"
        "Repair the candidate PlantUML in priority order.\n"
        "Do not redesign the diagram unless the issue count is severe.\n"
        "Prefer the smallest possible edit that fixes the current highest-priority issue.\n"
        "Preserve requirement-supported states and transitions.\n"
        "Do not delete states/transitions merely to pass validation unless they are unsupported by the requirement.\n"
        "Do not introduce states or transitions that are not supported by the requirement.\n"
        "Output ONLY corrected PlantUML. No markdown fences. No explanation.\n\n"
        "Repair strategy:\n"
        f"{severity_rule}\n\n"
        "Priority order:\n"
        "1. Syntax errors\n"
        "2. Parse warnings and invalid [*] transitions\n"
        "3. Missing or multiple initial states\n"
        "4. Missing final state\n"
        "5. Invalid transition source/target\n"
        "6. Duplicate transitions\n"
        "7. Orphan states\n"
        "8. Unreachable states\n"
        "9. Choice/fork/join/history errors\n\n"
        "Issue-specific details:\n"
        + "\n".join(f"- {detail}" for detail in issue_details)
        + "\n\nRequirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues to fix, already sorted by priority:\n"
        + ("\n".join(f"- {err}" for err in validation_issues) if validation_issues else "- none")
        + "\n\nRepair guidance for these issues:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
    )


def build_syntax_grounded_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    issue_details = _validation_issue_details(validation)
    syntax_patterns = format_syntax_patterns(validation_issues)
    structural_rules = _format_structural_validation_rules()
    return (
        "You are a PlantUML repair assistant.\n"
        "Repair the candidate using the valid PlantUML syntax patterns below.\n"
        "The uppercase identifiers in the patterns are placeholders, not literal state names.\n"
        "Replace placeholders only with existing or requirement-supported states, events, and guards.\n"
        "Apply only patterns that correspond to the listed validation issues.\n"
        "Keep unaffected states, transitions, labels, and behavior unchanged.\n"
        "Do not copy placeholder identifiers into the final diagram.\n"
        "Output ONLY one corrected PlantUML diagram. No markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
        + "\n\nValidator details:\n"
        + "\n".join(f"- {detail}" for detail in issue_details)
        + "\n\n--- Structural Validation Rules ---\n"
        + structural_rules
        + "\n\nValid PlantUML repair patterns:\n"
        + syntax_patterns
    )


def build_syntax_grounded_no_rules_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    issue_details = _validation_issue_details(validation)
    syntax_patterns = format_syntax_patterns(validation_issues)
    return (
        "You are a PlantUML repair assistant.\n"
        "Repair the candidate using the valid PlantUML syntax patterns below.\n"
        "The uppercase identifiers in the patterns are placeholders, not literal state names.\n"
        "Replace placeholders only with existing or requirement-supported states, events, and guards.\n"
        "Apply only patterns that correspond to the listed validation issues.\n"
        "Keep unaffected states, transitions, labels, and behavior unchanged.\n"
        "Do not copy placeholder identifiers into the final diagram.\n"
        "Output ONLY one corrected PlantUML diagram. No markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
        + "\n\nValidator details:\n"
        + "\n".join(f"- {detail}" for detail in issue_details)
        + "\n\nValid PlantUML repair patterns:\n"
        + syntax_patterns
    )


def build_diagnostic_syntax_grounded_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    diagnostic_issues = _diagnostic_validation_issue_lines(candidate_puml, validation)
    repair_guidance = _repair_guidance_for_issues(validation_issues)
    syntax_patterns = format_syntax_patterns(validation_issues)
    return (
        "General instruction:\n"
        "You are a PlantUML repair assistant. Repair only the listed validation issues. "
        "Preserve all unaffected states, transitions, labels, and requirement-supported behavior. "
        "Do not add unsupported behavior. Output only one corrected PlantUML diagram, "
        "with no markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + "\n".join(diagnostic_issues)
        + "\n\nRepair guidance for these issues:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + "\n\nValid PlantUML repair patterns:\n"
        + syntax_patterns
    )


def build_constrained_validator_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    diagnostic_issues = _diagnostic_validation_issue_lines(candidate_puml, validation)
    repair_guidance = _repair_guidance_for_issues(validation_issues)
    syntax_patterns = format_syntax_patterns(validation_issues)
    first_issue = validation_issues[0] if validation_issues else ""
    low = first_issue.lower()
    if "unreachable" in low:
        edit_rule = (
            "Fix only unreachable states. Prefer adding the minimum supported transitions needed "
            "to make the listed states reachable. Do not rename states. Do not delete states. "
            "Do not rewrite unrelated transitions."
        )
    elif "orphan" in low:
        edit_rule = (
            "Fix only orphan states. Connect requirement-supported orphan states with the minimum "
            "incoming/outgoing transitions. Remove an orphan only if it is unsupported by the requirement."
        )
    elif "missing_final_state_transition" in low:
        edit_rule = (
            "Fix only the missing final transition. Add one terminal-state --> [*] transition "
            "from an existing natural terminal state. Do not rewrite the diagram."
        )
    elif "missing_initial_state_transition" in low:
        edit_rule = (
            "Fix only the missing initial transition. Add exactly one [*] --> first-state transition "
            "using an existing first lifecycle state."
        )
    elif "multiple_initial_state_transitions" in low:
        edit_rule = (
            "Fix only multiple initial transitions. Keep one top-level [*] --> state transition. "
            "Replace extra [*] --> child transitions with ordinary supported transitions. "
            "Do not add new states."
        )
    elif "duplicate_transitions" in low:
        edit_rule = (
            "Fix only duplicate transitions. Remove exact duplicates or merge their labels into one transition. "
            "Do not change unrelated transitions."
        )
    elif "plantuml_syntax_error" in low:
        edit_rule = (
            "Fix only PlantUML syntax. Remove malformed fragments, complete incomplete declarations, "
            "and keep valid existing state/transition content. Do not redesign behavior."
        )
    else:
        edit_rule = "Fix only the listed validation issues with the smallest possible edit."

    return (
        "General instruction:\n"
        "You are a constrained PlantUML repair assistant. Make the smallest possible edit. "
        "Do not redesign the diagram. Do not add unsupported behavior. "
        "Return only one corrected PlantUML diagram, with no markdown fences or explanation.\n\n"
        "Current edit constraint:\n"
        f"{edit_rule}\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + "\n".join(diagnostic_issues)
        + "\n\nRepair guidance for these issues:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + "\n\nValid PlantUML repair patterns:\n"
        + syntax_patterns
    )


def build_compiler_guided_syntax_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    syntax_issues = [
        issue for issue in validation_issues if "plantuml_syntax_error" in issue.lower()
    ]
    if not syntax_issues:
        return build_syntax_grounded_repair_prompt(
            requirement,
            candidate_puml,
            validation,
            critic_feedback,
        )

    return (
        "You are a compiler-guided PlantUML syntax repair assistant.\n"
        "Fix only the official PlantUML compiler error shown below.\n"
        "Make the smallest possible syntax edit. Preserve all supported states, "
        "transitions, labels, and behavior. Do not redesign the diagram.\n"
        "Return only the complete corrected PlantUML code with no markdown fences "
        "and no explanation.\n\n"
        "Official compiler diagnostic:\n"
        + "\n".join(f"- {issue}" for issue in syntax_issues)
        + "\n\nCommon valid syntax patterns:\n"
        "state ChoiceNode <<choice>>\n"
        "state ForkNode <<fork>>\n"
        "state JoinNode <<join>>\n"
        'state \"Display Name\" as StateAlias\n'
        "[*] --> FirstState\n"
        "StateA --> StateB : event [guard]\n"
        "FinalState --> [*]\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n"
    )


def build_syntax_preserving_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    syntax_issues = [
        issue
        for issue in _prioritized_repair_issues(validation)
        if "plantuml_syntax_error" in issue.lower()
    ]
    diagnostic = (
        "\n".join(f"- {issue}" for issue in syntax_issues)
        if syntax_issues
        else "- No official compiler diagnostic was captured."
    )
    return (
        "You are a syntax-preserving PlantUML repair assistant.\n"
        "Repair all official PlantUML syntax errors. The compiler diagnostic shows "
        "the first failing line; inspect the full diagram for repeated occurrences "
        "of the same malformed pattern. Do not perform structural, "
        "behavioral, or semantic redesign.\n\n"
        "Non-negotiable preservation constraints:\n"
        "- Preserve every existing state concept. You may add an alias, but do not delete a state.\n"
        "- Preserve every complete transition, including its source, target, event, and guard.\n"
        "- Preserve every state entry, do, and exit action and its label text.\n"
        "- Do not shorten, summarize, rename, merge, or remove requirement-supported behavior.\n"
        "- Do not add new behavior. Make only the smallest edits required for compilation.\n"
        "- A dangling fragment such as `State -->` is not a complete transition and may be removed.\n"
        "- Return the complete corrected PlantUML only, without markdown fences or explanation.\n\n"
        "Useful valid syntax patterns:\n"
        "title Diagram Title\n"
        'state "Display Name" as StateAlias\n'
        "StateAlias : entry / action text\n"
        "StateAlias : do / action text\n"
        "StateAlias : exit / action text\n"
        "SourceAlias --> TargetAlias : event [guard]\n"
        "CompositeState.ChildState --> TargetState : event\n"
        "[*] --> InitialState\n"
        "FinalState --> [*]\n"
        "Use aliases, not quoted display names, as transition endpoints.\n"
        "Remove explanatory prose accidentally placed between @startuml and @enduml.\n"
        "Replace semicolon-separated label fragments with valid `/` or `\\n` label text.\n\n"
        "Official PlantUML compiler diagnostic:\n"
        f"{diagnostic}\n\n"
        "Requirement (for preservation checking only; do not add missing behavior):\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n"
    )


def build_compiler_constrained_patch_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    del requirement
    syntax_issues = [
        issue
        for issue in _prioritized_repair_issues(validation)
        if "plantuml_syntax_error" in issue.lower()
    ]
    diagnostic = (
        "\n".join(f"- {issue}" for issue in syntax_issues)
        if syntax_issues
        else "- No official compiler diagnostic was captured."
    )
    numbered_candidate = "\n".join(
        f"{line_number:04d}|{line}"
        for line_number, line in enumerate(candidate_puml.splitlines(), start=1)
    )
    previous_rejection = ""
    if critic_feedback.strip():
        previous_rejection = (
            "\nPrevious patch rejection:\n"
            f"{critic_feedback.strip()}\n"
            "Return a different patch that avoids this rejection.\n"
        )
    return (
        "You are a compiler-guided PlantUML syntax patch assistant.\n"
        "Fix only the official PlantUML compiler error. Do not return a complete "
        "diagram. Return exactly one JSON object containing line edits.\n\n"
        "Non-negotiable constraints:\n"
        "- Preserve every existing state, complete transition, event, guard, label, "
        "and entry/do/exit action.\n"
        "- Do not rename, merge, delete, summarize, or add behavior.\n"
        "- Make the fewest and smallest edits needed for PlantUML compilation.\n"
        "- Line numbers are 1-based and refer to the numbered candidate below.\n"
        "- `old` must exactly match the current unnumbered line, including indentation.\n"
        "- Supported operations are replace, delete, insert_before, and insert_after.\n"
        "- For replace and insert operations, `new` is required and may contain `\\n`.\n"
        "- For delete, omit `new` or set it to an empty string.\n"
        "- Use at most 20 edits. Do not include markdown or explanation.\n\n"
        "Required JSON shape:\n"
        '{"edits":[{"operation":"replace","line":3,'
        '"old":"Choice <<choice>>","new":"state Choice <<choice>>"}]}\n\n'
        "Official PlantUML compiler diagnostic:\n"
        f"{diagnostic}\n"
        f"{previous_rejection}\n"
        "Numbered candidate PlantUML (the `0001|` prefixes are not part of the file):\n"
        f"{numbered_candidate}\n"
    )


def build_issue_routed_sequential_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
    route: str = "syntax_grounded",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    target_issue = validation_issues[0] if validation_issues else ""
    if "plantuml_syntax_error" in target_issue.lower():
        return build_compiler_guided_syntax_repair_prompt(
            requirement,
            candidate_puml,
            validation,
            critic_feedback,
        )

    target_issues = [target_issue] if target_issue else []
    repair_guidance = _repair_guidance_for_issues(target_issues)
    syntax_patterns = (
        format_syntax_patterns(target_issues)
        if route == "syntax_grounded"
        else ""
    )
    route_instruction = (
        "Use direct natural-language repair guidance for this target issue."
        if route == "baseline"
        else "Use the relevant valid PlantUML pattern for this target issue."
    )
    pattern_section = (
        "\n\nValid PlantUML pattern for the target issue:\n" + syntax_patterns
        if syntax_patterns
        else ""
    )
    return (
        "You are an issue-routed sequential PlantUML repair assistant.\n"
        "Fix exactly one validation issue in this attempt.\n"
        f"Selected repair strategy: {route}.\n"
        f"{route_instruction}\n"
        "Make the smallest possible edit that removes the target issue.\n"
        "Preserve every unaffected state, transition, name, label, and "
        "requirement-supported behavior.\n"
        "Do not attempt unrelated repairs. Do not introduce any new validation issue.\n"
        "Return only the complete corrected PlantUML code with no markdown fences "
        "or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Target validation issue for this attempt:\n"
        + (f"- {target_issue}" if target_issue else "- none")
        + "\n\nRepair guidance:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + pattern_section
    )


def build_transition_patch_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    graph = parse_plantuml(candidate_puml)
    validation_issues = _prioritized_repair_issues(validation)
    diagnostic_issues = _diagnostic_validation_issue_lines(candidate_puml, validation)
    reachable_hint = ""
    if validation.initial_state:
        reachable_hint = f"Current initial/reachable start state: {validation.initial_state}\n"
    unreachable = validation.unreachable_states
    if not unreachable:
        orphan_issues = [
            item
            for item in list(validation.errors) + list(validation.warnings)
            if item.startswith("orphan:")
        ]
        if orphan_issues:
            unreachable = [
                state.strip()
                for item in orphan_issues
                for state in item.split(":", 1)[-1].split(",")
                if state.strip()
            ]
    states = ", ".join(sorted(graph.states)) if graph.states else "none detected"
    target_states = ", ".join(unreachable) if unreachable else "use the listed validation issues"
    return (
        "General instruction:\n"
        "You are a PlantUML transition-patch assistant. Return ONLY transition lines to insert into the candidate diagram. "
        "Do not return @startuml, @enduml, full diagrams, markdown fences, comments, explanations, state declarations, or notes.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + "\n".join(diagnostic_issues)
        + "\n\n"
        f"{reachable_hint}"
        f"Existing states: {states}\n"
        f"States that need connection: {target_states}\n\n"
        "Patch task:\n"
        "- Add the minimum transition lines needed to make the disconnected states reachable.\n"
        "- Prefer existing states from the candidate diagram.\n"
        "- Do not rename states.\n"
        "- Do not remove or rewrite existing transitions.\n"
        "- Each output line must be valid PlantUML transition syntax.\n\n"
        "Output format:\n"
        "SOURCE_STATE --> TARGET_STATE : SUPPORTED_EVENT\n"
        "TARGET_STATE --> NEXT_STATE : SUPPORTED_EVENT\n"
    )


def build_hybrid_issue_guided_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    issue_details = _validation_issue_details(validation)
    repair_blocks = format_hybrid_issue_repair_blocks(validation_issues)
    return (
        "You are a PlantUML state-machine repair assistant.\n\n"
        "Your task is to fix all listed validation issues while preserving the rest of the diagram.\n\n"
        "Follow these priorities in order:\n\n"
        "1. Fix every listed validation issue.\n"
        "2. Preserve the behavior described in the requirement.\n"
        "3. Make the smallest possible edit.\n"
        "4. Keep unaffected states, transitions, and labels unchanged.\n"
        "5. Do not introduce any new validation issue.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
        + "\n\nValidator details:\n"
        + "\n".join(f"- {detail}" for detail in issue_details)
        + "\n\nIssue-specific repair instructions:\n"
        + repair_blocks
        + "\n\nGeneral repair constraints:\n\n"
        "* Apply only the repair instructions corresponding to the listed validation issues.\n"
        "* Fix every occurrence of each listed issue.\n"
        "* Prefer using existing states and transitions.\n"
        "* Add a new state or transition only when necessary to fix a listed issue and supported by the requirement.\n"
        "* Do not remove a requirement-supported state only to make the diagram valid.\n"
        "* Do not rename unaffected states.\n"
        "* Do not change unaffected transition labels.\n"
        "* Do not redesign or simplify unaffected parts of the diagram.\n"
        "* Uppercase identifiers in syntax patterns are placeholders. Replace them with candidate- and requirement-supported identifiers.\n"
        "* Never copy placeholder identifiers into the corrected diagram.\n"
        "* When several repairs are valid, choose the repair that changes the fewest lines.\n\n"
        "Before producing the answer, silently verify:\n\n"
        "* Every listed validation issue has been fixed.\n"
        "* No new structural violation has been introduced.\n"
        "* Exactly one top-level initial transition exists.\n"
        "* At least one valid final transition exists.\n"
        "* Every retained state is connected and reachable.\n"
        "* No duplicate transition remains.\n"
        "* Unaffected diagram behavior is unchanged.\n\n"
        "Output only one corrected PlantUML diagram.\n"
        "Do not output markdown fences, explanations, comments, or analysis."
    )


def build_syntax_grounded_pattern_rules_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    issue_details = _validation_issue_details(validation)
    syntax_patterns = format_syntax_patterns(validation_issues)
    structural_patterns = format_all_structural_validation_patterns()
    return (
        "You are a PlantUML repair assistant.\n"
        "Repair the candidate using the valid PlantUML syntax patterns below.\n"
        "The uppercase identifiers in the patterns are placeholders, not literal state names.\n"
        "Replace placeholders only with existing or requirement-supported states, events, and guards.\n"
        "Apply only patterns that correspond to the listed validation issues.\n"
        "Keep unaffected states, transitions, labels, and behavior unchanged.\n"
        "Do not copy placeholder identifiers into the final diagram.\n"
        "Output ONLY one corrected PlantUML diagram. No markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues:\n"
        + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
        + "\n\nValidator details:\n"
        + "\n".join(f"- {detail}" for detail in issue_details)
        + "\n\n"
        + structural_patterns
        + "\n\nValid PlantUML repair patterns:\n"
        + syntax_patterns
    )


def build_sequential_syntax_grounded_pattern_rules_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    target_issue = validation_issues[0] if validation_issues else ""
    target_issues = [target_issue] if target_issue else []
    syntax_patterns = format_syntax_patterns(target_issues)
    structural_patterns = format_all_structural_validation_patterns()
    return (
        "You are a sequential PlantUML repair assistant.\n"
        "Fix exactly one validation issue in this attempt: the target issue below.\n"
        "Use only the PlantUML syntax patterns relevant to this target issue.\n"
        "The uppercase identifiers in the patterns are placeholders, not literal state names.\n"
        "Replace placeholders only with existing or requirement-supported states, events, and guards.\n"
        "Make the smallest possible edit.\n"
        "Keep unaffected states, transitions, labels, and behavior unchanged.\n"
        "Do not copy placeholder identifiers into the final diagram.\n"
        "Output ONLY one corrected PlantUML diagram. No markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Target validation issue for THIS attempt:\n"
        + (f"- {target_issue}" if target_issue else "- none")
        + "\n\n"
        + structural_patterns
        + "\n\nValid PlantUML repair patterns for the target issue:\n"
        + syntax_patterns
        + "\n\nNow repair only the target issue. Return one corrected PlantUML diagram."
    )


def build_full_pattern_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    pattern_block = format_all_structural_validation_patterns()
    return (
        "You are a PlantUML repair assistant.\n"
        "Repair the candidate using the PlantUML structural-validation patterns below.\n"
        "Apply only the patterns needed for the listed validation issues.\n"
        "The uppercase identifiers are placeholders; replace them with requirement-supported identifiers.\n"
        "Keep unaffected states, transitions, labels, and behavior unchanged.\n"
        "Output ONLY one corrected PlantUML diagram. No markdown fences or explanation.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues to fix:\n"
        + ("\n".join(f"- {issue}" for issue in validation_issues) if validation_issues else "- none")
        + "\n\n"
        + pattern_block
    )


def build_example_guided_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
    repair_example_dataset: Path | None = None,
    examples_per_issue: int = 2,
    exclude_example_case_id: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    repair_guidance = _repair_guidance_for_issues(validation_issues)
    structural_rules = _format_structural_validation_rules()
    examples: list[dict[str, Any]] = []
    if repair_example_dataset is not None:
        examples = _select_repair_examples(
            repair_example_dataset=repair_example_dataset,
            issues=validation_issues,
            requirement=requirement,
            candidate_puml=candidate_puml,
            examples_per_issue=examples_per_issue,
            exclude_case_id=exclude_example_case_id,
        )
    example_block = _format_repair_examples(examples)
    return (
        "You are a UML repair assistant.\n"
        "Fix the candidate PlantUML using the validation issues, repair guidance, and historical repair examples below.\n"
        "The historical examples show how similar violations were repaired in past diagrams.\n"
        "Use them as repair patterns only; do not copy domain-specific states, transitions, or labels unless supported by the target requirement.\n"
        "Make the smallest possible edit.\n"
        "Do not add new states or transitions unless a listed issue cannot be fixed without doing so.\n"
        "Do not remove or rename unaffected states.\n"
        "Do not change unaffected transition labels.\n"
        "Do not redesign or simplify the diagram.\n"
        "Only change the lines needed to fix the listed validation issues.\n"
        "Preserve the requirement meaning. Output ONLY corrected PlantUML. No explanations.\n\n"
        "Target requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML to repair:\n"
        f"{candidate_puml}\n\n"
        "Validation issues to fix:\n"
        + ("\n".join(f"- {err}" for err in validation_issues) if validation_issues else "- none")
        + "\n\n--- Structural Validation Rules ---\n"
        + structural_rules
        + "\n\nRepair guidance for these issues:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + "\n\n--- Historical Violation-Specific Repair Examples ---\n"
        + example_block
        + "\n\nNow repair the target candidate PlantUML. Return only one corrected PlantUML diagram."
    )


def build_sequential_example_guided_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
    repair_example_dataset: Path | None = None,
    examples_per_issue: int = 2,
    exclude_example_case_id: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    target_issue = validation_issues[0] if validation_issues else ""
    target_issues = [target_issue] if target_issue else []
    repair_guidance = _repair_guidance_for_issues(target_issues)
    examples: list[dict[str, Any]] = []
    if repair_example_dataset is not None and target_issues:
        examples = _select_repair_examples(
            repair_example_dataset=repair_example_dataset,
            issues=target_issues,
            requirement=requirement,
            candidate_puml=candidate_puml,
            examples_per_issue=examples_per_issue,
            exclude_case_id=exclude_example_case_id,
        )
    example_block = _format_compact_repair_examples(examples)
    return (
        "You are a sequential UML repair assistant.\n"
        "Fix exactly one validation issue in this attempt: the target issue below.\n"
        "Use the historical repair examples as patterns for this target issue only.\n"
        "Make the smallest possible edit that fixes the target issue.\n"
        "Preserve all unaffected states, transitions, names, labels, and requirement-supported behavior.\n"
        "Do not try to solve the later issues unless the same small edit naturally fixes them.\n"
        "Do not introduce any new validation issue.\n"
        "Output ONLY corrected PlantUML. No explanations.\n\n"
        "Target requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML to repair:\n"
        f"{candidate_puml}\n\n"
        "Target validation issue for THIS attempt:\n"
        + (f"- {target_issue}" if target_issue else "- none")
        + "\n\nRepair guidance for the target issue:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + "\n\n--- Historical Repair Examples for the Target Issue ---\n"
        + example_block
        + "\n\nNow repair only the target issue. Return one corrected PlantUML diagram."
    )


def build_sequential_baseline_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    target_issue = validation_issues[0] if validation_issues else ""
    target_issues = [target_issue] if target_issue else []
    repair_guidance = _repair_guidance_for_issues(target_issues)
    return (
        "You are a sequential UML repair assistant.\n"
        "Fix exactly one validation issue in this attempt: the target issue below.\n"
        "Make the smallest possible edit that fixes the target issue.\n"
        "Preserve all unaffected states, transitions, names, labels, and requirement-supported behavior.\n"
        "Do not try to solve later issues unless the same small edit naturally fixes them.\n"
        "Do not introduce any new validation issue.\n"
        "Output ONLY corrected PlantUML. No explanations.\n\n"
        "Target requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML to repair:\n"
        f"{candidate_puml}\n\n"
        "Target validation issue for THIS attempt:\n"
        + (f"- {target_issue}" if target_issue else "- none")
        + "\n\nRepair guidance for the target issue:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
        + "\n\nNow repair only the target issue. Return one corrected PlantUML diagram."
    )


def build_repair_prompt(
    requirement: str,
    candidate_puml: str,
    validation: ValidationResult,
    critic_feedback: str = "",
) -> str:
    validation_issues = _prioritized_repair_issues(validation)
    repair_guidance = _repair_guidance_for_issues(validation_issues)
    structural_rules = _format_structural_validation_rules()
    return (
        "You are a UML repair assistant.\n"
        "Fix the candidate PlantUML using only the validation issues and repair guidance below.\n"
        "Make the smallest possible edit.\n"
        "Do not add new states or transitions unless a listed issue cannot be fixed without doing so.\n"
        "Do not remove or rename unaffected states.\n"
        "Do not change unaffected transition labels.\n"
        "Do not redesign or simplify the diagram.\n"
        "Only change the lines needed to fix the listed validation issues.\n"
        "Preserve the requirement meaning. Output ONLY corrected PlantUML. No explanations.\n\n"
        "Requirement:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{candidate_puml}\n\n"
        "Validation issues to fix:\n"
        + ("\n".join(f"- {err}" for err in validation_issues) if validation_issues else "- none")
        + "\n\n--- Structural Validation Rules ---\n"
        + structural_rules
        + "\n\nRepair guidance for these issues:\n"
        + "\n".join(f"- {hint}" for hint in repair_guidance)
    )
