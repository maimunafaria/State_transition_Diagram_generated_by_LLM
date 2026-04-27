#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "metrics"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "charts"
DEFAULT_ENSEMBLE_RUNS_DIR = (
    PROJECT_ROOT
    / "results"
    / "plantuml_pipeline"
    / "ensemble_stacked_llm"
    / "runs"
)
DEFAULT_ENSEMBLE_RUN_SPECS = [
    (
        "Ensemble Qwen 14B",
        PROJECT_ROOT / "results" / "plantuml_pipeline" / "ensemble_stacked_llm" / "runs",
    ),
    (
        "Ensemble Llama 8B",
        PROJECT_ROOT / "results" / "plantuml_pipeline" / "ensemble_stacked_llm_llama8b" / "runs",
    ),
]

MODEL_ORDER = [
    "DeepSeek R1 14B",
    "Llama 3.1 8B Instruct",
    "Qwen 2.5 7B Instruct",
    "Ensemble Qwen 14B",
    "Ensemble Llama 8B",
]
METHOD_ORDER = ["Zero-shot", "One-shot", "Few-shot", "RAG", "RAG + Repair", "Stacked Ensemble"]
METHOD_COLORS = {
    "Zero-shot": "#4E79A7",
    "One-shot": "#59A14F",
    "Few-shot": "#F28E2B",
    "RAG": "#76B7B2",
    "RAG + Repair": "#E15759",
    "Stacked Ensemble": "#7B61FF",
}


def read_summary(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "model": row["model"],
                    "method": row["method"],
                    "total": int(row["total"]),
                    "valid": int(row["valid"]),
                    "invalid": int(row["invalid"]),
                    "validity_percent": float(row["validity_percent"]),
                }
            )
    return rows


def read_ensemble_summary(
    ensemble_runs_dir: Path,
    model_label: str = "Ensemble",
) -> tuple[dict[str, object], dict[str, object]] | None:
    puml_files = sorted(ensemble_runs_dir.glob("*/*/ensemble.puml"))
    if not puml_files:
        return None

    sys.path.insert(0, str((PROJECT_ROOT / "Code" / "Scripts").resolve()))
    from plantuml_pipeline.parser import parse_and_validate_puml_text

    total = 0
    plantuml_valid = 0
    state_rules_valid = 0
    for puml_file in puml_files:
        _, validation = parse_and_validate_puml_text(puml_file.read_text(encoding="utf-8"))
        state_issues = list(validation.errors) + list(validation.warnings)
        total += 1
        if validation.valid:
            plantuml_valid += 1
        if validation.valid and not state_issues:
            state_rules_valid += 1

    def row(valid: int) -> dict[str, object]:
        return {
            "model": model_label,
            "method": "Stacked Ensemble",
            "total": total,
            "valid": valid,
            "invalid": total - valid,
            "validity_percent": round((valid / total * 100.0), 2) if total else 0.0,
        }

    return row(plantuml_valid), row(state_rules_valid)


def _ordered_models(rows: list[dict[str, object]]) -> list[str]:
    models = {str(row["model"]) for row in rows}
    ordered = [model for model in MODEL_ORDER if model in models]
    ordered.extend(sorted(models - set(ordered)))
    return ordered


def _ordered_methods(rows: list[dict[str, object]]) -> list[str]:
    methods = {str(row["method"]) for row in rows}
    ordered = [method for method in METHOD_ORDER if method in methods]
    ordered.extend(sorted(methods - set(ordered)))
    return ordered


def grouped_bar_svg(rows: list[dict[str, object]], title: str, subtitle: str) -> str:
    models = _ordered_models(rows)
    methods = _ordered_methods(rows)
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

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #333; stroke-width: 1.2; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #555; }",
        ".label { font-size: 12px; fill: #222; }",
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
        parts.append(f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{tick}%</text>')

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
            invalid = int(row["invalid"]) if row else 0
            x = group_x + method_index * (bar_w + bar_gap)
            y = y_for(value)
            bar_h = margin_top + plot_h - y
            color = METHOD_COLORS.get(method, "#888")
            tooltip = html.escape(
                f"{model} | {method}: {value:.2f}% ({valid} valid, {invalid} invalid, total {total})"
            )
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="2" fill="{color}"><title>{tooltip}</title></rect>'
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


def heatmap_svg(
    plantuml_rows: list[dict[str, object]],
    state_rows: list[dict[str, object]],
    title: str,
) -> str:
    models = _ordered_models(plantuml_rows + state_rows)
    methods = _ordered_methods(plantuml_rows + state_rows)
    plant_by_key = {(str(row["model"]), str(row["method"])): row for row in plantuml_rows}
    state_by_key = {(str(row["model"]), str(row["method"])): row for row in state_rows}

    cell_w = 146
    cell_h = 58
    label_w = 230
    header_h = 86
    width = label_w + cell_w * len(methods) + 40
    height = header_h + cell_h * len(models) + 70

    def color(value: float) -> str:
        # Red -> yellow -> green.
        if value < 50:
            ratio = value / 50.0
            r, g, b = 224, int(70 + ratio * 105), 70
        else:
            ratio = (value - 50) / 50.0
            r, g, b = int(245 - ratio * 100), 190, int(80 + ratio * 30)
        return f"#{r:02x}{g:02x}{b:02x}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 22px; font-weight: 700; }",
        ".method { font-size: 12px; font-weight: 700; }",
        ".model { font-size: 13px; font-weight: 700; }",
        ".metric { font-size: 12px; font-weight: 700; }",
        ".small { font-size: 10px; fill: #333; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="24" y="34">{html.escape(title)}</text>',
        '<text class="small" x="24" y="56">Top value: PlantUML syntax validity. Bottom value: strict state-rule validity.</text>',
    ]

    for method_index, method in enumerate(methods):
        x = label_w + method_index * cell_w + cell_w / 2
        parts.append(f'<text class="method" x="{x}" y="78" text-anchor="middle">{html.escape(method)}</text>')

    for model_index, model in enumerate(models):
        y = header_h + model_index * cell_h
        parts.append(f'<text class="model" x="24" y="{y + 34}">{html.escape(model)}</text>')
        for method_index, method in enumerate(methods):
            x = label_w + method_index * cell_w
            plant = float(plant_by_key.get((model, method), {}).get("validity_percent", 0.0))
            state = float(state_by_key.get((model, method), {}).get("validity_percent", 0.0))
            average = (plant + state) / 2.0
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w - 4}" height="{cell_h - 4}" '
                f'fill="{color(average)}" rx="4" opacity="0.95"/>'
            )
            parts.append(f'<text class="metric" x="{x + cell_w / 2}" y="{y + 23}" text-anchor="middle">P: {plant:.1f}%</text>')
            parts.append(f'<text class="metric" x="{x + cell_w / 2}" y="{y + 43}" text-anchor="middle">S: {state:.1f}%</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def write_html_dashboard(output_dir: Path, chart_files: list[str]) -> None:
    cards = "\n".join(
        f'<section><h2>{html.escape(Path(path).stem.replace("_", " ").title())}</h2>'
        f'<img src="{html.escape(path)}" alt="{html.escape(path)}"></section>'
        for path in chart_files
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Validity Charts</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 28px; color: #222; }}
    h1 {{ margin-bottom: 4px; }}
    p {{ color: #555; }}
    section {{ margin: 28px 0 42px; }}
    img {{ max-width: 100%; border: 1px solid #ddd; }}
  </style>
</head>
<body>
  <h1>PlantUML Validity Analysis</h1>
  <p>Generated from CSV files in results/plantuml_pipeline/metrics.</p>
  {cards}
</body>
</html>
"""
    (output_dir / "validity_dashboard.html").write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create SVG validity charts from metrics CSV files.")
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ensemble-runs-dir", type=Path, default=DEFAULT_ENSEMBLE_RUNS_DIR)
    parser.add_argument(
        "--ensemble-label",
        default="Ensemble",
        help="Label used when --ensemble-runs-dir is supplied.",
    )
    parser.add_argument(
        "--no-ensemble",
        action="store_true",
        help="Do not add the current stacked ensemble results to the charts.",
    )
    args = parser.parse_args()

    metrics_dir = args.metrics_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    plantuml_rows = read_summary(metrics_dir / "validity_by_model_method.csv")
    state_rows = read_summary(metrics_dir / "state_rules_validity_by_model_method.csv")
    if not args.no_ensemble:
        if args.ensemble_runs_dir == DEFAULT_ENSEMBLE_RUNS_DIR and args.ensemble_label == "Ensemble":
            ensemble_specs = DEFAULT_ENSEMBLE_RUN_SPECS
        else:
            ensemble_specs = [(args.ensemble_label, args.ensemble_runs_dir.resolve())]
        for ensemble_label, ensemble_runs_dir in ensemble_specs:
            ensemble_summary = read_ensemble_summary(
                Path(ensemble_runs_dir).resolve(),
                model_label=ensemble_label,
            )
            if ensemble_summary:
                ensemble_plantuml_row, ensemble_state_row = ensemble_summary
                plantuml_rows.append(ensemble_plantuml_row)
                state_rows.append(ensemble_state_row)

    chart_specs = [
        (
            "plantuml_validity_by_model_method.svg",
            grouped_bar_svg(
                plantuml_rows,
                title="PlantUML Render/Syntax Validity by Model and Method",
                subtitle="Percentage of final diagrams accepted by PlantUML syntax checking.",
            ),
        ),
        (
            "state_rules_validity_by_model_method.svg",
            grouped_bar_svg(
                state_rows,
                title="Strict UML State-Rule Validity by Model and Method",
                subtitle="Percentage of final diagrams with no PlantUML errors and no state-rule warnings.",
            ),
        ),
        (
            "validity_heatmap.svg",
            heatmap_svg(
                plantuml_rows,
                state_rows,
                title="Combined Validity Heatmap",
            ),
        ),
    ]
    for filename, svg in chart_specs:
        (output_dir / filename).write_text(svg, encoding="utf-8")

    write_html_dashboard(output_dir, [filename for filename, _ in chart_specs])

    print(f"Wrote charts to: {output_dir}")
    for filename, _ in chart_specs:
        print(f"- {output_dir / filename}")
    print(f"- {output_dir / 'validity_dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
