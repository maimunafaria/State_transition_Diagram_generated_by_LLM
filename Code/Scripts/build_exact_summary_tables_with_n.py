#!/usr/bin/env python3
"""Build exact summary tables with sample-size annotations.

This script regenerates the compact CSV tables used in the paper/spreadsheet
views from the underlying automatic-validity and human-evaluation CSVs.

Outputs:
  results/human_evaluation_likert/exact_zero_one_few_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_zero_one_few_rag_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_rag_ablation_table_score_only_with_n.csv
  results/human_evaluation_likert/exact_repair_table_score_only_with_n.csv

The script discovers additional RAG variants and repair methods from the input
files, so new entities appear automatically once their source rows exist.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "human_evaluation_likert"

MAIN_HUMAN = ROOT / "results" / "evaluation_diagram_responses_long_form.csv"
RAG_HUMAN = ROOT / "results" / "rag_ablation_evaluation_with_llm_method.csv"

MAIN_SYNTACTIC = ROOT / "results" / "plantuml_pipeline" / "metrics" / "validity_by_model_method.csv"
MAIN_STRUCTURAL = ROOT / "results" / "plantuml_pipeline" / "metrics" / "state_rules_validity_by_model_method.csv"

RAG_SYNTACTIC = (
    ROOT
    / "results"
    / "plantuml_pipeline"
    / "rq_rag_ablation_structural_validity"
    / "plantuml_syntax_validity_by_model_method.csv"
)
RAG_STRUCTURAL_ON_SYNTAX_VALID = (
    ROOT
    / "results"
    / "plantuml_pipeline"
    / "rq_rag_ablation_structural_validity"
    / "structural_validity_by_model_method_on_plantuml_valid.csv"
)

CRITERIA = [
    ("Completeness", "completeness"),
    ("Correctness", "correctness"),
    ("Understandability", "understandability"),
    ("Terminology alignment", "terminology_alignment"),
]

MODEL_ORDER = [
    "Llama 3.1 8B Instruct",
    "Mistral",
    "DeepSeek R1 14B",
    "Qwen 2.5 7B Instruct",
]

MODEL_SHORT = {
    "Llama 3.1 8B Instruct": "Llama",
    "Mistral": "Mistral",
    "DeepSeek R1 14B": "DeepSeek",
    "Qwen 2.5 7B Instruct": "Qwen",
}

MODEL_SHORT_LOWER = {
    model: short.lower() for model, short in MODEL_SHORT.items()
}

METHOD_ORDER = {
    "Zero-shot": 0,
    "One-shot": 1,
    "Few-shot": 2,
    "RAG": 3,
    "RAG [rules only]": 4,
    "RAG [examples only]": 5,
    "RAG [theory only]": 6,
    "Few-shot + Repair": 7,
    "RAG + Repair": 8,
}

RAG_METHOD_LABEL = {
    "RAG": "Rag (fully)",
    "RAG [rules only]": "Rag (only rules)",
    "RAG [examples only]": "Rag (only example)",
    "RAG [theory only]": "Rag (only theory)",
}

RAG_HUMAN_METHOD = {
    "RAG": "RAG",
    "RAG [rules only]": "RAG PlantUML/rules only",
    "RAG [examples only]": "RAG examples only",
    "RAG [theory only]": "RAG state-rules/theory only",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def model_sort_key(model: str) -> tuple[int, str]:
    try:
        return (MODEL_ORDER.index(model), model)
    except ValueError:
        return (len(MODEL_ORDER), model)


def method_sort_key(method: str) -> tuple[int, str]:
    return (METHOD_ORDER.get(method, 100), method)


def pct_value(valid: int, total: int) -> str:
    return f"{(valid / total * 100):.2f}%" if total else ""


def pct_with_n(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    valid = int(float(row["valid"]))
    total = int(float(row["total"]))
    return f"{pct_value(valid, total)} (n={valid}/{total})"


def median_with_n(values: list[int]) -> str:
    if not values:
        return ""
    med = median(values)
    med_text = f"{med:g}"
    return f"{med_text} (n={len(values)})"


def valid_index(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row["method"], row["model"]): row
        for row in read_csv(path)
        if row.get("method") and row.get("model")
    }


def numeric_scores(
    rows: list[dict[str, str]],
    *,
    method: str,
    model: str,
    criterion: str,
) -> list[int]:
    scores = []
    for row in rows:
        if row.get("method") != method or row.get("llm_used") != model:
            continue
        try:
            scores.append(int(float(row[criterion])))
        except Exception:
            pass
    return scores


def methods_in(indexes: list[dict[tuple[str, str], dict[str, str]]]) -> list[str]:
    methods = sorted({method for index in indexes for method, _ in index}, key=method_sort_key)
    return methods


def models_for_methods(
    methods: list[str],
    indexes: list[dict[tuple[str, str], dict[str, str]]],
    human_rows: list[dict[str, str]],
) -> list[str]:
    models = set()
    for index in indexes:
        for method, model in index:
            if method in methods:
                models.add(model)
    for row in human_rows:
        if row.get("method") in methods:
            models.add(row.get("llm_used", ""))
    models.discard("")
    return sorted(models, key=model_sort_key)


def make_header(
    methods: list[str],
    models: list[str],
    *,
    method_label,
    model_label,
) -> list[str]:
    return ["Evaluation group", "Metric"] + [
        f"{method_label(method)} | {model_label(model)}"
        for method in methods
        for model in models
    ]


def build_table(
    *,
    out_path: Path,
    methods: list[str],
    models: list[str],
    structural: dict[tuple[str, str], dict[str, str]],
    syntactic: dict[tuple[str, str], dict[str, str]],
    human_rows: list[dict[str, str]],
    human_method_map,
    method_label,
    model_label,
) -> None:
    header = make_header(methods, models, method_label=method_label, model_label=model_label)
    rows: list[list[str]] = []

    rows.append(
        ["Automatic (accuracy)", "Structural validity"]
        + [pct_with_n(structural.get((method, model))) for method in methods for model in models]
    )
    rows.append(
        ["Automatic (accuracy)", "Syntactic validity"]
        + [pct_with_n(syntactic.get((method, model))) for method in methods for model in models]
    )

    for criterion_label, criterion in CRITERIA:
        values = []
        for method in methods:
            human_method = human_method_map(method)
            for model in models:
                values.append(median_with_n(numeric_scores(human_rows, method=human_method, model=model, criterion=criterion)))
        rows.append(["Human (Likert scale 1-5)", criterion_label] + values)

    write_csv(out_path, header, rows)


def build_pair_table(
    *,
    out_path: Path,
    pairs: list[tuple[str, str]],
    structural: dict[tuple[str, str], dict[str, str]],
    syntactic: dict[tuple[str, str], dict[str, str]],
    human_rows: list[dict[str, str]],
    human_method_map,
    method_label,
    model_label,
) -> None:
    header = ["Evaluation group", "Metric"] + [
        f"{method_label(method, model)} | {model_label(model)}" for method, model in pairs
    ]
    rows: list[list[str]] = []

    rows.append(
        ["Automatic (accuracy)", "Structural validity"]
        + [pct_with_n(structural.get((method, model))) for method, model in pairs]
    )
    rows.append(
        ["Automatic (accuracy)", "Syntactic validity"]
        + [pct_with_n(syntactic.get((method, model))) for method, model in pairs]
    )

    for criterion_label, criterion in CRITERIA:
        values = []
        for method, model in pairs:
            human_method = human_method_map(method, model)
            values.append(median_with_n(numeric_scores(human_rows, method=human_method, model=model, criterion=criterion)))
        rows.append(["Human (Likert scale 1-5)", criterion_label] + values)

    write_csv(out_path, header, rows)


def build_zero_one_few() -> None:
    syntactic = valid_index(MAIN_SYNTACTIC)
    structural = valid_index(MAIN_STRUCTURAL)
    human_rows = read_csv(MAIN_HUMAN)

    methods = [m for m in ["Zero-shot", "One-shot", "Few-shot"] if any(k[0] == m for k in syntactic | structural)]
    models = models_for_methods(methods, [syntactic, structural], human_rows)
    build_table(
        out_path=OUT_DIR / "exact_zero_one_few_table_score_only_with_n.csv",
        methods=methods,
        models=models,
        structural=structural,
        syntactic=syntactic,
        human_rows=human_rows,
        human_method_map=lambda method: method,
        method_label=lambda method: method,
        model_label=lambda model: MODEL_SHORT.get(model, model),
    )


def build_zero_one_few_rag() -> None:
    syntactic = valid_index(MAIN_SYNTACTIC)
    structural = valid_index(MAIN_STRUCTURAL)
    human_rows = read_csv(MAIN_HUMAN)

    methods = [m for m in ["Zero-shot", "One-shot", "Few-shot", "RAG"] if any(k[0] == m for k in syntactic | structural)]
    models = models_for_methods(methods, [syntactic, structural], human_rows)
    build_table(
        out_path=OUT_DIR / "exact_zero_one_few_rag_table_score_only_with_n.csv",
        methods=methods,
        models=models,
        structural=structural,
        syntactic=syntactic,
        human_rows=human_rows,
        human_method_map=lambda method: method,
        method_label=lambda method: method,
        model_label=lambda model: MODEL_SHORT.get(model, model),
    )


def build_rag_ablation() -> None:
    syntactic = valid_index(RAG_SYNTACTIC)
    structural = valid_index(RAG_STRUCTURAL_ON_SYNTAX_VALID)
    human_rows = read_csv(MAIN_HUMAN) + read_csv(RAG_HUMAN)

    methods = [m for m in methods_in([syntactic, structural]) if m == "RAG" or m.startswith("RAG [")]
    models = models_for_methods(methods, [syntactic, structural], human_rows)
    build_table(
        out_path=OUT_DIR / "exact_rag_ablation_table_score_only_with_n.csv",
        methods=methods,
        models=models,
        structural=structural,
        syntactic=syntactic,
        human_rows=human_rows,
        human_method_map=lambda method: RAG_HUMAN_METHOD.get(method, method),
        method_label=lambda method: RAG_METHOD_LABEL.get(method, method.replace("[", "(").replace("]", ")")),
        model_label=lambda model: MODEL_SHORT_LOWER.get(model, MODEL_SHORT.get(model, model).lower()),
    )


def build_repair() -> None:
    syntactic = valid_index(MAIN_SYNTACTIC)
    structural = valid_index(MAIN_STRUCTURAL)
    human_rows = read_csv(MAIN_HUMAN)

    repair_pairs = sorted(
        {
            (method, model)
            for index in (syntactic, structural)
            for method, model in index
            if method.endswith("+ Repair") or "+ Repair [" in method or method == "Repair"
        },
        key=lambda item: (model_sort_key(item[1]), method_sort_key(item[0])),
    )
    repair_human_rows = []
    for row in human_rows:
        if row.get("method") == "Repair":
            repair_human_rows.append(row)
        elif any(row.get("method") == method for method, _ in repair_pairs):
            repair_human_rows.append(row)

    build_pair_table(
        out_path=OUT_DIR / "exact_repair_table_score_only_with_n.csv",
        pairs=repair_pairs,
        structural=structural,
        syntactic=syntactic,
        human_rows=repair_human_rows,
        human_method_map=lambda method, model: method
        if any(r.get("method") == method and r.get("llm_used") == model for r in repair_human_rows)
        else "Repair",
        method_label=lambda method, model: "Repair" if method.endswith("+ Repair") else method,
        model_label=lambda model: MODEL_SHORT_LOWER.get(model, MODEL_SHORT.get(model, model).lower()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--table",
        choices=["all", "zero-one-few", "zero-one-few-rag", "rag-ablation", "repair"],
        default="all",
        help="Which exact table to regenerate.",
    )
    args = parser.parse_args()

    if args.table in ("all", "zero-one-few"):
        build_zero_one_few()
    if args.table in ("all", "zero-one-few-rag"):
        build_zero_one_few_rag()
    if args.table in ("all", "rag-ablation"):
        build_rag_ablation()
    if args.table in ("all", "repair"):
        build_repair()

    print(f"updated={OUT_DIR}")


if __name__ == "__main__":
    main()
