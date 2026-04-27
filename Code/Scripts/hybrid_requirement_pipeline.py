#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plantuml_pipeline.model_client import call_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"

DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"


ACTOR_TERMS = [
    "inventory managers",
    "inventory manager",
    "salespersons",
    "salesperson",
    "administrators",
    "administrator",
    "admin",
    "customers",
    "customer",
    "patients",
    "patient",
    "caregivers",
    "caregiver",
    "doctors",
    "doctor",
    "sellers",
    "seller",
    "users",
    "user",
    "citizens",
    "citizen",
    "students",
    "student",
    "drivers",
    "driver",
    "donors",
    "donor",
    "volunteers",
    "volunteer",
    "authorities",
    "authority",
    "companies",
    "company",
    "employers",
    "employer",
    "job seekers",
    "job seeker",
]

CAPABILITY_RE = re.compile(
    r"\b("
    r"allow|allows|enable|enables|support|supports|generate|generates|calculate|calculates|"
    r"notify|notifies|update|updates|manage|manages|monitor|monitors|track|tracks|"
    r"operate|operated|submit|submitted|cancel|cancelled|pass|passed|regulate|regulated|"
    r"detect|detection|warn|stock|view|check|log|register|issue|search|replace|remove|add|place|create|"
    r"select|selects|order|orders|provide|provides|fill|fills|upload|uploads|verify|verifies|purchase|purchases|"
    r"transition|transitions|enter|enters|reenter|reenters|leave|leaves|open|opens|close|closes|"
    r"press|presses|input|inputs|expire|expires|list|lists|serve|serves|predict|predicts|"
    r"shortlist|shortlists|assess|assesses|map|maps|alert|alerts"
    r")\b",
    re.IGNORECASE,
)

AMBIGUOUS_TERMS = [
    "etc",
    "and so on",
    "user friendly",
    "easy to use",
    "efficient",
    "quickly",
    "some",
    "many",
    "appropriate",
    "suitable",
    "as needed",
]

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "that",
    "this",
    "these",
    "those",
    "it",
    "its",
    "as",
    "at",
    "from",
    "into",
    "than",
    "then",
    "if",
    "when",
    "while",
    "can",
    "will",
    "shall",
    "should",
    "would",
    "could",
    "may",
    "might",
    "must",
    "not",
    "no",
    "so",
    "such",
    "their",
    "his",
    "her",
    "our",
    "your",
    "they",
    "them",
    "he",
    "she",
    "we",
    "you",
    "i",
}


def normalize_ws(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("\u200b", " ")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentence_split(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = re.split(r"(?<=[.!?])\s+", compact)
    return [p.strip() for p in parts if p.strip()]


def canonical(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", text.lower()).strip(" .")


def ensure_period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text[-1] in ".!?":
        return text
    return f"{text}."


def lower_first(text: str) -> str:
    if not text:
        return text
    if len(text) == 1:
        return text.lower()
    if text[0].isupper() and not text[:2].isupper():
        return text[0].lower() + text[1:]
    return text


def dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = canonical(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item.strip())
    return out


def clean_clause(text: str) -> str:
    clause = re.sub(r"\s+", " ", text).strip()
    clause = re.sub(r"\(Figures?[^)]*\)", "", clause, flags=re.IGNORECASE).strip()
    clause = re.sub(r"(?<=\w)\.(\d+)\.", ". ", clause)
    clause = re.sub(
        r"^(however|hence|furthermore|therefore|moreover|in addition|on one hand|on the other hand|"
        r"as a result|before it|next|then|if instead)\s*,?\s*",
        "",
        clause,
        flags=re.IGNORECASE,
    )
    clause = re.sub(r"^to\s+", "", clause, flags=re.IGNORECASE)
    clause = clause.strip(" :-")
    return clause


def case_title(case_name: str) -> str:
    value = re.sub(r"^case_\d+_", "", case_name)
    value = value.replace("_", " ").strip()
    if not value:
        return case_name
    return " ".join(word.capitalize() for word in value.split())


def summarize(raw_text: str) -> str:
    sentences = [s for s in sentence_split(raw_text) if "figure" not in s.lower()]
    if not sentences:
        return ""
    return " ".join(sentences[:3]).strip()


def extract_actors(raw_text: str) -> list[str]:
    lower = raw_text.lower()
    found = []
    for term in ACTOR_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", lower):
            found.append(term)
    ordered = dedupe_keep_order(found)
    final: list[str] = []
    lowered = {x.lower() for x in ordered}
    for term in ordered:
        if term.endswith("s") and term[:-1] in lowered:
            continue
        final.append(term)
    return final


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {tok for tok in tokens if tok not in STOPWORDS and len(tok) > 2}


def jaccard(a: str, b: str) -> float:
    ta = tokenize(a)
    tb = tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    candidates: list[str] = [text]

    for pattern in (r"```json\s*(.*?)```", r"```\s*(.*?)```"):
        m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if m:
            candidates.append(m.group(1).strip())

    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(text[first : last + 1])

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise RuntimeError(f"Could not parse JSON object from LLM response: {text[:400]}")


def call_llm_json(
    model_name: str,
    prompt: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> tuple[dict[str, Any], str]:
    response = call_model(
        model_name=model_name,
        prompt=prompt,
        ollama_host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    parsed = extract_json_object(response)
    return parsed, response


def build_extractor_prompt(raw_text: str) -> str:
    return f"""
You are a requirements engineer.
Extract functional software requirements from the source text.

Return ONLY valid JSON with this schema:
{{
  "functional_requirements": [
    {{
      "requirement": "string",
      "evidence_quote": "short exact quote from source text"
    }}
  ]
}}

Rules:
1. Include only system capabilities/behaviors.
2. Exclude background context, impact statements, problem motivation, and pure business goals.
3. Keep each requirement atomic and clear.
4. Preserve original meaning. Do not invent functionality.
5. If uncertain, keep the item but keep evidence_quote explicit.

Source text:
<<<
{raw_text}
>>>
""".strip()


def build_rewriter_prompt(extracted: list[dict[str, str]]) -> str:
    payload = json.dumps({"functional_requirements": extracted}, ensure_ascii=False, indent=2)
    return f"""
You are a requirements rewriter.
Rewrite each requirement into clean natural language suitable for UML state diagram generation.

Return ONLY valid JSON with this schema:
{{
  "rewritten_requirements": [
    {{
      "source_requirement": "string",
      "rewritten_requirement": "The system shall ..."
    }}
  ]
}}

Rules:
1. Keep exactly the same number of requirements and same order.
2. Do not add new meaning.
3. Each rewritten requirement must start with "The system shall".
4. Keep them concise and implementation-neutral.

Input JSON:
{payload}
""".strip()


def build_validator_prompt(raw_text: str, rewritten: list[str]) -> str:
    payload = json.dumps({"rewritten_requirements": rewritten}, ensure_ascii=False, indent=2)
    return f"""
You are a strict requirements validator.
Compare rewritten requirements against the source text.

Return ONLY valid JSON with this schema:
{{
  "missing_requirements": [
    {{
      "evidence_quote": "string",
      "suggested_requirement": "The system shall ..."
    }}
  ],
  "hallucinations": [
    {{
      "rewritten_requirement": "string",
      "reason": "string"
    }}
  ],
  "duplicates": [
    {{
      "requirement_a": "string",
      "requirement_b": "string",
      "reason": "string"
    }}
  ],
  "ambiguities": [
    {{
      "rewritten_requirement": "string",
      "reason": "string"
    }}
  ],
  "overall_assessment": "pass|needs_review"
}}

Source text:
<<<
{raw_text}
>>>

Rewritten requirements JSON:
{payload}
""".strip()


def fallback_extract(raw_text: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for sent in sentence_split(raw_text):
        clean = clean_clause(sent)
        if not clean:
            continue
        low = clean.lower()
        if "figure" in low:
            continue
        if CAPABILITY_RE.search(low):
            candidates.append({"requirement": clean, "evidence_quote": sent.strip()})
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        key = canonical(item["requirement"])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def normalize_extracted(data: dict[str, Any]) -> list[dict[str, str]]:
    items = data.get("functional_requirements", [])
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        req = ""
        evidence = ""
        if isinstance(item, dict):
            req = clean_clause(str(item.get("requirement", "")).strip())
            evidence = str(item.get("evidence_quote", "")).strip()
        else:
            req = clean_clause(str(item).strip())
        if not req:
            continue
        key = canonical(req)
        if key in seen:
            continue
        seen.add(key)
        out.append({"requirement": req, "evidence_quote": evidence})
    return out


def to_shall(requirement: str) -> str:
    req = clean_clause(requirement)
    if not req:
        return ""
    low = req.lower()
    if low.startswith("the system shall"):
        return ensure_period(req)
    if re.match(
        r"^(allow|allows|enable|enables|support|supports|provide|provides|manage|manages|"
        r"monitor|monitors|track|tracks|detect|detects|verify|verifies|register|registers|"
        r"log|logs|view|views|create|creates|update|updates|cancel|cancels|search|searches|"
        r"order|orders|select|selects)\b",
        low,
    ):
        return ensure_period(f"The system shall {lower_first(req)}")
    if re.match(r"^(user|users|customer|customers|patient|patients|admin|administrator|driver|citizen|student)\b", low):
        return ensure_period(f"The system shall allow {lower_first(req)}")
    if re.search(r"\b(is|are|will be|shall be)\b", low):
        return ensure_period(f"The system shall ensure that {lower_first(req)}")
    return ensure_period(f"The system shall support {lower_first(req)}")


def normalize_rewritten(data: dict[str, Any], extracted: list[dict[str, str]]) -> list[str]:
    items = data.get("rewritten_requirements", [])
    if not isinstance(items, list):
        return []
    out: list[str] = []
    for item in items:
        text = ""
        if isinstance(item, dict):
            text = str(item.get("rewritten_requirement", "")).strip()
        else:
            text = str(item).strip()
        if not text:
            continue
        shall = to_shall(text)
        if shall:
            out.append(shall)
    if not out:
        out = [to_shall(x["requirement"]) for x in extracted if x.get("requirement")]
    return dedupe_keep_order([x for x in out if x])


def deterministic_validation(raw_text: str, rewritten: list[str]) -> dict[str, Any]:
    duplicates: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for idx, req in enumerate(rewritten):
        key = canonical(req)
        if key in seen:
            duplicates.append(
                {"first_index": seen[key] + 1, "duplicate_index": idx + 1, "requirement": req}
            )
        else:
            seen[key] = idx

    ambiguity_hits: list[dict[str, Any]] = []
    for idx, req in enumerate(rewritten):
        low = req.lower()
        hits = [term for term in AMBIGUOUS_TERMS if term in low]
        if hits:
            ambiguity_hits.append(
                {"index": idx + 1, "requirement": req, "terms": hits}
            )

    source_actions = []
    for sent in sentence_split(raw_text):
        clean = clean_clause(sent)
        if not clean:
            continue
        if "figure" in clean.lower():
            continue
        if CAPABILITY_RE.search(clean.lower()):
            source_actions.append(clean)

    potential_missing: list[dict[str, Any]] = []
    for sent in source_actions:
        overlap = max((jaccard(sent, req) for req in rewritten), default=0.0)
        if overlap < 0.20:
            potential_missing.append({"source_sentence": sent, "max_overlap": round(overlap, 3)})

    potential_hallucinations: list[dict[str, Any]] = []
    for req in rewritten:
        overlap = max((jaccard(req, sent) for sent in source_actions), default=0.0)
        if source_actions and overlap < 0.12:
            potential_hallucinations.append({"requirement": req, "max_overlap": round(overlap, 3)})

    needs_review = bool(duplicates or ambiguity_hits or potential_missing or potential_hallucinations)
    return {
        "duplicates": duplicates,
        "ambiguities": ambiguity_hits,
        "potential_missing": potential_missing[:20],
        "potential_hallucinations": potential_hallucinations[:20],
        "overall_assessment": "needs_review" if needs_review else "pass",
    }


def build_structured_requirement_text(case_name: str, raw_text: str, rewritten: list[str]) -> str:
    title = case_title(case_name)
    summary = summarize(raw_text)
    actors = extract_actors(raw_text)

    lines: list[str] = []
    lines.append(f"{title} - Polished Requirement Specification")
    lines.append("")
    lines.append("Overview")
    lines.append(ensure_period(summary) if summary else "Overview is not explicitly stated in the source text.")
    lines.append("")
    lines.append("Operational Context")
    if actors:
        lines.append(f"Primary actors include {', '.join(actors)}.")
    else:
        lines.append("Primary actors are not explicitly stated in the source text.")
    lines.append("")
    lines.append("Functional Requirements")
    if not rewritten:
        lines.append("1. The system shall provide the capabilities described in the source requirement text.")
    else:
        for idx, req in enumerate(rewritten, start=1):
            lines.append(f"{idx}. {req}")
    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_case(
    case_dir: Path,
    output_name: str,
    overwrite: bool,
    extractor_model: str,
    rewriter_model: str,
    validator_model: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
    disable_llm_validator: bool,
) -> dict[str, Any]:
    raw_path = case_dir / "raw_requirement.txt"
    out_path = case_dir / output_name

    if not raw_path.exists():
        return {"case_id": case_dir.name, "status": "skip_missing_raw"}
    if out_path.exists() and not overwrite:
        return {"case_id": case_dir.name, "status": "skip_exists"}

    raw_text = normalize_ws(raw_path.read_text(encoding="utf-8"))
    extraction_prompt = build_extractor_prompt(raw_text)
    rewriting_prompt = ""
    validation_prompt = ""

    extraction_error = ""
    rewriting_error = ""
    validator_error = ""

    extracted: list[dict[str, str]] = []
    rewritten: list[str] = []
    llm_validation: dict[str, Any] = {}

    extraction_response = ""
    rewriting_response = ""
    validator_response = ""

    try:
        extracted_obj, extraction_response = call_llm_json(
            model_name=extractor_model,
            prompt=extraction_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        extracted = normalize_extracted(extracted_obj)
    except Exception as exc:
        extraction_error = str(exc)

    if not extracted:
        extracted = fallback_extract(raw_text)

    rewriting_prompt = build_rewriter_prompt(extracted)
    try:
        rewritten_obj, rewriting_response = call_llm_json(
            model_name=rewriter_model,
            prompt=rewriting_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        rewritten = normalize_rewritten(rewritten_obj, extracted)
    except Exception as exc:
        rewriting_error = str(exc)

    if not rewritten:
        rewritten = [to_shall(x["requirement"]) for x in extracted if x.get("requirement")]
        rewritten = dedupe_keep_order([x for x in rewritten if x])

    if not disable_llm_validator:
        validation_prompt = build_validator_prompt(raw_text, rewritten)
        try:
            llm_obj, validator_response = call_llm_json(
                model_name=validator_model,
                prompt=validation_prompt,
                ollama_host=ollama_host,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            llm_validation = llm_obj
        except Exception as exc:
            validator_error = str(exc)
            llm_validation = {"overall_assessment": "needs_review", "error": validator_error}

    deterministic = deterministic_validation(raw_text, rewritten)
    final_status = "needs_review"
    if deterministic["overall_assessment"] == "pass":
        if disable_llm_validator:
            final_status = "pass"
        elif str(llm_validation.get("overall_assessment", "needs_review")).lower() == "pass":
            final_status = "pass"

    structured_text = build_structured_requirement_text(case_dir.name, raw_text, rewritten)
    out_path.write_text(structured_text, encoding="utf-8")

    extracted_artifact = {
        "case_id": case_dir.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": extractor_model,
        "functional_requirements": extracted,
        "errors": {"llm_extraction_error": extraction_error},
        "prompt": extraction_prompt,
        "llm_response": extraction_response,
    }
    write_json(case_dir / "functional_requirements_extracted.json", extracted_artifact)

    rewritten_artifact = {
        "case_id": case_dir.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": rewriter_model,
        "rewritten_requirements": rewritten,
        "source_extracted_requirements": extracted,
        "errors": {"llm_rewriting_error": rewriting_error},
        "prompt": rewriting_prompt,
        "llm_response": rewriting_response,
    }
    write_json(case_dir / "functional_requirements_rewritten.json", rewritten_artifact)

    validation_artifact = {
        "case_id": case_dir.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": validator_model if not disable_llm_validator else "",
        "disable_llm_validator": disable_llm_validator,
        "deterministic_validation": deterministic,
        "llm_validation": llm_validation,
        "errors": {"llm_validator_error": validator_error},
        "prompt": validation_prompt,
        "llm_response": validator_response,
        "final_assessment": final_status,
    }
    write_json(case_dir / "validation_report.json", validation_artifact)

    return {
        "case_id": case_dir.name,
        "status": "ok",
        "extracted_count": len(extracted),
        "rewritten_count": len(rewritten),
        "final_assessment": final_status,
        "has_errors": bool(extraction_error or rewriting_error or validator_error),
    }


def find_case_dirs(dataset_root: Path, start_case: int, end_case: int, cases: list[str] | None) -> list[Path]:
    case_dirs = sorted([p for p in dataset_root.glob("case_*") if p.is_dir()], key=lambda p: p.name)
    ranged: list[Path] = []
    for p in case_dirs:
        m = re.match(r"^case_(\d+)_", p.name)
        if not m:
            continue
        num = int(m.group(1))
        if start_case <= num <= end_case:
            ranged.append(p)
    if cases:
        selected = set(cases)
        ranged = [p for p in ranged if p.name in selected]
    return ranged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid LLM pipeline: extract, rewrite, validate, and build structured requirements."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--output-name", default="structured_requirement.txt")
    parser.add_argument("--start-case", type=int, default=1)
    parser.add_argument("--end-case", type=int, default=999)
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Default model for all three LLM passes.")
    parser.add_argument("--extractor-model", default="", help="Override model for extraction.")
    parser.add_argument("--rewriter-model", default="", help="Override model for rewriting.")
    parser.add_argument("--validator-model", default="", help="Override model for validation.")
    parser.add_argument("--disable-llm-validator", action="store_true")
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=2400)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    extractor_model = args.extractor_model or args.model
    rewriter_model = args.rewriter_model or args.model
    validator_model = args.validator_model or args.model

    case_dirs = find_case_dirs(args.dataset_root, args.start_case, args.end_case, args.cases)
    if args.cases and not case_dirs:
        raise RuntimeError(f"No matching case folders found for: {', '.join(args.cases)}")
    if not case_dirs:
        raise RuntimeError(f"No case_* folders found in {args.dataset_root}")

    print(
        "Pipeline configuration:"
        f" extractor={extractor_model}, rewriter={rewriter_model}, validator={validator_model},"
        f" llm_validator={'off' if args.disable_llm_validator else 'on'}"
    )

    summary = {
        "ok": 0,
        "skip_exists": 0,
        "skip_missing_raw": 0,
        "error": 0,
    }
    needs_review: list[str] = []
    errors: list[dict[str, str]] = []

    for case_dir in case_dirs:
        try:
            result = process_case(
                case_dir=case_dir,
                output_name=args.output_name,
                overwrite=args.overwrite,
                extractor_model=extractor_model,
                rewriter_model=rewriter_model,
                validator_model=validator_model,
                ollama_host=args.ollama_host,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                disable_llm_validator=args.disable_llm_validator,
            )
            status = str(result.get("status", "error"))
            summary[status] = summary.get(status, 0) + 1
            if result.get("final_assessment") == "needs_review":
                needs_review.append(case_dir.name)
            print(
                f"[{status}] {case_dir.name}"
                f" extracted={result.get('extracted_count', '-')}"
                f" rewritten={result.get('rewritten_count', '-')}"
                f" assessment={result.get('final_assessment', '-')}"
                f" errors={result.get('has_errors', '-')}"
            )
        except Exception as exc:
            summary["error"] = summary.get("error", 0) + 1
            errors.append({"case_id": case_dir.name, "error": str(exc)})
            print(f"[error] {case_dir.name}: {exc}")

    print("Done.")
    print(json.dumps(summary, indent=2))
    if needs_review:
        print("Needs review:")
        for case_id in needs_review:
            print(f"- {case_id}")
    if errors:
        print("Errors:")
        for item in errors:
            print(f"- {item['case_id']}: {item['error']}")


if __name__ == "__main__":
    main()
