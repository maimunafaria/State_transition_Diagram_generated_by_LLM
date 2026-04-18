#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import hybrid_requirement_pipeline as hrp


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"

CHANGED_PLAIN_RE = re.compile(r"^(?:raw_requirement|aw_requirement)_changed\.txt$")
CHANGED_INDEXED_RE = re.compile(r"^(?:raw_requirement|aw_requirement)_(\d+)_changed\.txt$")


def discover_changed_files(case_dir: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for p in sorted(case_dir.glob("*requirement*changed*.txt")):
        name = p.name
        if CHANGED_PLAIN_RE.match(name):
            found.append((p, ""))
            continue
        m = CHANGED_INDEXED_RE.match(name)
        if m:
            found.append((p, m.group(1)))
    found.sort(key=lambda x: (0 if x[1] == "" else 1, int(x[1]) if x[1].isdigit() else 0, x[0].name))
    return found


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


def build_output_paths(case_dir: Path, suffix: str) -> dict[str, Path]:
    tag = f"_{suffix}" if suffix else ""
    return {
        "structured": case_dir / (f"structured_requirement{tag}.txt" if tag else "structured_requirement.txt"),
        "extracted": case_dir / (f"functional_requirements_extracted{tag}.json" if tag else "functional_requirements_extracted.json"),
        "rewritten": case_dir / (f"functional_requirements_rewritten{tag}.json" if tag else "functional_requirements_rewritten.json"),
        "validation": case_dir / (f"validation_report{tag}.json" if tag else "validation_report.json"),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def process_changed_file(
    case_dir: Path,
    changed_path: Path,
    suffix: str,
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
    out = build_output_paths(case_dir, suffix)
    if out["structured"].exists() and not overwrite:
        return {
            "case_id": case_dir.name,
            "suffix": suffix,
            "status": "skip_exists",
            "changed_file": changed_path.name,
        }

    raw_text = hrp.normalize_ws(changed_path.read_text(encoding="utf-8"))
    extraction_prompt = hrp.build_extractor_prompt(raw_text)
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
        extracted_obj, extraction_response = hrp.call_llm_json(
            model_name=extractor_model,
            prompt=extraction_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        extracted = hrp.normalize_extracted(extracted_obj)
    except Exception as exc:
        extraction_error = str(exc)

    if not extracted:
        extracted = hrp.fallback_extract(raw_text)

    rewriting_prompt = hrp.build_rewriter_prompt(extracted)
    try:
        rewritten_obj, rewriting_response = hrp.call_llm_json(
            model_name=rewriter_model,
            prompt=rewriting_prompt,
            ollama_host=ollama_host,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        rewritten = hrp.normalize_rewritten(rewritten_obj, extracted)
    except Exception as exc:
        rewriting_error = str(exc)

    if not rewritten:
        rewritten = [hrp.to_shall(x["requirement"]) for x in extracted if x.get("requirement")]
        rewritten = hrp.dedupe_keep_order([x for x in rewritten if x])

    if not disable_llm_validator:
        validation_prompt = hrp.build_validator_prompt(raw_text, rewritten)
        try:
            llm_obj, validator_response = hrp.call_llm_json(
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

    deterministic = hrp.deterministic_validation(raw_text, rewritten)
    final_status = "needs_review"
    if deterministic["overall_assessment"] == "pass":
        if disable_llm_validator:
            final_status = "pass"
        elif str(llm_validation.get("overall_assessment", "needs_review")).lower() == "pass":
            final_status = "pass"

    title_case_name = case_dir.name if not suffix else f"{case_dir.name}_scenario_{suffix}"
    structured_text = hrp.build_structured_requirement_text(title_case_name, raw_text, rewritten)
    out["structured"].write_text(structured_text, encoding="utf-8")

    case_key = case_dir.name if not suffix else f"{case_dir.name}#{suffix}"
    extracted_artifact = {
        "case_id": case_key,
        "source_changed_file": changed_path.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": extractor_model,
        "functional_requirements": extracted,
        "errors": {"llm_extraction_error": extraction_error},
        "prompt": extraction_prompt,
        "llm_response": extraction_response,
    }
    write_json(out["extracted"], extracted_artifact)

    rewritten_artifact = {
        "case_id": case_key,
        "source_changed_file": changed_path.name,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": rewriter_model,
        "rewritten_requirements": rewritten,
        "source_extracted_requirements": extracted,
        "errors": {"llm_rewriting_error": rewriting_error},
        "prompt": rewriting_prompt,
        "llm_response": rewriting_response,
    }
    write_json(out["rewritten"], rewritten_artifact)

    validation_artifact = {
        "case_id": case_key,
        "source_changed_file": changed_path.name,
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
    write_json(out["validation"], validation_artifact)

    return {
        "case_id": case_dir.name,
        "suffix": suffix,
        "status": "ok",
        "changed_file": changed_path.name,
        "extracted_count": len(extracted),
        "rewritten_count": len(rewritten),
        "final_assessment": final_status,
        "has_errors": bool(extraction_error or rewriting_error or validator_error),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hybrid LLM pipeline over raw_requirement_changed*.txt files."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--start-case", type=int, default=1)
    parser.add_argument("--end-case", type=int, default=999)
    parser.add_argument("--cases", nargs="*", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--model", default=hrp.DEFAULT_MODEL, help="Default model for all three passes.")
    parser.add_argument("--extractor-model", default="", help="Override extractor model.")
    parser.add_argument("--rewriter-model", default="", help="Override rewriter model.")
    parser.add_argument("--validator-model", default="", help="Override validator model.")
    parser.add_argument("--disable-llm-validator", action="store_true")
    parser.add_argument("--ollama-host", default=hrp.DEFAULT_OLLAMA_HOST)
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

    summary: dict[str, int] = {
        "ok": 0,
        "skip_exists": 0,
        "skip_no_changed_files": 0,
        "error": 0,
    }

    for case_dir in case_dirs:
        changed_files = discover_changed_files(case_dir)
        if not changed_files:
            summary["skip_no_changed_files"] += 1
            print(f"[skip_no_changed_files] {case_dir.name}")
            continue
        for changed_path, suffix in changed_files:
            try:
                result = process_changed_file(
                    case_dir=case_dir,
                    changed_path=changed_path,
                    suffix=suffix,
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
                status = result.get("status", "error")
                if status in summary:
                    summary[status] += 1
                else:
                    summary["error"] += 1
                print(
                    f"[{status}] {case_dir.name}"
                    f"{'#' + suffix if suffix else ''}"
                    f" source={changed_path.name}"
                    f" extracted={result.get('extracted_count', 0)}"
                    f" rewritten={result.get('rewritten_count', 0)}"
                    f" assessment={result.get('final_assessment', '')}"
                )
            except Exception as exc:
                summary["error"] += 1
                print(f"[error] {case_dir.name}{'#' + suffix if suffix else ''}: {exc}")

    print("Done.")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

