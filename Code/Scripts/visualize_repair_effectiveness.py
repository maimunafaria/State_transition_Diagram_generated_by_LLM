#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "repair_effectiveness"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "charts"

METHOD_ORDER = ["Few-shot + Repair", "RAG + Repair"]
MODEL_ORDER = [
    "DeepSeek R1 14B",
    "Llama 3.1 8B Instruct",
    "Mistral",
    "Qwen 2.5 7B Instruct",
]
METHOD_COLORS = {
    "Few-shot + Repair": "#F28E2B",
    "RAG + Repair": "#76B7B2",
}
CHANGE_COLORS = {
    "mean_added_states": "#59A14F",
    "mean_deleted_states": "#E15759",
    "mean_added_transitions": "#4E79A7",
    "mean_deleted_transitions": "#B07AA1",
    "mean_modified_transition_labels": "#EDC948",
}

METRICS = {
    "success": ("repair_success_rate", "Repair Success Rate", "%"),
    "improvement": ("structural_improvement_rate", "Structural Improvement Rate", "%"),
    "recovery": ("validity_recovery_rate", "Validity Recovery Rate", "%"),
    "regression": ("regression_rate", "Regression Rate", "%"),
    "iterations": ("mean_attempted_repair_iterations", "Average Repair Iterations", ""),
    "change": ("mean_total_graph_change", "Minimality of Change: Mean Total Graph Change", ""),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ordered_methods(rows: list[dict[str, str]]) -> list[str]:
    methods = {row["method"] for row in rows}
    ordered = [method for method in METHOD_ORDER if method in methods]
    ordered.extend(sorted(methods - set(ordered)))
    return ordered


def ordered_models(rows: list[dict[str, str]]) -> list[str]:
    models = {row["model"] for row in rows if row.get("model")}
    ordered = [model for model in MODEL_ORDER if model in models]
    ordered.extend(sorted(models - set(ordered)))
    return ordered


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".axis { stroke: #333; stroke-width: 1.2; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".tick { font-size: 12px; fill: #555; }",
        ".label { font-size: 12px; fill: #222; }",
        ".value { font-size: 11px; fill: #222; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="70" y="34">{html.escape(title)}</text>',
        f'<text class="subtitle" x="70" y="56">{html.escape(subtitle)}</text>',
    ]


def max_axis(rows: list[dict[str, str]], value_col: str, suffix: str) -> float:
    if suffix == "%":
        return 100.0
    value = max(float(row[value_col]) for row in rows) if rows else 1.0
    return max(1.0, round(value + 0.75, 1))


def label_value(value: float, suffix: str) -> str:
    return f"{value:.1f}{suffix}" if suffix == "%" else f"{value:.2f}"


def add_legend(parts: list[str], labels: list[str], colors: dict[str, str], x: int, y: int) -> None:
    cursor = x
    for label in labels:
        color = colors.get(label, "#777")
        parts.append(f'<rect x="{cursor}" y="{y}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{cursor + 20}" y="{y + 12}">{html.escape(label)}</text>')
        cursor += 20 + len(label) * 7 + 30


def bar_svg(rows: list[dict[str, str]], value_col: str, title: str, suffix: str, scope: str) -> str:
    by_model = scope == "by-model"
    models = ordered_models(rows) if by_model else ["Overall"]
    methods = ordered_methods(rows)
    lookup = (
        {(row["model"], row["method"]): row for row in rows}
        if by_model
        else {("Overall", row["method"]): row for row in rows}
    )
    max_value = max_axis(rows, value_col, suffix)
    width = max(1040, 270 * len(models) + 160)
    height = 620
    ml, mr, mt, mb = 78, 34, 92, 122
    plot_w = width - ml - mr
    plot_h = height - mt - mb
    group_gap = 34
    group_w = (plot_w - group_gap * (len(models) - 1)) / max(1, len(models))
    bar_gap = 12
    bar_w = (group_w - bar_gap * (len(methods) - 1)) / max(1, len(methods))

    def y_for(value: float) -> float:
        return mt + plot_h - (value / max_value * plot_h)

    subtitle = "Grouped by LLM and repair strategy" if by_model else "Aggregated repair results"
    parts = svg_start(width, height, title, subtitle)
    for idx in range(6):
        tick = max_value * idx / 5
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{width - mr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml - 12}" y="{y + 4:.1f}" text-anchor="end">{label_value(tick, suffix)}</text>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt + plot_h}" x2="{width - mr}" y2="{mt + plot_h}"/>')

    for model_idx, model in enumerate(models):
        group_x = ml + model_idx * (group_w + group_gap)
        for method_idx, method in enumerate(methods):
            row = lookup.get((model, method))
            if not row:
                continue
            value = float(row[value_col])
            x = group_x + method_idx * (bar_w + bar_gap)
            y = y_for(value)
            color = METHOD_COLORS.get(method, "#777")
            label = label_value(value, suffix)
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{mt + plot_h - y:.1f}" rx="2" fill="{color}"><title>{html.escape(model)} | {html.escape(method)}: {label}</title></rect>')
            parts.append(f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 6, mt - 8):.1f}" text-anchor="middle">{label}</text>')
        parts.append(f'<text class="label" x="{group_x + group_w / 2:.1f}" y="{mt + plot_h + 28}" text-anchor="middle">{html.escape(model)}</text>')
    add_legend(parts, methods, METHOD_COLORS, ml, height - 56)
    parts.append("</svg>")
    return "\n".join(parts)


def heatmap_color(value: float, max_value: float, suffix: str) -> str:
    scale = 100.0 if suffix == "%" else max_value
    ratio = max(0.0, min(value / scale if scale else 0.0, 1.0))
    r = int(235 - ratio * 170)
    g = int(245 - ratio * 90)
    b = int(248 - ratio * 100)
    return f"#{r:02x}{g:02x}{b:02x}"


def heatmap_svg(rows: list[dict[str, str]], value_col: str, title: str, suffix: str, scope: str) -> str:
    by_model = scope == "by-model"
    methods = ordered_methods(rows)
    models = ordered_models(rows) if by_model else ["Overall"]
    lookup = (
        {(row["model"], row["method"]): row for row in rows}
        if by_model
        else {("Overall", row["method"]): row for row in rows}
    )
    max_value = max_axis(rows, value_col, suffix)
    cell_w, cell_h, label_w, header_h = 170, 56, 230, 104
    width = label_w + cell_w * len(methods) + 50
    height = header_h + cell_h * len(models) + 44
    parts = svg_start(width, height, title, "Cell values by LLM and repair strategy")
    for col, method in enumerate(methods):
        x = label_w + col * cell_w
        parts.append(f'<text class="label" x="{x + cell_w / 2:.1f}" y="88" text-anchor="middle">{html.escape(method)}</text>')
    for row_idx, model in enumerate(models):
        y = header_h + row_idx * cell_h
        parts.append(f'<text class="label" x="{label_w - 14}" y="{y + 35:.1f}" text-anchor="end">{html.escape(model)}</text>')
        for col, method in enumerate(methods):
            x = label_w + col * cell_w
            row = lookup.get((model, method))
            value = float(row[value_col]) if row else 0.0
            label = label_value(value, suffix)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{heatmap_color(value, max_value, suffix)}" stroke="#fff" stroke-width="2"><title>{html.escape(model)} | {html.escape(method)}: {label}</title></rect>')
            parts.append(f'<text class="value" x="{x + cell_w / 2:.1f}" y="{y + 34:.1f}" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def line_svg(rows: list[dict[str, str]], value_col: str, title: str, suffix: str, scope: str) -> str:
    models = ordered_models(rows)
    methods = ordered_methods(rows)
    lookup = {(row["model"], row["method"]): row for row in rows}
    max_value = max_axis(rows, value_col, suffix)
    width, height = 1040, 620
    ml, mr, mt, mb = 78, 46, 92, 122
    plot_w = width - ml - mr
    plot_h = height - mt - mb

    def x_for(idx: int) -> float:
        return ml + idx * plot_w / max(1, len(models) - 1)

    def y_for(value: float) -> float:
        return mt + plot_h - (value / max_value * plot_h)

    parts = svg_start(width, height, title, "Each line is a repair strategy across LLMs")
    for idx in range(6):
        tick = max_value * idx / 5
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{width - mr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml - 12}" y="{y + 4:.1f}" text-anchor="end">{label_value(tick, suffix)}</text>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt + plot_h}" x2="{width - mr}" y2="{mt + plot_h}"/>')
    for idx, model in enumerate(models):
        x = x_for(idx)
        parts.append(f'<text class="label" x="{x:.1f}" y="{mt + plot_h + 28}" text-anchor="middle">{html.escape(model)}</text>')
    for method in methods:
        points = []
        for idx, model in enumerate(models):
            row = lookup.get((model, method))
            if row:
                value = float(row[value_col])
                points.append((x_for(idx), y_for(value), value))
        color = METHOD_COLORS.get(method, "#777")
        parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y, value in points:
            label = label_value(value, suffix)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"><title>{html.escape(method)}: {label}</title></circle>')
            parts.append(f'<text class="value" x="{x:.1f}" y="{max(y - 10, mt - 8):.1f}" text-anchor="middle">{label}</text>')
    add_legend(parts, methods, METHOD_COLORS, ml, height - 56)
    parts.append("</svg>")
    return "\n".join(parts)


def minimality_stacked_svg(rows: list[dict[str, str]], scope: str) -> str:
    groups = (
        [(row["model"], row["method"]) for row in rows]
        if scope == "by-model"
        else [("Overall", row["method"]) for row in rows]
    )
    unique_groups = []
    seen = set()
    for group in groups:
        if group not in seen:
            seen.add(group)
            unique_groups.append(group)
    lookup = (
        {(row["model"], row["method"]): row for row in rows}
        if scope == "by-model"
        else {("Overall", row["method"]): row for row in rows}
    )
    components = list(CHANGE_COLORS)
    max_total = max(sum(float(lookup[group][component]) for component in components) for group in unique_groups)
    width = max(1120, 120 * len(unique_groups) + 220)
    height = 660
    ml, mr, mt, mb = 80, 40, 92, 170
    plot_w = width - ml - mr
    plot_h = height - mt - mb
    bar_gap = 18
    bar_w = (plot_w - bar_gap * (len(unique_groups) - 1)) / max(1, len(unique_groups))

    def y_for(value: float) -> float:
        return mt + plot_h - (value / max_total * plot_h)

    def group_label(group: tuple[str, str]) -> str:
        return group[1] if group[0] == "Overall" else f"{group[0]} | {group[1]}"

    parts = svg_start(width, height, "Minimality of Change Components", "Stacked mean graph-edit counts")
    for idx in range(6):
        tick = max_total * idx / 5
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y:.1f}" x2="{width - mr}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{ml - 12}" y="{y + 4:.1f}" text-anchor="end">{tick:.1f}</text>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt + plot_h}" x2="{width - mr}" y2="{mt + plot_h}"/>')
    for idx, group in enumerate(unique_groups):
        x = ml + idx * (bar_w + bar_gap)
        cumulative = 0.0
        row = lookup[group]
        for component in components:
            value = float(row[component])
            y_top = y_for(cumulative + value)
            y_bottom = y_for(cumulative)
            parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{y_bottom - y_top:.1f}" fill="{CHANGE_COLORS[component]}"><title>{html.escape(group_label(group))} | {component}: {value:.2f}</title></rect>')
            cumulative += value
        parts.append(f'<text class="label" x="{x + bar_w / 2:.1f}" y="{mt + plot_h + 18}" text-anchor="end" transform="rotate(-35 {x + bar_w / 2:.1f} {mt + plot_h + 18})">{html.escape(group_label(group))}</text>')
    add_legend(parts, components, CHANGE_COLORS, ml, height - 70)
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualize repair effectiveness metrics as SVG.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--chart-type", choices=["bar", "line", "heatmap", "minimality"], required=True)
    parser.add_argument(
        "--metric",
        choices=["success", "improvement", "recovery", "regression", "iterations", "change", "all"],
        default="all",
    )
    parser.add_argument("--scope", choices=["by-model"], default="by-model")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(input_dir / "repair_summary_by_model_method.csv")

    if args.chart_type == "minimality":
        svg = minimality_stacked_svg(rows, args.scope)
        output_path = output_dir / f"minimality_{args.scope}.svg"
        output_path.write_text(svg, encoding="utf-8")
        print(f"Wrote {output_path}")
        return 0

    metrics = list(METRICS) if args.metric == "all" else [args.metric]
    for metric in metrics:
        value_col, title, suffix = METRICS[metric]
        if args.chart_type == "bar":
            svg = bar_svg(rows, value_col, title, suffix, args.scope)
        elif args.chart_type == "line":
            svg = line_svg(rows, value_col, title, suffix, args.scope)
        else:
            svg = heatmap_svg(rows, value_col, title, suffix, args.scope)
        output_path = output_dir / f"{metric}_{args.scope}_{args.chart_type}.svg"
        output_path.write_text(svg, encoding="utf-8")
        print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
