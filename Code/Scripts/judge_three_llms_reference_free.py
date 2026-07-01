#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from ollama import Client as OllamaClient
except ImportError:  # pragma: no cover - exercised on machines without the optional client
    OllamaClient = None  # type: ignore[assignment]

from judge_plantuml_deepseek import CRITERIA, build_judge_prompt, extract_json_object
from plantuml_pipeline.parser import normalize_puml_text


EXPERIMENT_VERSION = "three_judge_reference_free_v1"
GENERAL_PROMPT_VERSION = "human_rubric_general_v1"
PROMETHEUS_PROMPT_VERSION = "human_rubric_prometheus_reference_free_v1"
DEFAULT_OUTPUT_DIR = Path(
    "results/plantuml_pipeline/llm_judge/three_judge_reference_free_v1"
)
RESULT_PATTERN = re.compile(
    r"\[RESULT\]\s*(?:<\s*score\s*>\s*)?([1-5])\b",
    re.IGNORECASE,
)

GENERAL_JUDGE_MODELS = {
    "deepseek": "deepseek-r1:14b",
    "llama": "llama3.1:8b-instruct-q4_K_M",
}
SPECIALIZED_JUDGE_MODEL = "ggozad/prometheus2"

JUDGE_OPTIONS: dict[str, Any] = {
    "temperature": 0.0,
    "top_p": 1.0,
    "num_predict": 1200,
}

PROMETHEUS_RUBRICS = {
    "completeness": (
        "Completeness: Determine whether all required states, transitions, events, "
        "guards, initial states, and final states are present.\n\n"
        "Score 1: Not fulfilled at all; almost all required diagram elements are absent.\n"
        "Score 2: Fulfilled to a minimal extent; only a small portion of the required "
        "diagram elements is present.\n"
        "Score 3: Partially fulfilled; the main elements are represented, but several "
        "important elements are missing.\n"
        "Score 4: Mainly fulfilled; nearly all required elements are present, with only "
        "minor omissions.\n"
        "Score 5: Completely fulfilled; all required states, transitions, events, guards, "
        "initial states, and final states are present."
    ),
    "correctness": (
        "Correctness: Determine whether the diagram's behaviour logically matches the "
        "requirement, with no contradictions.\n\n"
        "Score 1: Not fulfilled at all; the represented behaviour is almost entirely "
        "incorrect or contradictory.\n"
        "Score 2: Fulfilled to a minimal extent; only a small part is correct and major "
        "logical errors remain.\n"
        "Score 3: Partially fulfilled; the main behaviour is partly correct, but important "
        "logical problems remain.\n"
        "Score 4: Mainly fulfilled; the behaviour is mostly correct, with only minor "
        "logical issues.\n"
        "Score 5: Completely fulfilled; the behaviour completely and correctly matches "
        "the requirement without contradiction."
    ),
    "understandability": (
        "Understandability: Determine whether the diagram is clear, readable, and not "
        "unnecessarily complex or redundant.\n\n"
        "Score 1: Not fulfilled at all; the diagram is extremely confusing or unreadable.\n"
        "Score 2: Fulfilled to a minimal extent; major clarity or structural problems make "
        "the diagram difficult to understand.\n"
        "Score 3: Partially fulfilled; the diagram is understandable, but several clarity "
        "or complexity issues remain.\n"
        "Score 4: Mainly fulfilled; the diagram is clear and readable, with only minor "
        "issues.\n"
        "Score 5: Completely fulfilled; the diagram is fully clear, readable, concise, "
        "and well structured."
    ),
    "terminological_alignment": (
        "Terminological alignment: Determine whether state names and transition labels "
        "use the exact same terms as the requirement text.\n\n"
        "Score 1: Not fulfilled at all; terminology is almost entirely unrelated to the "
        "requirement.\n"
        "Score 2: Fulfilled to a minimal extent; only a small amount of terminology uses "
        "the same terms as the requirement.\n"
        "Score 3: Partially fulfilled; the main terminology is partly aligned, but several "
        "important mismatches exist.\n"
        "Score 4: Mainly fulfilled; terminology is mostly aligned, with only minor wording "
        "differences.\n"
        "Score 5: Completely fulfilled; state names and transition labels use the exact "
        "same terms as the requirement text."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def anonymous_id(generation_model: str, method: str, case_id: str) -> str:
    value = f"{generation_model}|{method}|{case_id}".encode("utf-8")
    return f"diagram_{hashlib.sha256(value).hexdigest()[:12]}"


def discover_diagrams(root: Path) -> list[dict[str, Any]]:
    diagrams: list[dict[str, Any]] = []
    for puml_path in sorted(root.glob("*/*/case_*/diagram.puml")):
        case_dir = puml_path.parent
        method_dir = case_dir.parent
        model_dir = method_dir.parent
        requirement_path = case_dir / "requirement.txt"
        source_path = case_dir / "source_run_id.txt"
        if not requirement_path.exists():
            raise FileNotFoundError(f"Requirement file not found: {requirement_path}")

        requirement = requirement_path.read_text(encoding="utf-8", errors="replace")
        candidate = normalize_puml_text(
            puml_path.read_text(encoding="utf-8", errors="replace")
        )
        diagrams.append(
            {
                "diagram_id": anonymous_id(
                    model_dir.name,
                    method_dir.name,
                    case_dir.name,
                ),
                "case_id": case_dir.name,
                "requirement_id": case_dir.name,
                "generation_model": model_dir.name,
                "generation_method": method_dir.name,
                "source_run_id": (
                    source_path.read_text(encoding="utf-8", errors="replace").strip()
                    if source_path.exists()
                    else ""
                ),
                "requirement": requirement,
                "candidate_plantuml": candidate,
                "requirement_sha256": sha256_text(requirement),
                "candidate_sha256": sha256_text(candidate),
            }
        )
    return diagrams


def build_prometheus_prompt(
    requirement: str,
    candidate_plantuml: str,
    criterion: str,
    retry_reminder: bool = False,
) -> str:
    reminder = (
        "\n6. This is a retry. End with `[RESULT] 1`, `[RESULT] 2`, "
        "`[RESULT] 3`, `[RESULT] 4`, or `[RESULT] 5` according to your score. "
        "Never write the literal text `<score>`.\n"
        if retry_reminder
        else ""
    )
    return (
        "### Task Description:\n\n"
        "An instruction, a response to evaluate, and a score rubric representing one "
        "evaluation criterion are provided.\n\n"
        "Evaluate the response strictly according to the rubric.\n\n"
        "Important rules:\n"
        "1. Do not repair, rewrite, or regenerate the response.\n"
        "2. Do not generate new PlantUML.\n"
        "3. Do not assume behaviour that is not stated or clearly implied by the instruction.\n"
        "4. Provide concise evaluation feedback.\n"
        "5. End with `[RESULT] N`, replacing N with one integer from 1 to 5. "
        "For example, a score of four must end exactly with `[RESULT] 4`. "
        "Never write the literal text `<score>`.\n"
        f"{reminder}\n"
        "### The instruction to evaluate:\n\n"
        f"{requirement}\n\n"
        "### Response to evaluate:\n\n"
        f"{candidate_plantuml}\n\n"
        "### Score Rubric:\n\n"
        f"{PROMETHEUS_RUBRICS[criterion]}\n\n"
        "### Feedback:\n"
    )


def _value(payload: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(payload, dict) and name in payload:
            return payload[name]
        if hasattr(payload, name):
            return getattr(payload, name)
    return default


def _model_name_matches(expected: str, actual: str) -> bool:
    def clean(value: str) -> str:
        normalized = value.strip().lower()
        return normalized[:-7] if normalized.endswith(":latest") else normalized

    return clean(expected) == clean(actual)


def get_model_digest(client: Any, model_tag: str) -> str:
    response = client.list()
    models = _value(response, "models", default=[]) or []
    for model in models:
        name = str(_value(model, "model", "name", default=""))
        if _model_name_matches(model_tag, name):
            digest = str(_value(model, "digest", default="")).strip()
            if digest:
                return digest
            raise RuntimeError(f"Ollama returned no digest for installed model: {model_tag}")
    raise RuntimeError(
        f"Ollama model is not installed: {model_tag}. Run `ollama pull {model_tag}`."
    )


def call_ollama(client: Any, model_tag: str, prompt: str) -> str:
    response = client.generate(
        model=model_tag,
        prompt=prompt,
        stream=False,
        options=dict(JUDGE_OPTIONS),
    )
    text = str(_value(response, "response", default="") or "").strip()
    if not text:
        raise ValueError("Ollama returned an empty response")
    return text


def parse_general_judgement(raw_output: str) -> dict[str, dict[str, Any]]:
    payload = extract_json_object(raw_output)
    parsed: dict[str, dict[str, Any]] = {}
    for criterion in CRITERIA:
        item = payload.get(criterion)
        if not isinstance(item, dict):
            raise ValueError(f"Missing JSON object for criterion: {criterion}")
        try:
            score = int(item.get("score"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid score for {criterion}") from exc
        if score not in range(1, 6):
            raise ValueError(f"Score for {criterion} is outside 1-5: {score}")
        justification = str(item.get("justification") or "").strip()
        if not justification:
            raise ValueError(f"Missing justification for criterion: {criterion}")
        parsed[criterion] = {
            "score": score,
            "justification": justification,
        }
    return parsed


def parse_prometheus_judgement(raw_output: str) -> dict[str, Any]:
    matches = list(RESULT_PATTERN.finditer(raw_output))
    if not matches:
        raise ValueError("Prometheus response does not contain `[RESULT] <score>`")
    match = matches[-1]
    score = int(match.group(1))
    feedback = raw_output[: match.start()].strip()
    if not feedback:
        feedback = "No textual feedback provided."
    return {"score": score, "feedback": feedback}


def compact_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt": attempt["attempt"],
        "timestamp": attempt["timestamp"],
        "prompt_sha256": attempt["prompt_sha256"],
        "raw_output": attempt["raw_output"],
        "error": attempt["error"],
    }


def evaluate_general_judge(
    client: Any,
    model_tag: str,
    model_digest: str,
    requirement: str,
    candidate_plantuml: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base_prompt = build_judge_prompt(requirement, candidate_plantuml)
    retry_suffix = (
        "\n\nIMPORTANT RETRY REMINDER: Return only one valid JSON object using the exact "
        "requested schema. Include all four criteria, integer scores from 1 to 5, and "
        "a non-empty justification for every criterion."
    )
    attempts: list[dict[str, Any]] = []
    parsed: dict[str, dict[str, Any]] | None = None

    for attempt_number in (1, 2):
        prompt = base_prompt if attempt_number == 1 else base_prompt + retry_suffix
        raw_output = ""
        error = ""
        try:
            raw_output = call_ollama(client, model_tag, prompt)
            parsed = parse_general_judgement(raw_output)
        except Exception as exc:  # noqa: BLE001 - preserve judge failures in the audit
            error = str(exc)
        attempts.append(
            {
                "attempt": attempt_number,
                "timestamp": utc_now(),
                "prompt_version": GENERAL_PROMPT_VERSION,
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt,
                "raw_output": raw_output,
                "error": error,
            }
        )
        if parsed is not None:
            break

    result: dict[str, Any] = {
        "judge_type": "general_purpose",
        "model_tag": model_tag,
        "ollama_digest": model_digest,
        "prompt_version": GENERAL_PROMPT_VERSION,
        "parameters": dict(JUDGE_OPTIONS),
        "evaluated_at": utc_now(),
        "status": "ok" if parsed is not None else "failed",
        "attempts": [compact_attempt(attempt) for attempt in attempts],
    }
    for criterion in CRITERIA:
        if parsed is None:
            result[criterion] = {
                "score": None,
                "justification": "Judge response could not be parsed after two attempts.",
            }
        else:
            result[criterion] = parsed[criterion]
    return result, attempts


def evaluate_prometheus_criterion(
    client: Any,
    model_tag: str,
    model_digest: str,
    requirement: str,
    candidate_plantuml: str,
    criterion: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    parsed: dict[str, Any] | None = None

    for attempt_number in (1, 2):
        prompt = build_prometheus_prompt(
            requirement,
            candidate_plantuml,
            criterion,
            retry_reminder=attempt_number == 2,
        )
        raw_output = ""
        error = ""
        try:
            raw_output = call_ollama(client, model_tag, prompt)
            parsed = parse_prometheus_judgement(raw_output)
        except Exception as exc:  # noqa: BLE001 - preserve judge failures in the audit
            error = str(exc)
        attempts.append(
            {
                "attempt": attempt_number,
                "timestamp": utc_now(),
                "criterion": criterion,
                "prompt_version": PROMETHEUS_PROMPT_VERSION,
                "prompt_sha256": sha256_text(prompt),
                "prompt": prompt,
                "raw_output": raw_output,
                "error": error,
            }
        )
        if parsed is not None:
            break

    result = {
        "score": parsed["score"] if parsed is not None else None,
        "feedback": (
            parsed["feedback"]
            if parsed is not None
            else "Judge response could not be parsed after two attempts."
        ),
        "status": "ok" if parsed is not None else "failed",
        "evaluated_at": utc_now(),
        "attempts": [compact_attempt(attempt) for attempt in attempts],
        "model_tag": model_tag,
        "ollama_digest": model_digest,
        "prompt_version": PROMETHEUS_PROMPT_VERSION,
        "parameters": dict(JUDGE_OPTIONS),
    }
    return result, attempts


def evaluate_prometheus_all(
    client: Any,
    model_tag: str,
    model_digest: str,
    requirement: str,
    candidate_plantuml: str,
    existing: dict[str, Any] | None = None,
    should_evaluate: Callable[[str, dict[str, Any] | None], bool] | None = None,
    on_result: Callable[
        [str, dict[str, Any], list[dict[str, Any]], dict[str, Any]],
        None,
    ]
    | None = None,
) -> dict[str, Any]:
    result = dict(existing or {})
    result.update(
        {
            "judge_type": "specialized_evaluation",
            "model_tag": model_tag,
            "ollama_digest": model_digest,
            "prompt_version": PROMETHEUS_PROMPT_VERSION,
            "parameters": dict(JUDGE_OPTIONS),
        }
    )
    for criterion in CRITERIA:
        current = result.get(criterion)
        if should_evaluate is not None and not should_evaluate(criterion, current):
            continue
        criterion_result, attempts = evaluate_prometheus_criterion(
            client=client,
            model_tag=model_tag,
            model_digest=model_digest,
            requirement=requirement,
            candidate_plantuml=candidate_plantuml,
            criterion=criterion,
        )
        result[criterion] = criterion_result
        result["evaluated_at"] = utc_now()
        if on_result is not None:
            on_result(criterion, criterion_result, attempts, result)

    statuses = [
        result.get(criterion, {}).get("status")
        for criterion in CRITERIA
        if isinstance(result.get(criterion), dict)
    ]
    if len(statuses) < len(CRITERIA):
        result["status"] = "partial"
    elif all(status == "ok" for status in statuses):
        result["status"] = "ok"
    else:
        result["status"] = "failed"
    return result


def new_combined_record(diagram: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagram_id": diagram["diagram_id"],
        "case_id": diagram["case_id"],
        "requirement_id": diagram["requirement_id"],
        "generation_model": diagram["generation_model"],
        "generation_method": diagram["generation_method"],
        "source_run_id": diagram["source_run_id"],
        "requirement_sha256": diagram["requirement_sha256"],
        "candidate_sha256": diagram["candidate_sha256"],
        "judges": {},
    }


def load_combined_records(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
            records[str(record["diagram_id"])] = record
    return records


def write_combined_records(
    path: Path,
    records: dict[str, dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for diagram_id in sorted(records):
            handle.write(json.dumps(records[diagram_id], ensure_ascii=False) + "\n")
    temporary.replace(path)


def append_audit_attempts(
    path: Path,
    diagram: dict[str, Any],
    judge_model: str,
    judge_type: str,
    attempts: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for attempt in attempts:
            event = {
                "experiment_version": EXPERIMENT_VERSION,
                "diagram_id": diagram["diagram_id"],
                "case_id": diagram["case_id"],
                "generation_model": diagram["generation_model"],
                "generation_method": diagram["generation_method"],
                "candidate_sha256": diagram["candidate_sha256"],
                "judge_model": judge_model,
                "judge_type": judge_type,
                **attempt,
            }
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_flat_csv(path: Path, records: dict[str, dict[str, Any]]) -> None:
    fields = [
        "diagram_id",
        "case_id",
        "requirement_id",
        "generation_model",
        "generation_method",
        "source_run_id",
        "judge_model",
        "judge_type",
        "ollama_digest",
        "prompt_version",
        "status",
        "completeness_score",
        "correctness_score",
        "understandability_score",
        "terminological_alignment_score",
        "completeness_feedback",
        "correctness_feedback",
        "understandability_feedback",
        "terminological_alignment_feedback",
    ]
    rows: list[dict[str, Any]] = []
    for diagram_id in sorted(records):
        record = records[diagram_id]
        for judge_model, judgement in sorted(record.get("judges", {}).items()):
            row: dict[str, Any] = {
                field: record.get(field, "")
                for field in (
                    "diagram_id",
                    "case_id",
                    "requirement_id",
                    "generation_model",
                    "generation_method",
                    "source_run_id",
                )
            }
            row.update(
                {
                    "judge_model": judge_model,
                    "judge_type": judgement.get("judge_type", ""),
                    "ollama_digest": judgement.get("ollama_digest", ""),
                    "prompt_version": judgement.get("prompt_version", ""),
                    "status": judgement.get("status", ""),
                }
            )
            for criterion in CRITERIA:
                criterion_result = judgement.get(criterion, {})
                row[f"{criterion}_score"] = criterion_result.get("score")
                row[f"{criterion}_feedback"] = criterion_result.get(
                    "justification",
                    criterion_result.get("feedback", ""),
                )
            rows.append(row)

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def judgement_is_complete(
    judgement: dict[str, Any] | None,
    model_digest: str,
    prompt_version: str,
    retry_failed: bool,
) -> bool:
    if not isinstance(judgement, dict):
        return False
    if judgement.get("ollama_digest") != model_digest:
        return False
    if judgement.get("prompt_version") != prompt_version:
        return False
    status = judgement.get("status")
    if status == "failed" and retry_failed:
        return False
    return status in {"ok", "failed"}


def make_client(host: str, timeout: int) -> Any:
    if OllamaClient is None:
        raise RuntimeError(
            "The Python Ollama client is not installed. Run `pip install -r requirements.txt`."
        )
    try:
        return OllamaClient(host=host, timeout=float(timeout))
    except TypeError:
        return OllamaClient(host=host)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reference-free DeepSeek, Llama, and Prometheus judging experiment."
    )
    parser.add_argument("--valid-diagrams-root", type=Path, default=Path("valid_diagrams"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--deepseek-model", default=GENERAL_JUDGE_MODELS["deepseek"])
    parser.add_argument("--llama-model", default=GENERAL_JUDGE_MODELS["llama"])
    parser.add_argument("--prometheus-model", default=SPECIALIZED_JUDGE_MODEL)
    parser.add_argument(
        "--judge",
        action="append",
        choices=["deepseek", "llama", "prometheus"],
        help="Judge to run; repeatable. Defaults to all three.",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--shuffle-seed", type=int, default=20260627)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--only-diagram-id",
        action="append",
        help="Run only this diagram ID; repeatable.",
    )
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    if not args.valid_diagrams_root.exists():
        raise FileNotFoundError(f"Folder not found: {args.valid_diagrams_root}")

    combined_path = args.output_dir / "combined_judgements.jsonl"
    csv_path = args.output_dir / "judge_scores_long.csv"
    audit_path = args.output_dir / "judge_call_audit.jsonl"
    manifest_path = args.output_dir / "experiment_manifest.json"
    if args.fresh:
        for path in (combined_path, csv_path, audit_path, manifest_path):
            path.unlink(missing_ok=True)

    diagrams = discover_diagrams(args.valid_diagrams_root)
    if args.only_diagram_id:
        requested_ids = set(args.only_diagram_id)
        available_ids = {diagram["diagram_id"] for diagram in diagrams}
        missing_ids = sorted(requested_ids - available_ids)
        if missing_ids:
            raise ValueError(
                "Requested diagram IDs were not found: " + ", ".join(missing_ids)
            )
        diagrams = [
            diagram for diagram in diagrams if diagram["diagram_id"] in requested_ids
        ]
    random.Random(args.shuffle_seed).shuffle(diagrams)
    if args.limit > 0:
        diagrams = diagrams[: args.limit]
    if not diagrams:
        raise FileNotFoundError(
            f"No diagram.puml files found under {args.valid_diagrams_root}"
        )

    selected_judges = args.judge or ["deepseek", "llama", "prometheus"]
    model_tags = {
        "deepseek": args.deepseek_model,
        "llama": args.llama_model,
        "prometheus": args.prometheus_model,
    }
    prompt_versions = {
        "deepseek": GENERAL_PROMPT_VERSION,
        "llama": GENERAL_PROMPT_VERSION,
        "prometheus": PROMETHEUS_PROMPT_VERSION,
    }

    client = make_client(args.ollama_host, args.timeout)
    model_digests = {
        judge: get_model_digest(client, model_tags[judge])
        for judge in selected_judges
    }
    records = load_combined_records(combined_path)

    manifest = {
        "experiment_version": EXPERIMENT_VERSION,
        "evaluation_mode": "reference_free",
        "valid_diagrams_root": str(args.valid_diagrams_root),
        "diagram_count": len(diagrams),
        "selected_judges": selected_judges,
        "models": {
            judge: {
                "model_tag": model_tags[judge],
                "ollama_digest": model_digests[judge],
                "prompt_version": prompt_versions[judge],
                "parameters": dict(JUDGE_OPTIONS),
            }
            for judge in selected_judges
        },
        "shuffle_seed": args.shuffle_seed,
        "started_or_resumed_at": utc_now(),
        "combined_output": str(combined_path),
        "flat_csv_output": str(csv_path),
        "audit_output": str(audit_path),
    }
    write_json_atomic(manifest_path, manifest)

    for judge in selected_judges:
        model_tag = model_tags[judge]
        digest = model_digests[judge]
        print(f"\n[judge] {judge} | model={model_tag} | diagrams={len(diagrams)}")

        for index, diagram in enumerate(diagrams, start=1):
            existing = records.get(diagram["diagram_id"])
            if (
                existing is None
                or existing.get("requirement_sha256") != diagram["requirement_sha256"]
                or existing.get("candidate_sha256") != diagram["candidate_sha256"]
            ):
                existing = new_combined_record(diagram)
                records[diagram["diagram_id"]] = existing

            judges = existing.setdefault("judges", {})
            current_judgement = judges.get(model_tag)

            if judge in {"deepseek", "llama"}:
                if judgement_is_complete(
                    current_judgement,
                    digest,
                    GENERAL_PROMPT_VERSION,
                    args.retry_failed,
                ):
                    print(f"  [{index}/{len(diagrams)}] skip {diagram['diagram_id']}")
                    continue

                judgement, attempts = evaluate_general_judge(
                    client=client,
                    model_tag=model_tag,
                    model_digest=digest,
                    requirement=diagram["requirement"],
                    candidate_plantuml=diagram["candidate_plantuml"],
                )
                judges[model_tag] = judgement
                append_audit_attempts(
                    audit_path,
                    diagram,
                    model_tag,
                    "general_purpose",
                    attempts,
                )
                write_combined_records(combined_path, records)
                write_flat_csv(csv_path, records)
                scores = "/".join(
                    str(judgement[criterion]["score"]) for criterion in CRITERIA
                )
                print(
                    f"  [{index}/{len(diagrams)}] {diagram['diagram_id']} "
                    f"status={judgement['status']} scores={scores}"
                )
                continue

            prometheus_record = (
                current_judgement
                if isinstance(current_judgement, dict)
                and current_judgement.get("ollama_digest") == digest
                and current_judgement.get("prompt_version")
                == PROMETHEUS_PROMPT_VERSION
                else {}
            )

            def should_evaluate(
                criterion: str,
                current: dict[str, Any] | None,
            ) -> bool:
                return not judgement_is_complete(
                    current,
                    digest,
                    PROMETHEUS_PROMPT_VERSION,
                    args.retry_failed,
                )

            def persist_prometheus_result(
                criterion: str,
                criterion_result: dict[str, Any],
                attempts: list[dict[str, Any]],
                current_record: dict[str, Any],
            ) -> None:
                judges[model_tag] = current_record
                append_audit_attempts(
                    audit_path,
                    diagram,
                    model_tag,
                    "specialized_evaluation",
                    attempts,
                )
                write_combined_records(combined_path, records)
                write_flat_csv(csv_path, records)
                print(
                    f"  [{index}/{len(diagrams)}] {diagram['diagram_id']} "
                    f"{criterion}={criterion_result['score']} "
                    f"status={criterion_result['status']}"
                )

            prometheus_record = evaluate_prometheus_all(
                client=client,
                model_tag=model_tag,
                model_digest=digest,
                requirement=diagram["requirement"],
                candidate_plantuml=diagram["candidate_plantuml"],
                existing=prometheus_record,
                should_evaluate=should_evaluate,
                on_result=persist_prometheus_result,
            )
            judges[model_tag] = prometheus_record
            write_combined_records(combined_path, records)
            write_flat_csv(csv_path, records)

    manifest["completed_at"] = utc_now()
    manifest["combined_record_count"] = len(records)
    write_json_atomic(manifest_path, manifest)
    print(f"\nCombined records: {combined_path}")
    print(f"Flat score CSV: {csv_path}")
    print(f"Full call audit: {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
