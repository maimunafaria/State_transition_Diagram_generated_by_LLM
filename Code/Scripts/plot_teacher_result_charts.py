#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "metrics"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "charts_teacher"

MODEL_ORDER = [
    "DeepSeek R1 14B",
    "Llama 3.1 8B Instruct",
    "Mistral",
    "Qwen 2.5 7B Instruct",
]
METHOD_ORDER = ["Zero-shot", "One-shot", "Few-shot", "RAG", "RAG + Repair"]
COMPLEXITY_ORDER = ["simple", "medium", "complex"]
METHOD_COLORS = {
    "Zero-shot": "#4E79A7",
    "One-shot": "#59A14F",
    "Few-shot": "#F28E2B",
    "RAG": "#76B7B2",
    "RAG + Repair": "#E15759",
}


def is_ensemble_row(row: dict[str, object]) -> bool:
    model = str(row.get("model", ""))
    method = str(row.get("method", ""))
    run_id = str(row.get("run_id", ""))
    return (
        model.lower().startswith("ensemble")
        or method == "Stacked Ensemble"
        or "ensemble" in run_id.lower()
    )


def read_summary(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed = {
                "model": row["model"],
                "method": row["method"],
                "total": int(row["total"]),
                "valid": int(row["valid"]),
                "invalid": int(row["invalid"]),
                "validity_percent": float(row["validity_percent"]),
            }
            if not is_ensemble_row(parsed):
                rows.append(parsed)
    return rows


def read_case_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed = {
                "model": row["model"],
                "method": row["method"],
                "run_id": row["run_id"],
                "case_id": row["case_id"],
                "valid": row["valid"].strip().lower() == "true",
            }
            if not is_ensemble_row(parsed):
                rows.append(parsed)
    return rows


def read_case_complexity(path: Path) -> dict[str, str]:
    complexity_by_case: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            case_id = row.get("case_id")
            complexity = row.get("complexity")
            if case_id and complexity:
                complexity_by_case[str(case_id)] = str(complexity).lower()
    return complexity_by_case


def ordered_models(rows: list[dict[str, object]]) -> list[str]:
    models = {str(row["model"]) for row in rows}
    ordered = [model for model in MODEL_ORDER if model in models]
    ordered.extend(sorted(models - set(ordered)))
    return ordered


def ordered_methods(rows: list[dict[str, object]]) -> list[str]:
    methods = {str(row["method"]) for row in rows}
    ordered = [method for method in METHOD_ORDER if method in methods]
    ordered.extend(sorted(methods - set(ordered)))
    return ordered


def percent(valid: int, total: int) -> float:
    return valid / total * 100.0 if total else 0.0


def build_difficulty_rows(
    case_rows: list[dict[str, object]],
    complexity_by_case: dict[str, str],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "valid": 0}
    )
    for row in case_rows:
        complexity = complexity_by_case.get(str(row["case_id"]))
        if complexity not in COMPLEXITY_ORDER:
            continue
        key = (str(row["model"]), str(row["method"]), complexity)
        grouped[key]["total"] += 1
        if row["valid"]:
            grouped[key]["valid"] += 1

    rows: list[dict[str, object]] = []
    models = ordered_models(case_rows)
    methods = ordered_methods(case_rows)
    for model in models:
        for method in methods:
            for complexity in COMPLEXITY_ORDER:
                counts = grouped.get((model, method, complexity), {"total": 0, "valid": 0})
                total = counts["total"]
                valid = counts["valid"]
                rows.append(
                    {
                        "model": model,
                        "method": method,
                        "complexity": complexity,
                        "total": total,
                        "valid": valid,
                        "invalid": total - valid,
                        "validity_percent": round(percent(valid, total), 2),
                    }
                )
    return rows


def write_difficulty_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "model",
                "method",
                "complexity",
                "total",
                "valid",
                "invalid",
                "validity_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def grouped_bar_svg(rows: list[dict[str, object]], title: str, subtitle: str) -> str:
    models = ordered_models(rows)
    methods = ordered_methods(rows)
    by_key = {(str(row["model"]), str(row["method"])): row for row in rows}

    width = max(1180, 250 * len(models) + 220)
    height = 620
    margin_left = 86
    margin_right = 34
    margin_top = 92
    margin_bottom = 130
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    group_gap = 34
    group_w = (plot_w - group_gap * (len(models) - 1)) / max(1, len(models))
    bar_gap = 7
    bar_w = (group_w - bar_gap * (len(methods) - 1)) / max(1, len(methods))

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / 100.0 * plot_h)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #333; stroke-width: 1.2; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #555; }",
        ".model { font-size: 13px; font-weight: 700; }",
        ".value { font-size: 11px; fill: #222; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="{margin_left}" y="34">{html.escape(title)}</text>',
        f'<text class="subtitle" x="{margin_left}" y="56">{html.escape(subtitle)}</text>',
    ]

    for tick in range(0, 101, 20):
        y = y_for(tick)
        parts.append(
            f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" '
            f'x2="{width - margin_right}" y2="{y:.1f}"/>'
        )
        parts.append(
            f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{tick}%</text>'
        )

    parts.append(
        f'<line class="axis" x1="{margin_left}" y1="{margin_top}" '
        f'x2="{margin_left}" y2="{margin_top + plot_h}"/>'
    )
    parts.append(
        f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" '
        f'x2="{width - margin_right}" y2="{margin_top + plot_h}"/>'
    )

    for model_index, model in enumerate(models):
        group_x = margin_left + model_index * (group_w + group_gap)
        for method_index, method in enumerate(methods):
            row = by_key.get((model, method))
            value = float(row["validity_percent"]) if row else 0.0
            total = int(row["total"]) if row else 0
            valid = int(row["valid"]) if row else 0
            x = group_x + method_index * (bar_w + bar_gap)
            y = y_for(value)
            bar_h = margin_top + plot_h - y
            color = METHOD_COLORS.get(method, "#888")
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="2" fill="{color}"><title>{html.escape(model)} | {html.escape(method)}: '
                f'{value:.2f}% ({valid}/{total})</title></rect>'
            )
            parts.append(
                f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 5, margin_top - 8):.1f}" '
                f'text-anchor="middle">{value:.0f}%</text>'
            )
        parts.append(
            f'<text class="model" x="{group_x + group_w / 2:.1f}" y="{margin_top + plot_h + 28}" '
            f'text-anchor="middle">{html.escape(model)}</text>'
        )

    legend_x = margin_left
    legend_y = height - 54
    cursor = legend_x
    for method in methods:
        color = METHOD_COLORS.get(method, "#888")
        parts.append(f'<rect x="{cursor}" y="{legend_y}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{cursor + 20}" y="{legend_y + 12}">{html.escape(method)}</text>')
        cursor += 20 + len(method) * 7 + 28

    parts.append("</svg>")
    return "\n".join(parts)


def difficulty_grouped_bar_svg(
    rows: list[dict[str, object]],
    title: str,
    subtitle: str,
) -> str:
    filtered = [row for row in rows if int(row["total"]) > 0]
    models = ordered_models(filtered)
    methods = ordered_methods(filtered)
    by_key = {
        (str(row["model"]), str(row["method"]), str(row["complexity"])): row
        for row in filtered
    }

    width = 1500
    height = 760
    margin_left = 86
    margin_right = 34
    margin_top = 96
    margin_bottom = 98
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    panel_gap = 52
    panel_w = (plot_w - panel_gap * (len(COMPLEXITY_ORDER) - 1)) / len(COMPLEXITY_ORDER)
    group_gap = 24
    group_w = (panel_w - group_gap * (len(models) - 1)) / max(1, len(models))
    bar_gap = 5
    bar_w = (group_w - bar_gap * (len(methods) - 1)) / max(1, len(methods))

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / 100.0 * plot_h)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #333; stroke-width: 1.1; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".tick { font-size: 11px; fill: #555; }",
        ".panel { font-size: 16px; font-weight: 700; }",
        ".model { font-size: 10px; font-weight: 700; }",
        ".value { font-size: 9px; fill: #222; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="{margin_left}" y="34">{html.escape(title)}</text>',
        f'<text class="subtitle" x="{margin_left}" y="56">{html.escape(subtitle)}</text>',
    ]

    for tick in range(0, 101, 20):
        y = y_for(tick)
        parts.append(
            f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{tick}%</text>'
        )

    for panel_index, complexity in enumerate(COMPLEXITY_ORDER):
        panel_x = margin_left + panel_index * (panel_w + panel_gap)
        parts.append(
            f'<text class="panel" x="{panel_x + panel_w / 2:.1f}" y="82" text-anchor="middle">'
            f'{html.escape(complexity.title())}</text>'
        )
        for tick in range(0, 101, 20):
            y = y_for(tick)
            parts.append(
                f'<line class="grid" x1="{panel_x}" y1="{y:.1f}" '
                f'x2="{panel_x + panel_w}" y2="{y:.1f}"/>'
            )
        parts.append(
            f'<line class="axis" x1="{panel_x}" y1="{margin_top}" x2="{panel_x}" y2="{margin_top + plot_h}"/>'
        )
        parts.append(
            f'<line class="axis" x1="{panel_x}" y1="{margin_top + plot_h}" '
            f'x2="{panel_x + panel_w}" y2="{margin_top + plot_h}"/>'
        )

        for model_index, model in enumerate(models):
            group_x = panel_x + model_index * (group_w + group_gap)
            for method_index, method in enumerate(methods):
                row = by_key.get((model, method, complexity))
                value = float(row["validity_percent"]) if row else 0.0
                total = int(row["total"]) if row else 0
                valid = int(row["valid"]) if row else 0
                x = group_x + method_index * (bar_w + bar_gap)
                y = y_for(value)
                bar_h = margin_top + plot_h - y
                color = METHOD_COLORS.get(method, "#888")
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                    f'rx="2" fill="{color}"><title>{html.escape(model)} | {html.escape(method)} | '
                    f'{html.escape(complexity)}: {value:.2f}% ({valid}/{total})</title></rect>'
                )
                if value > 0:
                    parts.append(
                        f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 4, margin_top - 7):.1f}" '
                        f'text-anchor="middle">{value:.0f}</text>'
                    )
            parts.append(
                f'<text class="model" x="{group_x + group_w / 2:.1f}" y="{margin_top + plot_h + 22}" '
                f'text-anchor="middle">{html.escape(model)}</text>'
            )

    cursor = margin_left
    legend_y = height - 42
    for method in methods:
        color = METHOD_COLORS.get(method, "#888")
        parts.append(f'<rect x="{cursor}" y="{legend_y}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{cursor + 20}" y="{legend_y + 12}">{html.escape(method)}</text>')
        cursor += 20 + len(method) * 7 + 28

    parts.append("</svg>")
    return "\n".join(parts)


def write_dashboard(output_dir: Path, chart_files: list[str]) -> None:
    cards = "\n".join(
        f'<section><h2>{html.escape(Path(filename).stem.replace("_", " ").title())}</h2>'
        f'<img src="{html.escape(filename)}" alt="{html.escape(filename)}"></section>'
        for filename in chart_files
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Teacher Result Charts</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; color: #222; }}
    h1 {{ margin-bottom: 4px; }}
    p {{ color: #555; }}
    section {{ margin: 28px 0 42px; }}
    img {{ max-width: 100%; border: 1px solid #ddd; }}
  </style>
</head>
<body>
  <h1>PlantUML LLM Result Charts</h1>
  <p>Generated without ensemble results.</p>
  {cards}
</body>
</html>
"""
    (output_dir / "teacher_result_dashboard.html").write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create simple teacher-facing bar charts without ensemble results."
    )
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    metrics_dir = args.metrics_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    state_summary_rows = read_summary(metrics_dir / "state_rules_validity_by_model_method.csv")
    structural_case_rows = read_case_rows(metrics_dir / "plantuml_validity_cases.csv")
    state_case_rows = read_case_rows(metrics_dir / "state_rules_validity_cases.csv")
    complexity_by_case = read_case_complexity(metrics_dir / "per_run_metrics.jsonl")
    state_difficulty_rows = build_difficulty_rows(state_case_rows, complexity_by_case)
    structural_difficulty_rows = build_difficulty_rows(structural_case_rows, complexity_by_case)
    write_difficulty_csv(
        state_difficulty_rows,
        output_dir / "teacher_difficulty_state_validity.csv",
    )
    write_difficulty_csv(
        structural_difficulty_rows,
        output_dir / "teacher_difficulty_structural_validity.csv",
    )

    charts = [
        (
            "teacher_state_rules_validity_by_model_method.svg",
            grouped_bar_svg(
                state_summary_rows,
                title="Strict UML State-Rule Validity by Model and Method",
                subtitle="Without ensemble results.",
            ),
        ),
        (
            "teacher_state_rules_validity_by_difficulty.svg",
            difficulty_grouped_bar_svg(
                state_difficulty_rows,
                title="State Validity by Diagram Difficulty Without Ensemble",
                subtitle="Grouped bars for simple, medium, and complex diagrams.",
            ),
        ),
        (
            "teacher_structural_validity_by_difficulty.svg",
            difficulty_grouped_bar_svg(
                structural_difficulty_rows,
                title="PlantUML Structural Validity by Diagram Difficulty Without Ensemble",
                subtitle="Grouped bars for simple, medium, and complex diagrams.",
            ),
        ),
    ]
    for filename, svg in charts:
        (output_dir / filename).write_text(svg, encoding="utf-8")

    write_dashboard(output_dir, [filename for filename, _ in charts])

    print(f"Wrote teacher bar charts to: {output_dir}")
    for filename, _ in charts:
        print(f"- {output_dir / filename}")
    print(f"- {output_dir / 'teacher_difficulty_state_validity.csv'}")
    print(f"- {output_dir / 'teacher_difficulty_structural_validity.csv'}")
    print(f"- {output_dir / 'teacher_result_dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
