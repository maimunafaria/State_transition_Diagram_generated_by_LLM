#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from plantuml_pipeline.dataset import load_cases
from plantuml_pipeline.model_client import call_model
from plantuml_pipeline.parser import normalize_puml_text


CRITERIA = [
    "completeness",
    "correctness",
    "understandability",
    "terminological_alignment",
]


def build_judge_prompt(requirement: str, puml: str) -> str:
    return (
        "You are an expert evaluator of PlantUML state transition diagrams.\n"
        "Evaluate the candidate diagram against the requirement using exactly the same rubric a human evaluator used.\n"
        "Do not repair the diagram. Do not generate new PlantUML. Only judge the given diagram.\n\n"
        "Evaluation criteria:\n"
        "1. Completeness: All required states, transitions, events, guards, initial and final states are present.\n"
        "2. Correctness: The diagram's behavior logically matches the requirement, with no contradictions.\n"
        "3. Understandability: The diagram is clear, readable, and not unnecessarily complex or redundant.\n"
        "4. Terminological alignment: State names and transition labels use the exact same terms as the requirement text.\n\n"
        "Likert scale:\n"
        "1 = Not fulfilled at all\n"
        "2 = Fulfilled to a minimal extent\n"
        "3 = Partially fulfilled\n"
        "4 = Mainly fulfilled\n"
        "5 = Completely fulfilled\n\n"
        "For every score below 5, provide a short one-line justification.\n"
        "If the score is 5, write \"Fully fulfilled.\" as the justification.\n\n"
        "Return ONLY valid JSON in this exact schema:\n"
        "{\n"
        "  \"completeness\": {\"score\": 1, \"justification\": \"...\"},\n"
        "  \"correctness\": {\"score\": 1, \"justification\": \"...\"},\n"
        "  \"understandability\": {\"score\": 1, \"justification\": \"...\"},\n"
        "  \"terminological_alignment\": {\"score\": 1, \"justification\": \"...\"}\n"
        "}\n\n"
        "Requirement text:\n"
        f"{requirement}\n\n"
        "Candidate PlantUML:\n"
        f"{puml}\n"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return json.loads(stripped[start : end + 1])
    raise ValueError(f"No JSON object found in response: {text[:500]}")


def normalize_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(1, min(5, score))


def normalize_judgement(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for criterion in CRITERIA:
        item = payload.get(criterion) or {}
        if not isinstance(item, dict):
            item = {}
        normalized[criterion] = {
            "score": normalize_score(item.get("score")),
            "justification": str(item.get("justification") or "").strip(),
        }
    return normalized


def iter_puml_files(runs_root: Path, run_id: str, case_id: str) -> list[Path]:
    run_dir = runs_root / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run folder not found: {run_dir}")
    if case_id:
        puml = run_dir / case_id / "run_01.puml"
        if not puml.exists():
            raise FileNotFoundError(f"PlantUML file not found: {puml}")
        return [puml]
    return sorted(run_dir.glob("case_*/run_01.puml"))


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "case_id",
        "puml_path",
        "completeness_score",
        "completeness_justification",
        "correctness_score",
        "correctness_justification",
        "understandability_score",
        "understandability_justification",
        "terminological_alignment_score",
        "terminological_alignment_justification",
        "mean_score",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge PlantUML diagrams with DeepSeek using a human-style rubric.")
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument("--runs-root", type=Path, default=Path("results/plantuml_pipeline/runs"))
    parser.add_argument("--run-id", required=True, help="Run folder to judge.")
    parser.add_argument("--case-id", default="", help="Optional single case_id to judge.")
    parser.add_argument("--model", default="deepseek-r1:14b")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("results/plantuml_pipeline/llm_judge/deepseek_judgements.jsonl"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/plantuml_pipeline/llm_judge/deepseek_judgements.csv"),
    )
    parser.add_argument("--save-prompts-dir", type=Path, default=Path(""))
    args = parser.parse_args()

    cases = {case.case_id: case for case in load_cases(args.dataset_root)}
    puml_files = iter_puml_files(args.runs_root, args.run_id, args.case_id)
    if not puml_files:
        raise FileNotFoundError(f"No run_01.puml files found for {args.run_id}")

    rows: list[dict[str, Any]] = []
    json_rows: list[dict[str, Any]] = []

    for puml_path in puml_files:
        case_id = puml_path.parent.name
        case = cases.get(case_id)
        if case is None:
            print(f"Skipping unknown case: {case_id}")
            continue
        requirement = case.structured_requirement or case.raw_requirement
        puml = normalize_puml_text(puml_path.read_text(encoding="utf-8", errors="replace"))
        prompt = build_judge_prompt(requirement, puml)

        if args.save_prompts_dir:
            prompt_dir = args.save_prompts_dir / args.run_id / case_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "judge_prompt.txt").write_text(prompt, encoding="utf-8")

        response = call_model(
            model_name=args.model,
            prompt=prompt,
            ollama_host=args.ollama_host,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
        )
        try:
            judgement = normalize_judgement(extract_json_object(response))
            error_message = ""
        except Exception as exc:  # noqa: BLE001
            judgement = {criterion: {"score": 0, "justification": ""} for criterion in CRITERIA}
            error_message = str(exc)

        scores = [judgement[criterion]["score"] for criterion in CRITERIA]
        mean_score = round(sum(scores) / len(scores), 3) if all(scores) else 0.0
        row = {
            "run_id": args.run_id,
            "case_id": case_id,
            "puml_path": str(puml_path),
            "mean_score": mean_score,
        }
        for criterion in CRITERIA:
            row[f"{criterion}_score"] = judgement[criterion]["score"]
            row[f"{criterion}_justification"] = judgement[criterion]["justification"]
        rows.append(row)
        json_rows.append(
            {
                "run_id": args.run_id,
                "case_id": case_id,
                "puml_path": str(puml_path),
                "judgement": judgement,
                "mean_score": mean_score,
                "raw_response": response,
                "error_message": error_message,
            }
        )
        print(
            f"{case_id}: mean={mean_score} "
            f"C={judgement['completeness']['score']} "
            f"K={judgement['correctness']['score']} "
            f"U={judgement['understandability']['score']} "
            f"T={judgement['terminological_alignment']['score']}"
        )

    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.output_jsonl.open("w", encoding="utf-8") as handle:
        for item in json_rows:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_csv(rows, args.output_csv)
    print(f"\nJSONL written to: {args.output_jsonl}")
    print(f"CSV written to: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
