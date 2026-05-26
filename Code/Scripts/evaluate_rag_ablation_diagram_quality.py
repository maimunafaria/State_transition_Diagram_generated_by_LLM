#!/usr/bin/env python3
"""Rate valid RAG-ablation diagrams against their requirements.

The output is intended as a first-pass human-evaluation sheet. It uses the
stored PlantUML source, requirement text, and simple transparent heuristics so
the ratings can be reviewed or adjusted manually.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path("results/plantuml_pipeline/valid_diagrams_by_case_rag_ablation")
OUT_CSV = ROOT / "rag_ablation_diagram_quality_ratings.csv"
OUT_MD = ROOT / "rag_ablation_diagram_quality_ratings.md"

STOPWORDS = {
    "a",
    "about",
    "access",
    "after",
    "all",
    "allow",
    "allows",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "complete",
    "do",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "shall",
    "system",
    "the",
    "their",
    "to",
    "user",
    "users",
    "when",
    "with",
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]+", text.lower())
    normalized: list[str] = []
    for word in words:
        if word in STOPWORDS or len(word) <= 2:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > 5 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        normalized.append(word)
    return normalized


def parse_requirements(text: str) -> list[str]:
    requirements = []
    for line in text.splitlines():
        match = re.match(r"^\s*\d+\.\s+(.+?)\s*$", line)
        if match:
            requirements.append(match.group(1))
    return requirements


def score_from_ratio(ratio: float) -> int:
    if ratio >= 0.90:
        return 5
    if ratio >= 0.75:
        return 4
    if ratio >= 0.55:
        return 3
    if ratio >= 0.35:
        return 2
    return 1


def clamp_score(value: int) -> int:
    return max(1, min(5, value))


def coverage_comment(score: int, covered: int, total: int, weak: int) -> str:
    if score == 5:
        return "The diagram represents the required behavior very well and includes almost all of the expected states/actions."
    if score == 4:
        return "The diagram covers the main behavior, but one or two supporting requirements are only partially represented."
    if score == 3:
        return "The diagram captures the central workflow, but several requirements are missing or only indirectly shown."
    if score == 2:
        return "The diagram includes only part of the required behavior, so important functions from the requirement text are not clearly modeled."
    return "The diagram does not cover the requirement set well; most required behavior is missing from the modeled flow."


def correctness_comment(
    score: int,
    transitions: int,
    has_initial: bool,
    has_final: bool,
    guarded_transitions: int,
    branch_cues: int,
) -> str:
    if score >= 5:
        return "The flow is logically organized, with a clear start, end, and connected transitions between states."
    issues = []
    if not has_initial:
        issues.append("the starting point is not clearly modeled")
    if not has_final:
        issues.append("the ending point is not clearly modeled")
    if branch_cues >= 2 and guarded_transitions == 0:
        issues.append("decision paths from the requirements are not clearly guarded")
    if transitions < 3:
        issues.append("the flow has very few transitions")
    if not issues:
        issues.append("some required behavior is not connected strongly enough to the main workflow")
    if score == 4:
        return "The flow is mostly correct, but " + "; ".join(issues[:2]) + "."
    if score == 3:
        return "The diagram is understandable as a flow, but " + "; ".join(issues[:2]) + "."
    if score == 2:
        return "The logical flow is weak because " + "; ".join(issues[:3]) + "."
    return "The diagram has major logical-flow problems because " + "; ".join(issues[:3]) + "."


def understandability_comment(score: int, states: int, terse_nodes: int, very_long_lines: int) -> str:
    if score == 5:
        return "The diagram is easy to read because the state names are clear and the workflow is not visually overloaded."
    issues = []
    if states > 22:
        issues.append("there are many states")
    if terse_nodes >= 3:
        issues.append("some connector labels are too abbreviated")
    if very_long_lines >= 3:
        issues.append("some labels are too long")
    if not issues:
        issues.append("some parts of the flow require extra effort to follow")
    if score == 4:
        return "The diagram is mostly understandable, although " + "; ".join(issues[:2]) + "."
    if score == 3:
        return "The diagram can be followed, but " + "; ".join(issues[:2]) + " make it less clear."
    if score == 2:
        return "The diagram is difficult to understand because " + "; ".join(issues[:3]) + "."
    return "The diagram is very hard to understand because " + "; ".join(issues[:3]) + "."


def terminology_comment(score: int) -> str:
    if score == 5:
        return "The diagram uses terminology that closely matches the requirement text, so the states are easy to relate back to the specification."
    if score == 4:
        return "The terminology is mostly aligned with the requirement text, with only minor wording differences."
    if score == 3:
        return "The terminology is partially aligned, but several state names use different wording from the requirement text."
    if score == 2:
        return "The terminology alignment is weak because many diagram labels do not clearly match the requirement wording."
    return "The terminology does not align well with the requirement text, making it difficult to connect the diagram back to the specification."


def read_manifest() -> dict[tuple[str, str], dict[str, str]]:
    manifest: dict[tuple[str, str], dict[str, str]] = {}
    with (ROOT / "manifest.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            manifest[(row["case_id"], row["label"])] = row
    return manifest


def split_model_method(label: str) -> tuple[str, str]:
    parts = label.split("__")
    model = parts[0] if parts else label
    method = "__".join(parts[1:]) if len(parts) > 1 else ""
    return model, method


def puml_body_text(puml: str) -> str:
    text = re.sub(r"@startuml|@enduml|title\s+.*", " ", puml, flags=re.IGNORECASE)
    text = re.sub(r"['\"{}\[\]():;/_\-]+", " ", text)
    text = re.sub(r"\bstate\b|\bas\b|\bentry\b|\bexit\b|\bdo\b", " ", text, flags=re.IGNORECASE)
    return text


def count_states(puml: str) -> int:
    named = re.findall(r"^\s*state\s+", puml, flags=re.MULTILINE)
    transition_names = set()
    for left, right in re.findall(r"^\s*([^\n:]+?)\s*-->\s*([^\n:]+)", puml, flags=re.MULTILINE):
        for side in (left, right):
            side = re.sub(r"\[\*\]|\[.+?\]|:.*", "", side).strip().strip('"')
            if side:
                transition_names.add(side)
    return max(len(named), len(transition_names))


def evaluate_one(case_id: str, label: str, png_path: Path, source_puml: Path) -> dict[str, str | int]:
    req_path = png_path.parent / "structured_requirement.txt"
    requirements = parse_requirements(req_path.read_text(encoding="utf-8"))
    puml = source_puml.read_text(encoding="utf-8", errors="replace")
    diagram_text = puml_body_text(puml)

    diagram_tokens = set(tokenize(diagram_text))
    requirement_token_sets = [set(tokenize(req)) for req in requirements]
    covered = 0
    weak = 0
    for req_tokens in requirement_token_sets:
        if not req_tokens:
            continue
        overlap = len(req_tokens & diagram_tokens)
        ratio = overlap / len(req_tokens)
        if ratio >= 0.25 or overlap >= 3:
            covered += 1
        elif overlap > 0:
            weak += 1

    req_count = len(requirements)
    coverage_ratio = covered / req_count if req_count else 0.0
    completeness = score_from_ratio(coverage_ratio)

    all_req_tokens = set().union(*requirement_token_sets) if requirement_token_sets else set()
    terminology_ratio = len(all_req_tokens & diagram_tokens) / len(all_req_tokens) if all_req_tokens else 0.0
    if terminology_ratio >= 0.62:
        terminology = 5
    elif terminology_ratio >= 0.48:
        terminology = 4
    elif terminology_ratio >= 0.34:
        terminology = 3
    elif terminology_ratio >= 0.20:
        terminology = 2
    else:
        terminology = 1

    transitions = len(re.findall(r"-->", puml))
    has_initial = bool(re.search(r"\[\*\]\s*-->", puml))
    has_final = bool(re.search(r"-->\s*\[\*\]", puml))
    guarded_transitions = len(re.findall(r"-->[^\n]*\[[^\]]+\]", puml))
    branch_cues = len(re.findall(r"\b(if|choose|choice|either|fail|failed|valid|invalid|available|not available)\b", " ".join(requirements), flags=re.IGNORECASE))

    correctness = 5
    if not has_initial:
        correctness -= 1
    if not has_final:
        correctness -= 1
    if transitions < max(3, req_count // 2):
        correctness -= 1
    if completeness <= 2:
        correctness -= 2
    elif completeness == 3:
        correctness -= 1
    if branch_cues >= 2 and guarded_transitions == 0:
        correctness -= 1
    correctness = clamp_score(correctness)

    states = count_states(puml)
    terse_nodes = len(re.findall(r"\b[JLFRC]\d+\b", puml))
    very_long_lines = sum(1 for line in puml.splitlines() if len(line) > 120)
    understandability = 5
    if states > 22:
        understandability -= 1
    if states > 35:
        understandability -= 1
    if terse_nodes >= 3:
        understandability -= 1
    if very_long_lines >= 3:
        understandability -= 1
    if transitions < 2:
        understandability -= 1
    understandability = clamp_score(understandability)

    model, method = split_model_method(label)
    return {
        "case_id": case_id,
        "diagram_file": png_path.name,
        "model": model,
        "rag_ablation": method,
        "completeness": completeness,
        "correctness": correctness,
        "understandability": understandability,
        "terminology_alignment": terminology,
        "requirements_covered": covered,
        "requirements_total": req_count,
        "coverage_percent": round(coverage_ratio * 100, 1),
        "terminology_overlap_percent": round(terminology_ratio * 100, 1),
        "justification_completeness": (
            f"{coverage_comment(completeness, covered, req_count, weak)} "
            f"It covers {covered} out of {req_count} requirements."
        ),
        "justification_correctness": correctness_comment(
            correctness,
            transitions,
            has_initial,
            has_final,
            guarded_transitions,
            branch_cues,
        ),
        "justification_understandability": understandability_comment(
            understandability,
            states,
            terse_nodes,
            very_long_lines,
        ),
        "justification_terminology": terminology_comment(terminology),
        "source_puml": str(source_puml),
    }


def main() -> None:
    manifest = read_manifest()
    rows: list[dict[str, str | int]] = []
    for png_path in sorted(ROOT.glob("case_*/*.png")):
        if png_path.name == "original_diagram.png":
            continue
        case_id = png_path.parent.name
        label = png_path.stem.removesuffix("__run_01")
        source = manifest.get((case_id, label), {}).get("source_puml", "")
        if not source:
            raise SystemExit(f"Could not find source_puml for {case_id}/{png_path.name}")
        rows.append(evaluate_one(case_id, label, png_path, Path(source)))

    fieldnames = list(rows[0].keys()) if rows else []
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with OUT_MD.open("w", encoding="utf-8") as fh:
        fh.write("# RAG Ablation Diagram Quality Ratings\n\n")
        fh.write("Scale: 1 = poor, 2 = weak, 3 = acceptable, 4 = good, 5 = excellent.\n\n")
        fh.write("| Case | Diagram | Completeness | Correctness | Understandability | Terminology | Short justification |\n")
        fh.write("|---|---|---:|---:|---:|---:|---|\n")
        for row in rows:
            short = (
                f"{row['requirements_covered']}/{row['requirements_total']} requirements covered; "
                f"{row['coverage_percent']}% coverage, {row['terminology_overlap_percent']}% term overlap."
            )
            fh.write(
                f"| {row['case_id']} | {row['diagram_file']} | {row['completeness']} | "
                f"{row['correctness']} | {row['understandability']} | "
                f"{row['terminology_alignment']} | {short} |\n"
            )

    print(f"rated_diagrams={len(rows)}")
    print(f"csv={OUT_CSV}")
    print(f"markdown={OUT_MD}")


if __name__ == "__main__":
    main()
