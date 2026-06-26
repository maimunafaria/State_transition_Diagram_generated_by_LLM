#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from judge_plantuml_deepseek import (
    CRITERIA,
    build_judge_prompt,
    extract_json_object,
    normalize_judgement,
)
from plantuml_pipeline.model_client import call_model
from plantuml_pipeline.parser import normalize_puml_text


CSV_FIELDS = [
    "llm_name",
    "case_name",
    "method_name",
    "completeness_score",
    "correctness_score",
    "understandability_score",
    "terminological_alignment_score",
    "completeness_justification",
    "correctness_justification",
    "understandability_justification",
    "terminological_alignment_justification",
]


def anonymous_id(llm_name: str, method_name: str, case_name: str) -> str:
    value = f"{llm_name}|{method_name}|{case_name}".encode("utf-8")
    return f"diagram_{hashlib.sha256(value).hexdigest()[:12]}"


def discover_diagrams(root: Path) -> list[dict[str, Any]]:
    diagrams: list[dict[str, Any]] = []
    for puml_path in sorted(root.glob("*/*/case_*/diagram.puml")):
        case_dir = puml_path.parent
        method_dir = case_dir.parent
        llm_dir = method_dir.parent
        requirement_path = case_dir / "requirement.txt"
        if not requirement_path.exists():
            raise FileNotFoundError(f"Requirement file not found: {requirement_path}")
        diagrams.append(
            {
                "llm_name": llm_dir.name,
                "method_name": method_dir.name,
                "case_name": case_dir.name,
                "requirement_path": requirement_path,
                "puml_path": puml_path,
                "anonymous_id": anonymous_id(llm_dir.name, method_dir.name, case_dir.name),
            }
        )
    return diagrams


def load_completed_keys(output_path: Path) -> set[tuple[str, str, str]]:
    if not output_path.exists():
        return set()
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        return {
            (row["llm_name"], row["method_name"], row["case_name"])
            for row in csv.DictReader(handle)
        }


def append_csv_row(output_path: Path, row: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_path.exists() or output_path.stat().st_size == 0
    with output_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def append_jsonl_row(output_path: Path, row: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Blindly judge strict-valid diagrams with DeepSeek and write one comparison CSV."
    )
    parser.add_argument("--valid-diagrams-root", type=Path, default=Path("valid_diagrams"))
    parser.add_argument("--model", default="deepseek-r1:14b")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20260627)
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("results/plantuml_pipeline/llm_judge/deepseek_valid_diagram_judgements.csv"),
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=Path("results/plantuml_pipeline/llm_judge/deepseek_valid_diagram_raw.jsonl"),
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete existing output files instead of resuming.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of new diagrams to judge; 0 means all.",
    )
    args = parser.parse_args()

    if not args.valid_diagrams_root.exists():
        raise FileNotFoundError(f"Folder not found: {args.valid_diagrams_root}")
    if args.fresh:
        args.output_csv.unlink(missing_ok=True)
        args.output_jsonl.unlink(missing_ok=True)

    diagrams = discover_diagrams(args.valid_diagrams_root)
    if not diagrams:
        raise FileNotFoundError(f"No diagram.puml files found under {args.valid_diagrams_root}")

    random.Random(args.seed).shuffle(diagrams)
    completed = load_completed_keys(args.output_csv)
    pending = [
        diagram
        for diagram in diagrams
        if (
            diagram["llm_name"],
            diagram["method_name"],
            diagram["case_name"],
        )
        not in completed
    ]
    if args.limit > 0:
        pending = pending[: args.limit]

    print(
        f"Discovered {len(diagrams)} diagrams; "
        f"already completed {len(completed)}; judging {len(pending)}."
    )

    for index, diagram in enumerate(pending, start=1):
        requirement = diagram["requirement_path"].read_text(
            encoding="utf-8", errors="replace"
        )
        puml = normalize_puml_text(
            diagram["puml_path"].read_text(encoding="utf-8", errors="replace")
        )

        # The prompt intentionally contains no model, method, case, path, or source-run metadata.
        prompt = build_judge_prompt(requirement, puml)
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
            judgement = {
                criterion: {"score": 0, "justification": f"Judge response error: {exc}"}
                for criterion in CRITERIA
            }
            error_message = str(exc)

        csv_row: dict[str, Any] = {
            "llm_name": diagram["llm_name"],
            "case_name": diagram["case_name"],
            "method_name": diagram["method_name"],
        }
        for criterion in CRITERIA:
            csv_row[f"{criterion}_score"] = judgement[criterion]["score"]
            csv_row[f"{criterion}_justification"] = judgement[criterion][
                "justification"
            ]
        append_csv_row(args.output_csv, csv_row)

        append_jsonl_row(
            args.output_jsonl,
            {
                "anonymous_id": diagram["anonymous_id"],
                "llm_name": diagram["llm_name"],
                "case_name": diagram["case_name"],
                "method_name": diagram["method_name"],
                "judgement": judgement,
                "raw_response": response,
                "error_message": error_message,
            },
        )
        scores = "/".join(
            str(judgement[criterion]["score"]) for criterion in CRITERIA
        )
        print(f"[{index}/{len(pending)}] {diagram['anonymous_id']}: {scores}")

    print(f"\nCSV written to: {args.output_csv}")
    print(f"Raw audit JSONL written to: {args.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
