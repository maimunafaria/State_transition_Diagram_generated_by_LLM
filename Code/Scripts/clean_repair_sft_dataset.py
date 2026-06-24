from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


INITIAL_RE = re.compile(r"\[\*\]\s*-->\s*(?!\[\*\])", re.IGNORECASE)
FINAL_RE = re.compile(r"(?!\[\*\])\b[\w\" ].*?-->\s*\[\*\]", re.IGNORECASE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def norm_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def text_hash(text: str) -> str:
    return hashlib.sha256(norm_text(text).encode("utf-8")).hexdigest()


def is_tiny_or_empty_puml(output: str, min_output_chars: int) -> bool:
    stripped = output.strip()
    body = re.sub(r"@startuml|@enduml", "", stripped, flags=re.IGNORECASE).strip()
    if len(stripped) < min_output_chars:
        return True
    if not body:
        return True
    non_comment_lines = [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("'")
    ]
    return len(non_comment_lines) < 3


def rejection_reasons(row: dict[str, Any], min_output_chars: int) -> list[str]:
    reasons: list[str] = []
    output = str(row.get("output", ""))
    metadata = row.get("metadata") or {}

    if metadata.get("remaining_violations_after_repair"):
        reasons.append("remaining_violations")
    if is_tiny_or_empty_puml(output, min_output_chars):
        reasons.append("tiny_output")
    if "@startuml" not in output.lower() or "@enduml" not in output.lower():
        reasons.append("missing_plantuml_wrapper")
    if not INITIAL_RE.search(output):
        reasons.append("missing_initial_transition")
    if not FINAL_RE.search(output):
        reasons.append("missing_final_transition")
    return reasons


def clean_rows(rows: list[dict[str, Any]], min_output_chars: int) -> tuple[list[dict[str, Any]], Counter[str]]:
    rejection_counts: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []

    for row in rows:
        reasons = rejection_reasons(row, min_output_chars)
        if reasons:
            rejection_counts.update(reasons)
            continue
        candidates.append(row)

    # Exact duplicate removal.
    exact_seen: set[tuple[str, str]] = set()
    exact_unique: list[dict[str, Any]] = []
    for row in candidates:
        key = (text_hash(str(row.get("input", ""))), text_hash(str(row.get("output", ""))))
        if key in exact_seen:
            rejection_counts["exact_duplicate"] += 1
            continue
        exact_seen.add(key)
        exact_unique.append(row)

    # Same input with multiple different outputs is a conflict. Keep only inputs with one output.
    outputs_by_input: dict[str, set[str]] = defaultdict(set)
    for row in exact_unique:
        outputs_by_input[text_hash(str(row.get("input", "")))].add(text_hash(str(row.get("output", ""))))

    cleaned: list[dict[str, Any]] = []
    for row in exact_unique:
        input_key = text_hash(str(row.get("input", "")))
        if len(outputs_by_input[input_key]) > 1:
            rejection_counts["conflicting_output_for_same_input"] += 1
            continue
        cleaned.append(row)

    return cleaned, rejection_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean PlantUML repair SFT JSONL data.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-output-chars", type=int, default=150)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    cleaned, rejection_counts = clean_rows(rows, args.min_output_chars)
    write_jsonl(args.output, cleaned)

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "total_rows": len(rows),
        "kept_rows": len(cleaned),
        "removed_rows": len(rows) - len(cleaned),
        "min_output_chars": args.min_output_chars,
        "rejection_counts": dict(sorted(rejection_counts.items())),
    }

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
