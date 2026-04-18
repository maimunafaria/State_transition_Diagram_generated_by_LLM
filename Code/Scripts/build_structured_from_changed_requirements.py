#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"


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
    "clients",
    "client",
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
    "companies",
    "company",
    "employers",
    "employer",
    "job seekers",
    "job seeker",
    "staff",
    "manager",
]


CAPABILITY_RE = re.compile(
    r"\b("
    r"allow|allows|enable|enables|support|supports|generate|generates|calculate|calculates|"
    r"notify|notifies|update|updates|manage|manages|monitor|monitors|track|tracks|"
    r"operate|operated|submit|submitted|cancel|cancelled|pass|passed|regulate|regulated|"
    r"detect|detection|warn|view|check|log|register|issue|search|replace|remove|add|place|create|"
    r"select|selects|order|orders|provide|provides|fill|fills|upload|uploads|verify|verifies|"
    r"purchase|purchases|transfer|dispense|dispenses|print|prints|return|returns|process|processes|"
    r"transition|transitions|enter|enters|reenter|reenters|leave|leaves|open|opens|close|closes|"
    r"press|presses|input|inputs|expire|expires|withdraw|withdraws|authorize|authorizes"
    r")\b",
    re.IGNORECASE,
)

MODAL_RE = re.compile(
    r"\b(must|should|shall|can|needs to|need to|required to|is required|able to)\b",
    re.IGNORECASE,
)

CONDITIONAL_RE = re.compile(r"\b(if|when|once|after|before|upon|at any point)\b", re.IGNORECASE)

CHANGED_PLAIN_RE = re.compile(r"^(?:raw_requirement|aw_requirement)_changed\.txt$")
CHANGED_INDEXED_RE = re.compile(r"^(?:raw_requirement|aw_requirement)_(\d+)_changed\.txt$")


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


def case_title(case_name: str) -> str:
    value = re.sub(r"^case_\d+_", "", case_name)
    value = value.replace("_", " ").strip()
    if not value:
        return case_name
    return " ".join(word.capitalize() for word in value.split())


def clean_clause(text: str) -> str:
    clause = re.sub(r"\s+", " ", text).strip()
    clause = re.sub(r"\(Figures?[^)]*\)", "", clause, flags=re.IGNORECASE).strip()
    clause = re.sub(r"(?<=\w)\.(\d+)\.", ". ", clause)
    clause = re.sub(
        r"^(however|hence|furthermore|therefore|moreover|in addition|as a result|next|then)\s*,?\s*",
        "",
        clause,
        flags=re.IGNORECASE,
    )
    clause = clause.strip(" :-")
    return clause


def extract_actors(text: str) -> list[str]:
    lower = text.lower()
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


def is_requirement_sentence(sentence: str) -> bool:
    s = clean_clause(sentence)
    if not s:
        return False
    low = s.lower()
    if "incomplete" in low and "requirement" in low:
        return False
    score = 0
    if CAPABILITY_RE.search(low):
        score += 2
    if MODAL_RE.search(low):
        score += 2
    if CONDITIONAL_RE.search(low):
        score += 1
    if re.search(r"\b(state|transition|event|trigger|action)\b", low):
        score += 1
    if re.search(r"\bbackground|overview|context\b", low):
        score -= 1
    return score >= 1


def normalize_actor_action(action: str) -> str:
    action = action.strip()
    action = re.sub(r"^(then|next|once again)\s+", "", action, flags=re.IGNORECASE)
    action = re.sub(r"^will\s+", "", action, flags=re.IGNORECASE)
    action = re.sub(r"^is able to\s+", "", action, flags=re.IGNORECASE)
    action = re.sub(r"^able to\s+", "", action, flags=re.IGNORECASE)
    action = re.sub(r"^to\s+", "", action, flags=re.IGNORECASE)

    base_map = {
        "selects": "select",
        "orders": "order",
        "views": "view",
        "creates": "create",
        "fills": "fill",
        "provides": "provide",
        "updates": "update",
        "checks": "check",
        "tracks": "track",
        "places": "place",
        "presses": "press",
        "closes": "close",
        "opens": "open",
        "inputs": "input",
        "goes": "go",
        "returns": "return",
        "dispenses": "dispense",
        "prints": "print",
        "processes": "process",
        "transitions": "transition",
    }
    first = action.split(" ", 1)[0]
    if first in base_map:
        action = base_map[first] + action[len(first):]

    for inflected, base in base_map.items():
        action = re.sub(rf"\band {inflected}\b", f"and {base}", action, flags=re.IGNORECASE)

    return action.strip(" ,.")


def to_shall(sentence: str) -> str:
    desc = clean_clause(sentence)
    if not desc:
        return ""

    desc = lower_first(desc)
    low = desc.lower()
    if low.startswith("the system shall"):
        return ensure_period(desc)

    actor_modal = re.match(
        r"^(?:the\s+)?(customer|client|user|patient|admin|administrator|seller|driver|student|citizen|staff|manager)\s+"
        r"(?:can|needs? to|need to|must|shall|should|is able to|able to)\s+(.+)$",
        low,
    )
    if actor_modal:
        actor, action = actor_modal.group(1), normalize_actor_action(actor_modal.group(2))
        return ensure_period(f"The system shall allow the {actor} to {action}")

    actor_action = re.match(
        r"^(?:the\s+)?(customer|client|user|patient|admin|administrator|seller|driver|student|citizen|staff|manager)\s+(.+)$",
        low,
    )
    if actor_action:
        actor, action = actor_action.group(1), normalize_actor_action(actor_action.group(2))
        return ensure_period(f"The system shall allow the {actor} to {action}")

    if re.match(
        r"^(allow|allows|enable|enables|support|supports|generate|generates|calculate|calculates|"
        r"notify|notifies|update|updates|manage|manages|monitor|monitors|track|tracks|provide|provides|"
        r"create|creates|store|stores|remove|removes|replace|replaces|search|searches|place|places|"
        r"issue|issues|view|views|collect|collects|cancel|cancels|register|registers|log|logs|authenticate|authenticates)\b",
        low,
    ):
        return ensure_period(f"The system shall {desc}")

    if CONDITIONAL_RE.search(low) or re.search(r"\b(is|are|will be|shall be)\b", low):
        return ensure_period(f"The system shall ensure that {desc}")

    return ensure_period(f"The system shall support {desc}")


def discover_changed_files(case_dir: Path) -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for p in sorted(case_dir.glob("*requirement*changed*.txt")):
        name = p.name
        if CHANGED_PLAIN_RE.match(name):
            result.append((p, ""))
            continue
        m = CHANGED_INDEXED_RE.match(name)
        if m:
            result.append((p, m.group(1)))
    result.sort(key=lambda x: (0 if x[1] == "" else 1, int(x[1]) if x[1].isdigit() else 0, x[0].name))
    return result


def build_structured_text(case_name: str, changed_text: str, suffix: str) -> str:
    text = normalize_ws(changed_text)
    sentences = sentence_split(text)
    title = case_title(case_name)

    lines: list[str] = []
    if suffix:
        lines.append(f"{title} — Scenario {suffix} Structured Requirement Specification")
    else:
        lines.append(f"{title} — Structured Requirement Specification")
    lines.append("")

    lines.append("Overview")
    if sentences:
        lines.append(ensure_period(" ".join(sentences[: min(3, len(sentences))])))
    else:
        lines.append("No readable requirement content is available in the source changed file.")
    lines.append("")

    lines.append("Operational Context")
    actors = extract_actors(text)
    if actors:
        lines.append(f"Primary actors include {', '.join(actors)}.")
    else:
        lines.append("Primary actors are not explicitly stated in the source text.")
    lines.append("")

    lines.append("Functional Requirements")
    candidates = [s for s in sentences if is_requirement_sentence(s)]
    if not candidates and sentences:
        candidates = sentences

    reqs = dedupe_keep_order([to_shall(s) for s in candidates if to_shall(s)])
    if not reqs:
        reqs = ["The system shall provide the capabilities described in the source changed requirement text."]

    for idx, req in enumerate(reqs[:15], start=1):
        lines.append(f"{idx}. {req}")
    lines.append("")
    return "\n".join(lines)


def find_case_dirs(dataset_root: Path, start_case: int, end_case: int) -> list[Path]:
    dirs: list[Path] = []
    for p in sorted(dataset_root.glob("case_*")):
        if not p.is_dir():
            continue
        m = re.match(r"^case_(\d+)_", p.name)
        if not m:
            continue
        num = int(m.group(1))
        if start_case <= num <= end_case:
            dirs.append(p)
    return dirs


def process_case(case_dir: Path, overwrite: bool) -> tuple[int, int, int]:
    files = discover_changed_files(case_dir)
    if not files:
        return (0, 0, 0)

    created = 0
    skipped = 0
    errors = 0

    for changed_path, suffix in files:
        if suffix:
            out_name = f"structured_requirement_{suffix}.txt"
        else:
            out_name = "structured_requirement.txt"
        out_path = case_dir / out_name

        if out_path.exists() and not overwrite:
            skipped += 1
            continue

        try:
            changed_text = changed_path.read_text(encoding="utf-8")
            structured = build_structured_text(case_dir.name, changed_text, suffix)
            out_path.write_text(structured, encoding="utf-8")
            created += 1
        except Exception:
            errors += 1

    return (created, skipped, errors)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create structured_requirement files from raw_requirement_changed variants. "
            "Supports raw_requirement_changed.txt and raw_requirement_<n>_changed.txt."
        )
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--start-case", type=int, default=1)
    parser.add_argument("--end-case", type=int, default=999)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    case_dirs = find_case_dirs(args.dataset_root, args.start_case, args.end_case)
    if not case_dirs:
        raise RuntimeError(
            f"No case folders found in range case_{args.start_case:02d} to case_{args.end_case:02d}."
        )

    print(
        f"Building structured requirements from changed inputs for {len(case_dirs)} cases "
        f"(range {args.start_case}-{args.end_case})."
    )

    total_created = 0
    total_skipped = 0
    total_errors = 0
    total_cases_with_changed = 0

    for case_dir in case_dirs:
        changed_files = discover_changed_files(case_dir)
        if not changed_files:
            continue
        total_cases_with_changed += 1

        created, skipped, errors = process_case(case_dir, overwrite=args.overwrite)
        total_created += created
        total_skipped += skipped
        total_errors += errors
        print(
            f"[ok] {case_dir.name}: changed_files={len(changed_files)} "
            f"created={created} skipped={skipped} errors={errors}"
        )

    print("Done.")
    print(f"cases_with_changed={total_cases_with_changed}")
    print(f"created={total_created}")
    print(f"skipped={total_skipped}")
    print(f"errors={total_errors}")


if __name__ == "__main__":
    main()

