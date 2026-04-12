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
]

NON_FEATURE_KEYS = {
    "description",
    "flow of events",
    "basic flow",
    "alternative flow",
    "pre-condition",
    "pre-conditions",
    "precondition",
    "preconditions",
    "post-condition",
    "post-conditions",
    "postcondition",
    "postconditions",
    "constraints",
    "constraint",
    "functionalities",
    "system functionalities",
}

LABEL_HEADER_RE = re.compile(
    r"^\s*(pre[-\s]?conditions?|post[-\s]?conditions?|triggers?|basic flow|alternative flow|constraints?)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def normalize_ws(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("\u200b", " ")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def merge_wrapped_lines(text: str) -> list[str]:
    raw_lines = text.splitlines()
    merged: list[str] = []

    def is_heading(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        if re.match(r"^\d+[.)]?\s+[A-Za-z]", s):
            return True
        if re.match(r"^[A-Za-z][A-Za-z0-9 /&(),'\-–]{1,120}\s*:", s):
            return True
        return False

    for raw in raw_lines:
        line = raw.strip()
        if not line:
            merged.append("")
            continue
        if not merged:
            merged.append(line)
            continue
        prev = merged[-1]
        if (
            prev
            and prev[-1] not in ".:!?"
            and not is_heading(line)
            and not re.match(r"^[•*-]\s*", line)
        ):
            merged[-1] = f"{prev} {line}".strip()
        else:
            merged.append(line)
    return merged


def canonical(text: str) -> str:
    return re.sub(r"[\s_-]+", " ", text.lower()).strip(" .")


def ensure_period(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text[-1] in ".!?":
        return text
    return f"{text}."


def sentence_split(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    parts = re.split(r"(?<=[.!?])\s+", compact)
    return [p.strip() for p in parts if p.strip()]


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
        r"^(this|the)\s+(process|functionality|module|system)\s+(allows?|will allow|enables?)\s+",
        "",
        clause,
        flags=re.IGNORECASE,
    )
    clause = re.sub(r"^(this|the)\s+(process|functionality|module|system)\s+", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^(this\s+)?will\s+", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^allows?\s+", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^can\s+", "", clause, flags=re.IGNORECASE)
    clause = re.sub(r"^to\s+", "", clause, flags=re.IGNORECASE)
    clause = clause.strip(" :-")
    return clause


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


def is_valid_feature_name(name: str) -> bool:
    key = canonical(name)
    if not key or key in {canonical(x) for x in NON_FEATURE_KEYS}:
        return False
    if len(name.split()) > 12:
        return False
    if key in {"pre", "post", "basic", "alternative", "flow"}:
        return False
    return True


def extract_features(raw_text: str) -> list[dict[str, str]]:
    lines = [ln for ln in merge_wrapped_lines(raw_text) if ln.strip()]
    feats: list[dict[str, str]] = []
    index: dict[str, int] = {}
    current_name = ""

    numbered_heading = re.compile(r"^\d+[.)]?\s*([A-Za-z][A-Za-z0-9 /&(),'\-]{1,100})\s*$")
    numbered_colon = re.compile(r"^\d+[.)]?\s*([A-Za-z][A-Za-z0-9 /&(),'\-–]{1,100})\s*:\s*(.+)$")
    colon_line = re.compile(r"^([A-Za-z][A-Za-z0-9 /&(),'\-–]{1,100})\s*:\s*(.+)$")
    dash_line = re.compile(r"^([A-Za-z][A-Za-z0-9 /&(),'\-]{1,100})\s+[–-]\s+(.+)$")
    desc_line = re.compile(r"^\s*Description\s*:\s*(.+)$", re.IGNORECASE)

    def upsert(name: str, desc: str) -> None:
        clean_name = name.strip(" .")
        if not is_valid_feature_name(clean_name):
            return
        key = canonical(clean_name)
        clean_desc = clean_clause(desc)
        if key in index:
            pos = index[key]
            if clean_desc and not feats[pos]["description"]:
                feats[pos]["description"] = clean_desc
            return
        feats.append({"name": clean_name, "description": clean_desc})
        index[key] = len(feats) - 1

    for i, line in enumerate(lines):
        m = numbered_heading.match(line)
        if m:
            current_name = m.group(1).strip(" .")
            upsert(current_name, "")
            continue

        m = numbered_colon.match(line)
        if m:
            key, value = m.group(1).strip(" ."), m.group(2)
            if canonical(key) in {canonical(x) for x in NON_FEATURE_KEYS}:
                continue
            current_name = key
            upsert(key, value)
            continue

        m = desc_line.match(line)
        if m and current_name:
            upsert(current_name, m.group(1))
            continue

        m = colon_line.match(line)
        if m:
            key, value = m.group(1).strip(" ."), m.group(2)
            if canonical(key) in {canonical(x) for x in NON_FEATURE_KEYS}:
                continue
            current_name = key
            upsert(key, value)
            continue

        m = dash_line.match(line)
        if m:
            key, value = m.group(1).strip(" ."), m.group(2)
            if canonical(key) in {canonical(x) for x in NON_FEATURE_KEYS}:
                continue
            current_name = key
            upsert(key, value)
            continue

        # Standalone heading followed by Description line.
        if i + 1 < len(lines) and desc_line.match(lines[i + 1]) and is_valid_feature_name(line):
            current_name = line
            upsert(current_name, "")

    if feats:
        return feats

    # Fallback: detect "functionalities are ..." style lists.
    m = re.search(
        r"(?:major|main|key|various)?\s*functionalities(?:\s+are|\s+include|:)\s+(.+?)(?:\.\s|$)",
        raw_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return feats
    items = [x.strip(" .") for x in re.split(r",| and ", re.sub(r"\s+", " ", m.group(1)).strip()) if x.strip(" .")]
    for item in items:
        if is_valid_feature_name(item):
            feats.append({"name": item, "description": ""})
    return feats


def extract_labeled_lists(raw_text: str) -> dict[str, list[str]]:
    buckets = {"preconditions": [], "postconditions": [], "triggers": [], "constraints": []}
    lines = [ln.strip() for ln in merge_wrapped_lines(raw_text)]
    active_label = ""
    active_text = ""

    def map_label(label: str) -> str:
        key = canonical(label)
        if key.startswith("pre condition"):
            return "preconditions"
        if key.startswith("post condition"):
            return "postconditions"
        if key.startswith("constraint"):
            return "constraints"
        return "triggers"

    def flush() -> None:
        nonlocal active_label, active_text
        if not active_label:
            return
        text = clean_clause(active_text)
        if text:
            buckets[active_label].append(ensure_period(text))
        active_label = ""
        active_text = ""

    for line in lines:
        if not line:
            flush()
            continue
        m = LABEL_HEADER_RE.match(line)
        if m:
            flush()
            active_label = map_label(m.group(1))
            active_text = m.group(2).strip()
            continue
        if active_label:
            if re.match(r"^\d+[.)]?\s+[A-Za-z]", line):
                flush()
                continue
            if re.match(r"^\s*(description|flow of events)\b", line, re.IGNORECASE):
                flush()
                continue
            active_text = f"{active_text} {line}".strip()
    flush()
    return {k: dedupe_keep_order(v) for k, v in buckets.items()}


def summarize(raw_text: str) -> str:
    sentences = [s for s in sentence_split(raw_text) if "figure" not in s.lower()]
    if not sentences:
        return ""
    return " ".join(sentences[:3]).strip()


def extract_rationale(raw_text: str) -> str:
    for sent in sentence_split(raw_text):
        low = sent.lower()
        if any(k in low for k in ("aim", "objective", "purpose", "designed", "to help", "to provide")):
            return sent
    sentences = sentence_split(raw_text)
    return sentences[1] if len(sentences) > 1 else (sentences[0] if sentences else "")


def format_shall(name: str, description: str) -> str:
    desc = clean_clause(description)
    if not desc:
        desc = clean_clause(name)
    verb_map = {
        "views": "view",
        "updates": "update",
        "creates": "create",
        "validates": "validate",
        "calculates": "calculate",
        "generates": "generate",
        "notifies": "notify",
        "allows": "allow",
        "enables": "enable",
        "supports": "support",
        "replaces": "replace",
        "removes": "remove",
        "searches": "search",
        "places": "place",
        "issues": "issue",
        "collects": "collect",
        "cancels": "cancel",
        "registers": "register",
        "authenticates": "authenticate",
        "logs": "log",
    }
    lower_desc = desc.lower()
    for inflected, base in verb_map.items():
        if lower_desc.startswith(inflected + " "):
            desc = base + desc[len(inflected):]
            break
    if desc and desc[0].isupper():
        first = desc.split(" ", 1)[0]
        if not first.isupper():
            desc = desc[0].lower() + desc[1:]
    low = desc.lower()
    if low.startswith("the system shall"):
        return ensure_period(desc)
    if re.match(r"^(allow|allows|enable|enables|support|supports|generate|generates|calculate|calculates|notify|notifies|validate|validates|track|tracks|provide|provides|create|creates|store|stores|update|updates|remove|removes|replace|replaces|search|searches|place|places|issue|issues|view|views|collect|collects|cancel|cancels|register|registers|login|log in|log|logs|authenticate|authenticates)\b", low):
        return ensure_period(f"The system shall {desc}")
    if re.match(r"^(user|users|admin|administrator|customer|customers|patient|patients|seller|sellers|student|students|citizen|citizens|driver|drivers|inventory manager|inventory managers|salesperson|salespersons)\b", low):
        return ensure_period(f"The system shall allow {desc}")
    if re.search(r"\b(users?|customers?|patients?|sellers?|citizens?|drivers?|students?)\s+to\b", low):
        return ensure_period(f"The system shall allow {desc}")
    if re.match(r"^[a-z]+ing\b", low):
        return ensure_period(f"The system shall allow {desc}")
    return ensure_period(f"The system shall support {desc}")


def clean_behavior_items(items: list[str]) -> list[str]:
    out = []
    for item in items:
        s = clean_clause(item)
        if not s:
            continue
        low = s.lower()
        if "description:" in low or "flow of events" in low:
            continue
        if len(s) < 6:
            continue
        out.append(ensure_period(s))
    return dedupe_keep_order(out)


def build_polished_text(case_dir: Path) -> str:
    raw_path = case_dir / "raw_requirement.txt"
    raw_text = normalize_ws(raw_path.read_text(encoding="utf-8"))
    title = case_title(case_dir.name)
    summary = summarize(raw_text)
    rationale = extract_rationale(raw_text)
    actors = extract_actors(raw_text)
    features = extract_features(raw_text)
    labels = extract_labeled_lists(raw_text)

    lines: list[str] = []
    lines.append(f"{title} — Polished Requirement Specification")
    lines.append("")
    lines.append("Overview")
    lines.append(ensure_period(summary))
    if rationale and canonical(rationale) not in canonical(summary):
        lines.append(ensure_period(rationale))
    lines.append("")

    lines.append("Operational Context")
    if actors:
        lines.append(f"Primary actors include {', '.join(actors)}.")
    else:
        lines.append("Primary actors are not explicitly stated in the source text.")
    lines.append("")

    lines.append("Functional Requirements")
    reqs: list[str] = []
    for feat in features:
        reqs.append(format_shall(feat["name"], feat["description"]))

    if not reqs:
        for sent in sentence_split(raw_text):
            low = sent.lower()
            if any(k in low for k in ("allow", "enable", "support", "generate", "calculate", "notify", "update", "manage", "monitor", "track")):
                reqs.append(format_shall("", sent))
            if len(reqs) >= 10:
                break

    reqs = dedupe_keep_order(reqs)
    if not reqs:
        reqs = ["The system shall provide the capabilities described in the source requirement text."]
    for idx, req in enumerate(reqs, start=1):
        lines.append(f"{idx}. {req}")
    lines.append("")

    pre = clean_behavior_items(labels["preconditions"])
    post = clean_behavior_items(labels["postconditions"])
    trig = clean_behavior_items(labels["triggers"])
    cons = clean_behavior_items(labels["constraints"])
    if pre or post or trig or cons:
        lines.append("Behavioral Conditions")
        if pre:
            lines.append("Preconditions:")
            for item in pre:
                lines.append(f"- {item}")
        if post:
            lines.append("Postconditions:")
            for item in post:
                lines.append(f"- {item}")
        if trig:
            lines.append("Triggers:")
            for item in trig[:8]:
                lines.append(f"- {item}")
        if cons:
            lines.append("Constraints:")
            for item in cons[:8]:
                lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rewrite raw requirements into polished natural-language requirements."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root containing case_* folders",
    )
    parser.add_argument(
        "--output-name",
        default="structured_requirement.txt",
        help="Output file name in each case folder",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    args = parser.parse_args()

    case_dirs = sorted([p for p in args.dataset_root.glob("case_*") if p.is_dir()], key=lambda p: p.name)
    if not case_dirs:
        raise RuntimeError(f"No case_* folders found in {args.dataset_root}")

    written = 0
    skipped = 0
    for case_dir in case_dirs:
        raw_path = case_dir / "raw_requirement.txt"
        if not raw_path.exists():
            print(f"[skip] {case_dir.name}: missing raw_requirement.txt")
            skipped += 1
            continue
        out_path = case_dir / args.output_name
        if out_path.exists() and not args.overwrite:
            print(f"[skip] {case_dir.name}: {args.output_name} exists (use --overwrite)")
            skipped += 1
            continue
        out_path.write_text(build_polished_text(case_dir), encoding="utf-8")
        print(f"[ok] {case_dir.name} -> {out_path.name}")
        written += 1

    print(f"Done. written={written}, skipped={skipped}")


if __name__ == "__main__":
    main()
