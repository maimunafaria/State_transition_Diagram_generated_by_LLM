#!/usr/bin/env python3
"""Build complexity-level validation and human-evaluation tables/charts.

Outputs are grouped by requirement complexity: simple, medium, complex.
Automatic validation is computed from per-case PlantUML and state-rule validity
files. Human scores are computed from the long-form evaluator CSVs.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METRICS_DIR = ROOT / "results" / "plantuml_pipeline" / "metrics"
HUMAN_MAIN = ROOT / "results" / "evaluation_diagram_responses_long_form.csv"
HUMAN_RAG_ABLATION = ROOT / "results" / "rag_ablation_evaluation_with_llm_method.csv"
DEFAULT_OUT = ROOT / "results" / "complexity_evaluation"

COMPLEXITY_ORDER = ["simple", "medium", "complex"]
MODEL_ORDER = [
    "Llama 3.1 8B Instruct",
    "Mistral",
    "DeepSeek R1 14B",
    "Qwen 2.5 7B Instruct",
]
METHOD_ORDER = [
    "Zero-shot",
    "One-shot",
    "Few-shot",
    "RAG",
    "RAG [rules only]",
    "RAG [examples only]",
    "RAG [theory only]",
    "Few-shot + Repair",
    "RAG + Repair",
]
MAIN_PROMPTING_METHODS = ["Zero-shot", "One-shot", "Few-shot", "RAG"]
RAG_ABLATION_METHODS = [
    "RAG",
    "RAG [rules only]",
    "RAG [examples only]",
    "RAG [theory only]",
]
HUMAN_METRICS = [
    ("completeness", "Completeness"),
    ("correctness", "Correctness"),
    ("understandability", "Understandability"),
    ("terminology_alignment", "Terminology alignment"),
]
PALETTE = {
    "Llama 3.1 8B Instruct": "#4E79A7",
    "Mistral": "#F28E2B",
    "DeepSeek R1 14B": "#59A14F",
    "Qwen 2.5 7B Instruct": "#E15759",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    fields = fieldnames or list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def median(values: list[float]) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def pct(valid: int, total: int) -> float | None:
    return round(valid / total * 100.0, 2) if total else None


def fmt_num(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_pct(value: float | None, numerator: int, denominator: int) -> str:
    if value is None:
        return ""
    return f"{value:.2f}% (n={numerator}/{denominator})"


def normalize_method(method: str, diagram_name: str = "") -> str:
    raw = (method or "").strip()
    lowered = raw.lower()
    diagram_lower = (diagram_name or "").lower()
    if raw == "Repair":
        if "rag_repair" in diagram_lower:
            return "RAG + Repair"
        if "few_shot_repair" in diagram_lower:
            return "Few-shot + Repair"
        return raw
    if lowered in {"rag examples only", "rag example only"}:
        return "RAG [examples only]"
    if lowered in {"rag plantuml/rules only", "rag rules only"}:
        return "RAG [rules only]"
    if lowered in {"rag theory only", "rag state-rules/theory only"}:
        return "RAG [theory only]"
    return raw


def case_number_to_id(number: str, known_cases: set[str]) -> str:
    try:
        prefix = f"case_{int(float(str(number))):02d}_"
    except ValueError:
        return ""
    matches = [case_id for case_id in known_cases if case_id.startswith(prefix)]
    return matches[0] if len(matches) == 1 else ""


def complexity_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with (METRICS_DIR / "per_run_metrics.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = str(row.get("case_id", ""))
            complexity = str(row.get("complexity", "")).lower()
            if case_id and complexity in COMPLEXITY_ORDER:
                mapping.setdefault(case_id, complexity)
    return mapping


def ordered(items: set[str], preferred: list[str]) -> list[str]:
    out = [item for item in preferred if item in items]
    out.extend(sorted(items - set(out)))
    return out


def validation_summary(complexity_by_case: dict[str, str]) -> list[dict[str, object]]:
    plantuml_rows = read_csv(METRICS_DIR / "plantuml_validity_cases.csv")
    structural_rows = read_csv(METRICS_DIR / "state_rules_validity_cases.csv")

    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {
            "plantuml_total": 0,
            "plantuml_valid": 0,
            "structural_total": 0,
            "structural_valid": 0,
        }
    )
    plantuml_valid_keys: set[tuple[str, str, str, str]] = set()
    for row in plantuml_rows:
        complexity = complexity_by_case.get(row["case_id"])
        if complexity not in COMPLEXITY_ORDER:
            continue
        key = (row["model"], row["method"], complexity)
        grouped[key]["plantuml_total"] += 1
        if row["valid"].strip().lower() == "true":
            grouped[key]["plantuml_valid"] += 1
            plantuml_valid_keys.add((row["model"], row["method"], complexity, row["case_id"]))

    structural_on_plantuml: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "valid": 0}
    )
    for row in structural_rows:
        complexity = complexity_by_case.get(row["case_id"])
        if complexity not in COMPLEXITY_ORDER:
            continue
        key = (row["model"], row["method"], complexity)
        grouped[key]["structural_total"] += 1
        is_valid = row["valid"].strip().lower() == "true"
        if is_valid:
            grouped[key]["structural_valid"] += 1
        if (row["model"], row["method"], complexity, row["case_id"]) in plantuml_valid_keys:
            structural_on_plantuml[key]["total"] += 1
            if is_valid:
                structural_on_plantuml[key]["valid"] += 1

    rows: list[dict[str, object]] = []
    models = ordered({key[0] for key in grouped}, MODEL_ORDER)
    methods = ordered({key[1] for key in grouped}, METHOD_ORDER)
    for complexity in COMPLEXITY_ORDER:
        for method in methods:
            for model in models:
                counts = grouped.get((model, method, complexity))
                if not counts:
                    continue
                on_counts = structural_on_plantuml.get(
                    (model, method, complexity), {"total": 0, "valid": 0}
                )
                rows.append(
                    {
                        "complexity": complexity,
                        "method": method,
                        "model": model,
                        "plantuml_valid": counts["plantuml_valid"],
                        "plantuml_total": counts["plantuml_total"],
                        "plantuml_valid_percent": pct(
                            counts["plantuml_valid"], counts["plantuml_total"]
                        ),
                        "structural_valid": counts["structural_valid"],
                        "structural_total": counts["structural_total"],
                        "structural_valid_percent": pct(
                            counts["structural_valid"], counts["structural_total"]
                        ),
                        "structural_on_plantuml_valid": on_counts["valid"],
                        "plantuml_valid_denominator": on_counts["total"],
                        "structural_on_plantuml_valid_percent": pct(
                            on_counts["valid"], on_counts["total"]
                        ),
                    }
                )
    return rows


def human_rows(complexity_by_case: dict[str, str]) -> list[dict[str, object]]:
    known_cases = set(complexity_by_case)
    rows: list[dict[str, object]] = []
    sources = [
        (HUMAN_MAIN, "main_human_evaluation"),
        (HUMAN_RAG_ABLATION, "rag_ablation_human_evaluation"),
    ]
    for path, source in sources:
        if not path.exists():
            continue
        for row in read_csv(path):
            case_id = case_number_to_id(row.get("case_number", ""), known_cases)
            complexity = complexity_by_case.get(case_id)
            if complexity not in COMPLEXITY_ORDER:
                continue
            diagram_name = row.get("original_unbiased_diagram_name") or row.get("diagram_name") or ""
            method = normalize_method(row.get("method", ""), diagram_name)
            model = row.get("llm_used", "").strip()
            for metric_key, metric_label in HUMAN_METRICS:
                raw = row.get(metric_key, "")
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                rows.append(
                    {
                        "source": source,
                        "case_id": case_id,
                        "complexity": complexity,
                        "model": model,
                        "method": method,
                        "metric": metric_label,
                        "score": value,
                        "diagram_name": diagram_name,
                    }
                )
    return rows


def human_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    diagrams: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        key = (
            str(row["complexity"]),
            str(row["method"]),
            str(row["model"]),
            str(row["metric"]),
        )
        grouped[key].append(float(row["score"]))
        diagrams[key].add(str(row["diagram_name"]))

    out: list[dict[str, object]] = []
    for key, vals in sorted(grouped.items()):
        complexity, method, model, metric = key
        med = median(vals)
        out.append(
            {
                "complexity": complexity,
                "method": method,
                "model": model,
                "metric": metric,
                "median_score": med,
                "response_n": len(vals),
                "diagram_n": len(diagrams[key]),
            }
        )
    return out


def compact_table(
    validation_rows: list[dict[str, object]],
    human_summary_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    model_methods = ordered(
        {f'{row["method"]} | {row["model"]}' for row in validation_rows}
        | {f'{row["method"]} | {row["model"]}' for row in human_summary_rows},
        [f"{method} | {model}" for method in METHOD_ORDER for model in MODEL_ORDER],
    )
    rows: list[dict[str, object]] = []
    v_lookup = {
        (row["complexity"], row["method"], row["model"]): row for row in validation_rows
    }
    h_lookup = {
        (row["complexity"], row["method"], row["model"], row["metric"]): row
        for row in human_summary_rows
    }
    for complexity in COMPLEXITY_ORDER:
        specs = [
            ("Automatic (accuracy)", "PlantUML validity"),
            ("Automatic (accuracy)", "Structural validity"),
            ("Human (Likert scale 1-5)", "Average human score"),
            *[("Human (Likert scale 1-5)", label) for _key, label in HUMAN_METRICS],
        ]
        for group, metric in specs:
            row: dict[str, object] = {
                "Complexity": complexity,
                "Evaluation group": group,
                "Metric": metric,
            }
            for col in model_methods:
                method, model = col.split(" | ", 1)
                if group.startswith("Automatic"):
                    item = v_lookup.get((complexity, method, model))
                    if not item:
                        row[col] = ""
                    elif metric == "PlantUML validity":
                        row[col] = fmt_pct(
                            item["plantuml_valid_percent"],
                            int(item["plantuml_valid"]),
                            int(item["plantuml_total"]),
                        )
                    else:
                        row[col] = fmt_pct(
                            item["structural_on_plantuml_valid_percent"],
                            int(item["structural_on_plantuml_valid"]),
                            int(item["plantuml_valid_denominator"]),
                        )
                    continue

                if metric == "Average human score":
                    vals = [
                        h_lookup[(complexity, method, model, label)]["median_score"]
                        for _key, label in HUMAN_METRICS
                        if (complexity, method, model, label) in h_lookup
                    ]
                    ns = [
                        h_lookup[(complexity, method, model, label)]["response_n"]
                        for _key, label in HUMAN_METRICS
                        if (complexity, method, model, label) in h_lookup
                    ]
                    avg = round(sum(float(v) for v in vals) / len(vals), 2) if vals else None
                    row[col] = "" if avg is None else f"{fmt_num(avg)} (n={min(ns)})"
                else:
                    item = h_lookup.get((complexity, method, model, metric))
                    row[col] = (
                        ""
                        if not item
                        else f"{fmt_num(item['median_score'])} (n={item['response_n']})"
                    )
            rows.append(row)
    return rows


def svg_start(width: int, height: int, title: str, subtitle: str = "") -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".panel { font-size: 15px; font-weight: 700; }",
        ".label { font-size: 12px; }",
        ".tick { font-size: 11px; fill: #555; }",
        ".value { font-size: 11px; font-weight: 700; }",
        ".legend { font-size: 12px; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".axis { stroke: #333; stroke-width: 1.2; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="40" y="34">{html.escape(title)}</text>',
        f'<text class="subtitle" x="40" y="56">{html.escape(subtitle)}</text>' if subtitle else "",
    ]


def wrap_label(text: str, max_chars: int = 16) -> list[str]:
    words = text.replace(" + ", " + ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def add_text(parts: list[str], text: str, x: float, y: float, max_chars: int, anchor: str = "middle") -> None:
    for idx, line in enumerate(wrap_label(text, max_chars)):
        parts.append(
            f'<text class="label" x="{x:.1f}" y="{y + idx * 13:.1f}" text-anchor="{anchor}">{html.escape(line)}</text>'
        )


def heat_color(value: float | None, max_value: float) -> str:
    if value is None:
        return "#f1f1f1"
    ratio = max(0.0, min(value / max_value, 1.0))
    r = int(240 - 130 * ratio)
    g = int(246 - 55 * ratio)
    b = int(248 - 95 * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def selected_methods(rows_methods: set[str], requested: list[str]) -> list[str]:
    return [method for method in requested if method in rows_methods or method in requested]


def validation_heatmap(
    rows: list[dict[str, object]],
    output: Path,
    *,
    methods: list[str],
    title_suffix: str,
) -> None:
    models = ordered({str(r["model"]) for r in rows}, MODEL_ORDER)
    methods = selected_methods({str(r["method"]) for r in rows}, methods)
    lookup = {(r["complexity"], r["method"], r["model"]): r for r in rows}
    cell_w, cell_h = 100, 36
    label_w, top, left, gap = 160, 154, 40, 44
    panel_w = label_w + len(models) * cell_w
    width = left * 2 + len(COMPLEXITY_ORDER) * panel_w + (len(COMPLEXITY_ORDER) - 1) * gap
    height = top + len(methods) * cell_h + 54
    parts = svg_start(
        width,
        height,
        f"Validation Ratio by Diagram Complexity: {title_suffix}",
        "Structural validity among PlantUML-valid diagrams",
    )
    for p_idx, complexity in enumerate(COMPLEXITY_ORDER):
        x0 = left + p_idx * (panel_w + gap)
        parts.append(f'<text class="panel" x="{x0}" y="{top - 56}">{complexity.title()}</text>')
        for m_idx, model in enumerate(models):
            x = x0 + label_w + m_idx * cell_w + cell_w / 2
            add_text(parts, model.replace(" 7B Instruct", "").replace(" 8B Instruct", ""), x, top - 34, 12)
        for r_idx, method in enumerate(methods):
            y = top + r_idx * cell_h
            add_text(parts, method, x0 + label_w - 8, y + 15, 20, "end")
            for m_idx, model in enumerate(models):
                x = x0 + label_w + m_idx * cell_w
                item = lookup.get((complexity, method, model))
                value = None if not item else item["structural_on_plantuml_valid_percent"]
                title = "" if value is None else f"{method} | {model} | {complexity}: {value:.2f}%"
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{heat_color(value, 100)}" stroke="#fff"><title>{html.escape(title)}</title></rect>'
                )
                label = "" if value is None else f"{value:.0f}%"
                parts.append(f'<text class="value" x="{x + cell_w / 2}" y="{y + 22}" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    output.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def human_heatmap(
    rows: list[dict[str, object]],
    output: Path,
    *,
    methods: list[str],
    title_suffix: str,
) -> None:
    avg: dict[tuple[str, str, str], float] = {}
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["complexity"], row["method"], row["model"])].append(float(row["median_score"]))
    for key, vals in grouped.items():
        avg[key] = round(sum(vals) / len(vals), 2)
    models = ordered({key[2] for key in avg}, MODEL_ORDER)
    methods = selected_methods({key[1] for key in avg}, methods)
    cell_w, cell_h = 100, 38
    label_w, top, left, gap = 160, 154, 40, 44
    panel_w = label_w + len(models) * cell_w
    width = left * 2 + len(COMPLEXITY_ORDER) * panel_w + (len(COMPLEXITY_ORDER) - 1) * gap
    height = top + len(methods) * cell_h + 54
    parts = svg_start(
        width,
        height,
        f"Human Scores by Diagram Complexity: {title_suffix}",
        "Average of median completeness, correctness, understandability, and terminology scores",
    )
    for p_idx, complexity in enumerate(COMPLEXITY_ORDER):
        x0 = left + p_idx * (panel_w + gap)
        parts.append(f'<text class="panel" x="{x0}" y="{top - 56}">{complexity.title()}</text>')
        for m_idx, model in enumerate(models):
            x = x0 + label_w + m_idx * cell_w + cell_w / 2
            add_text(parts, model.replace(" 7B Instruct", "").replace(" 8B Instruct", ""), x, top - 34, 12)
        for r_idx, method in enumerate(methods):
            y = top + r_idx * cell_h
            add_text(parts, method, x0 + label_w - 8, y + 15, 20, "end")
            for m_idx, model in enumerate(models):
                x = x0 + label_w + m_idx * cell_w
                value = avg.get((complexity, method, model))
                title_value = "" if value is None else str(value)
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{heat_color(value, 5)}" stroke="#fff"><title>{html.escape(method)} | {html.escape(model)} | {complexity}: {title_value}</title></rect>'
                )
                label = "" if value is None else fmt_num(value)
                parts.append(f'<text class="value" x="{x + cell_w / 2}" y="{y + 23}" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    output.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def human_average_bars(
    rows: list[dict[str, object]],
    output: Path,
    *,
    methods: list[str],
    title_suffix: str,
) -> None:
    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for row in rows:
        grouped[(row["complexity"], row["method"], row["model"])].append(float(row["median_score"]))
    values = {
        key: round(sum(vals) / len(vals), 2)
        for key, vals in grouped.items()
        if vals
    }
    methods = selected_methods({key[1] for key in values}, methods)
    models = ordered({key[2] for key in values}, MODEL_ORDER)
    panel_w = 760
    width = 80 + panel_w * len(COMPLEXITY_ORDER)
    height = 660
    ml, mr, mt, mb = 70, 42, 100, 178
    plot_h = height - mt - mb
    panel_gap = 34
    inner_w = panel_w - panel_gap
    method_gap = 18
    method_w = (inner_w - method_gap * (len(methods) - 1)) / max(1, len(methods))
    bar_gap = 8
    bar_w = max(10, (method_w - bar_gap * (len(models) - 1)) / max(1, len(models)))
    parts = svg_start(
        width,
        height,
        f"Average Human Score by Complexity and Method: {title_suffix}",
        "Average of median human scores; panels are diagram complexity, bars are LLMs",
    )

    def y_for(v: float) -> float:
        return mt + plot_h - ((v - 1) / 4 * plot_h)

    for tick in [1, 2, 3, 4, 5]:
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y}" x2="{width - mr}" y2="{y}"/>')
        parts.append(f'<text class="tick" x="{ml - 10}" y="{y + 4}" text-anchor="end">{tick}</text>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}"/>')

    for c_idx, complexity in enumerate(COMPLEXITY_ORDER):
        panel_x = ml + c_idx * panel_w
        parts.append(f'<text class="panel" x="{panel_x}" y="{mt - 24}">{complexity.title()}</text>')
        parts.append(f'<line class="axis" x1="{panel_x}" y1="{mt + plot_h}" x2="{panel_x + inner_w}" y2="{mt + plot_h}"/>')
        for method_idx, method in enumerate(methods):
            x0 = panel_x + method_idx * (method_w + method_gap)
            for model_idx, model in enumerate(models):
                value = values.get((complexity, method, model))
                if value is None:
                    continue
                x = x0 + model_idx * (bar_w + bar_gap)
                y = y_for(value)
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{mt + plot_h - y:.1f}" fill="{PALETTE.get(model, "#777")}" rx="2">'
                    f'<title>{html.escape(complexity.title())} | {html.escape(method)} | {html.escape(model)}: {value:.2f}</title></rect>'
                )
                if bar_w >= 16:
                    parts.append(f'<text class="value" x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle">{value:.1f}</text>')
            add_text(parts, method, x0 + method_w / 2, mt + plot_h + 28, 14)

    lx, ly = ml, height - 48
    for model in models:
        parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{PALETTE.get(model, "#777")}" rx="2"/>')
        parts.append(f'<text class="legend" x="{lx + 20}" y="{ly + 12}">{html.escape(model)}</text>')
        lx += 210
    parts.append("</svg>")
    output.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    out = args.output_dir.resolve()
    charts = out / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    complexity_by_case = complexity_map()
    case_rows = [
        {"case_id": case_id, "complexity": complexity}
        for case_id, complexity in sorted(complexity_by_case.items())
    ]
    write_csv(out / "case_complexity_map.csv", case_rows)

    validation = validation_summary(complexity_by_case)
    human_long = human_rows(complexity_by_case)
    human = human_summary(human_long)
    compact = compact_table(validation, human)

    write_csv(out / "validation_by_complexity_model_method.csv", validation)
    write_csv(out / "human_scores_long_by_complexity.csv", human_long)
    write_csv(out / "human_scores_by_complexity_model_method.csv", human)
    write_csv(out / "complexity_summary_table.csv", compact)

    for old_name in [
        "validation_ratio_by_complexity_heatmap.svg",
        "human_score_by_complexity_heatmap.svg",
        "human_average_score_by_complexity_bars.svg",
    ]:
        old_path = charts / old_name
        if old_path.exists():
            old_path.unlink()

    validation_heatmap(
        validation,
        charts / "main_prompting_validation_ratio_by_complexity_heatmap.svg",
        methods=MAIN_PROMPTING_METHODS,
        title_suffix="Main Prompting",
    )
    human_heatmap(
        human,
        charts / "main_prompting_human_score_by_complexity_heatmap.svg",
        methods=MAIN_PROMPTING_METHODS,
        title_suffix="Main Prompting",
    )
    human_average_bars(
        human,
        charts / "main_prompting_human_average_score_by_complexity_bars.svg",
        methods=MAIN_PROMPTING_METHODS,
        title_suffix="Main Prompting",
    )

    validation_heatmap(
        validation,
        charts / "rag_ablation_validation_ratio_by_complexity_heatmap.svg",
        methods=RAG_ABLATION_METHODS,
        title_suffix="RAG Ablation",
    )
    human_heatmap(
        human,
        charts / "rag_ablation_human_score_by_complexity_heatmap.svg",
        methods=RAG_ABLATION_METHODS,
        title_suffix="RAG Ablation",
    )
    human_average_bars(
        human,
        charts / "rag_ablation_human_average_score_by_complexity_bars.svg",
        methods=RAG_ABLATION_METHODS,
        title_suffix="RAG Ablation",
    )

    print(f"wrote complexity tables and charts to: {out}")


if __name__ == "__main__":
    main()
