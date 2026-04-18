#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from plantuml_pipeline.model_client import call_model


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"


def normalize_ws(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("\u200b", " ")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def build_prompt(case_name: str, raw_text: str, diagram_text: str) -> str:
    raw_section = raw_text if raw_text else "[raw requirement text is empty or missing]"
    diagram_section = diagram_text if diagram_text else "[diagram text is missing]"
    return f"""
You are a requirements analyst.
Rewrite the requirement into a clear natural-language description by analyzing BOTH:
1) raw requirement text
2) the corresponding UML state diagram (PlantUML)

Rules:
1. Prefer diagram behavior as the primary source of states, transitions, triggers, and actions.
2. Use raw text to preserve domain context and constraints when present.
3. Do not invent functionality not supported by either source.
4. If either source is incomplete or inconsistent, explicitly mention that limitation in the prose.
5. Output plain prose only (no bullets, no headings, no JSON).
6. Keep the output concise and readable for an engineering dataset.

Case:
<<<
{case_name}
>>>

Raw requirement text:
<<<
{raw_section}
>>>

PlantUML state diagram:
<<<
{diagram_section}
>>>
""".strip()


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


def process_case(
    case_dir: Path,
    output_name: str,
    overwrite: bool,
    model: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    raw_path = case_dir / "raw_requirement.txt"
    diagram_path = case_dir / "diagram.puml"
    out_path = case_dir / output_name

    if not raw_path.exists():
        return "skip_missing_raw"
    if out_path.exists() and not overwrite:
        return "skip_exists"

    raw_text = normalize_ws(raw_path.read_text(encoding="utf-8"))
    diagram_text = ""
    if diagram_path.exists():
        diagram_text = normalize_ws(diagram_path.read_text(encoding="utf-8"))

    if not raw_text and not diagram_text:
        out_path.write_text("", encoding="utf-8")
        return "ok_empty"

    prompt = build_prompt(case_dir.name, raw_text, diagram_text)
    rewritten = call_model(
        model_name=model,
        prompt=prompt,
        ollama_host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    rewritten = normalize_ws(strip_fences(rewritten))

    if not rewritten:
        rewritten = raw_text if raw_text else "The requirement sources are empty or unavailable."

    out_path.write_text(rewritten + "\n", encoding="utf-8")
    return "ok"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rewrite raw_requirement.txt into raw_requirement_changed.txt for selected case range."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--start-case", type=int, default=47)
    parser.add_argument("--end-case", type=int, default=72)
    parser.add_argument("--output-name", default="raw_requirement_changed.txt")
    parser.add_argument("--model", default="qwen2.5:7b-instruct")
    parser.add_argument("--ollama-host", default="http://127.0.0.1:11434")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=1600)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    case_dirs = find_case_dirs(args.dataset_root, args.start_case, args.end_case)
    if not case_dirs:
        raise RuntimeError(
            f"No case folders found in range case_{args.start_case:02d} to case_{args.end_case:02d}."
        )

    print(
        f"Rewriting {len(case_dirs)} cases "
        f"(range {args.start_case}-{args.end_case}) with model={args.model}"
    )

    counts = {"ok": 0, "ok_empty": 0, "skip_exists": 0, "skip_missing_raw": 0, "error": 0}
    for case_dir in case_dirs:
        try:
            status = process_case(
                case_dir=case_dir,
                output_name=args.output_name,
                overwrite=args.overwrite,
                model=args.model,
                ollama_host=args.ollama_host,
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
            )
        except Exception as exc:
            status = "error"
            print(f"[error] {case_dir.name}: {exc}")

        counts[status] = counts.get(status, 0) + 1
        if status != "error":
            print(f"[{status}] {case_dir.name}")

    print("Done.")
    for key in ["ok", "ok_empty", "skip_exists", "skip_missing_raw", "error"]:
        print(f"{key}={counts.get(key, 0)}")


if __name__ == "__main__":
    main()
