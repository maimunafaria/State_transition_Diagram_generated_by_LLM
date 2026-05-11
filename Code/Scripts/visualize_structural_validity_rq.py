#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "rq_structural_validity"
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "charts"

METHOD_ORDER = [
    "Zero-shot",
    "Few-shot",
    "RAG",
    "RAG [examples only]",
    "RAG [rules only]",
    "RAG [theory only]",
]
MODEL_ORDER = [
    "DeepSeek R1 14B",
    "Llama 3.1 8B Instruct",
    "Mistral",
    "Qwen 2.5 7B Instruct",
]
METHOD_COLORS = {
    "Zero-shot": "#4E79A7",
    "Few-shot": "#F28E2B",
    "RAG": "#76B7B2",
    "RAG [examples only]": "#59A14F",
    "RAG [rules only]": "#EDC948",
    "RAG [theory only]": "#B07AA1",
}
VIOLATION_COLORS = {
    "missing_final_state": "#4E79A7",
    "missing_initial_state": "#F28E2B",
    "multiple_initial_states": "#E15759",
    "unreachable_states": "#76B7B2",
    "orphan_states": "#59A14F",
    "duplicate_transitions": "#B07AA1",
    "invalid_choice_node": "#EDC948",
    "invalid_choice_guards": "#FF9DA7",
    "invalid_fork_node": "#9C755F",
    "invalid_join_node": "#BAB0AC",
    "invalid_history_state": "#86BCB6",
    "parse_warning": "#8CD17D",
}

METRIC_CONFIG = {
    "plantuml": {
        "overall_file": "plantuml_syntax_validity_by_method.csv",
        "by_model_file": "plantuml_syntax_validity_by_model_method.csv",
        "value_col": "validity_percent",
        "title": "PlantUML Syntax Validity Rate",
        "y_label": "Validity (%)",
        "suffix": "%",
    },
    "structural": {
        "overall_file": "structural_validity_by_method_on_plantuml_valid.csv",
        "by_model_file": "structural_validity_by_model_method_on_plantuml_valid.csv",
        "value_col": "validity_percent",
        "title": "Structural Validity Rate on PlantUML-Valid Diagrams",
        "y_label": "Validity (%)",
        "suffix": "%",
    },
    "violations": {
        "overall_file": "violation_count_summary_by_method.csv",
        "by_model_file": "violation_count_summary_by_model_method.csv",
        "value_col": "mean_violations",
        "title": "Average Number of Structural Violations",
        "y_label": "Mean violations",
        "suffix": "",
    },
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


def nice_max(value: float, percentage: bool) -> float:
    if percentage:
        return 100.0
    if value <= 0:
        return 1.0
    if value <= 5:
        return round(value + 0.5, 1)
    return round(value + 1.0, 0)


def line_bar_common_svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
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


def grouped_bar_svg(
    rows: list[dict[str, str]],
    title: str,
    value_col: str,
    scope: str,
    suffix: str,
) -> str:
    by_model = scope == "by-model"
    methods = ordered_methods(rows)
    models = ordered_models(rows) if by_model else ["Overall"]
    percentage = suffix == "%"
    max_value = nice_max(max(float(row[value_col]) for row in rows), percentage)

    width = max(1040, 270 * len(models) + 160)
    height = 620
    margin_left = 78
    margin_right = 34
    margin_top = 92
    margin_bottom = 122
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    group_gap = 34
    group_w = (plot_w - group_gap * (len(models) - 1)) / max(1, len(models))
    bar_gap = 10
    bar_w = (group_w - bar_gap * (len(methods) - 1)) / max(1, len(methods))

    if by_model:
        lookup = {(row["model"], row["method"]): row for row in rows}
        subtitle = "Grouped by LLM and generation strategy"
    else:
        lookup = {("Overall", row["method"]): row for row in rows}
        subtitle = "Aggregated across all LLMs"

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / max_value * plot_h)

    parts = line_bar_common_svg_start(width, height, title, subtitle)
    tick_count = 5
    for idx in range(tick_count + 1):
        tick = max_value * idx / tick_count
        y = y_for(tick)
        label = f"{tick:.0f}{suffix}" if percentage else f"{tick:.1f}"
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{label}</text>')

    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}"/>')

    for model_index, model in enumerate(models):
        group_x = margin_left + model_index * (group_w + group_gap)
        for method_index, method in enumerate(methods):
            row = lookup.get((model, method))
            if not row:
                continue
            value = float(row[value_col])
            x = group_x + method_index * (bar_w + bar_gap)
            y = y_for(value)
            bar_h = margin_top + plot_h - y
            color = METHOD_COLORS.get(method, "#777")
            label = f"{value:.1f}{suffix}" if percentage else f"{value:.2f}"
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="2" fill="{color}"><title>{html.escape(model)} | {html.escape(method)}: {label}</title></rect>'
            )
            parts.append(f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 6, margin_top - 8):.1f}" text-anchor="middle">{label}</text>')
        parts.append(
            f'<text class="label" x="{group_x + group_w / 2:.1f}" y="{margin_top + plot_h + 28}" text-anchor="middle">'
            f"{html.escape(model)}</text>"
        )

    add_legend(parts, methods, margin_left, height - 56)
    parts.append("</svg>")
    return "\n".join(parts)


def line_svg(
    rows: list[dict[str, str]],
    title: str,
    value_col: str,
    scope: str,
    suffix: str,
) -> str:
    by_model = scope == "by-model"
    methods = ordered_methods(rows)
    models = ordered_models(rows) if by_model else ["Overall"]
    percentage = suffix == "%"
    max_value = nice_max(max(float(row[value_col]) for row in rows), percentage)

    width = max(1000, 170 * len(models) + 220)
    height = 620
    margin_left = 78
    margin_right = 46
    margin_top = 92
    margin_bottom = 122
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    step_x = plot_w / max(1, len(models) - 1)

    if by_model:
        lookup = {(row["model"], row["method"]): row for row in rows}
        subtitle = "Each line is a generation strategy across LLMs"
    else:
        lookup = {("Overall", row["method"]): row for row in rows}
        subtitle = "Aggregated across all LLMs"

    def x_for(index: int) -> float:
        return margin_left + index * step_x if len(models) > 1 else margin_left + plot_w / 2

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / max_value * plot_h)

    parts = line_bar_common_svg_start(width, height, title, subtitle)
    tick_count = 5
    for idx in range(tick_count + 1):
        tick = max_value * idx / tick_count
        y = y_for(tick)
        label = f"{tick:.0f}{suffix}" if percentage else f"{tick:.1f}"
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{label}</text>')

    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}"/>')

    for index, model in enumerate(models):
        x = x_for(index)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{margin_top + plot_h}"/>')
        parts.append(
            f'<text class="label" x="{x:.1f}" y="{margin_top + plot_h + 28}" text-anchor="middle">'
            f"{html.escape(model)}</text>"
        )

    for method in methods:
        points: list[tuple[float, float, float]] = []
        for index, model in enumerate(models):
            row = lookup.get((model, method))
            if row:
                value = float(row[value_col])
                points.append((x_for(index), y_for(value), value))
        if not points:
            continue
        color = METHOD_COLORS.get(method, "#777")
        point_text = " ".join(f"{x:.1f},{y:.1f}" for x, y, _value in points)
        parts.append(f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y, value in points:
            label = f"{value:.1f}{suffix}" if percentage else f"{value:.2f}"
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"><title>{html.escape(method)}: {label}</title></circle>')
            parts.append(f'<text class="value" x="{x:.1f}" y="{max(y - 10, margin_top - 8):.1f}" text-anchor="middle">{label}</text>')

    add_legend(parts, methods, margin_left, height - 56)
    parts.append("</svg>")
    return "\n".join(parts)


def add_legend(parts: list[str], methods: list[str], x: int, y: int) -> None:
    cursor = x
    for method in methods:
        color = METHOD_COLORS.get(method, "#777")
        parts.append(f'<rect x="{cursor}" y="{y}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(f'<text class="legend" x="{cursor + 20}" y="{y + 12}">{html.escape(method)}</text>')
        cursor += 20 + len(method) * 7 + 30


def heatmap_color(value: float, max_value: float, percentage: bool) -> str:
    scale_max = 100.0 if percentage else max_value
    ratio = max(0.0, min(value / scale_max if scale_max else 0.0, 1.0))
    # Light blue to deep teal.
    r = int(232 - ratio * 170)
    g = int(244 - ratio * 95)
    b = int(248 - ratio * 95)
    return f"#{r:02x}{g:02x}{b:02x}"


def heatmap_svg(
    rows: list[dict[str, str]],
    title: str,
    value_col: str,
    scope: str,
    suffix: str,
) -> str:
    by_model = scope == "by-model"
    methods = ordered_methods(rows)
    models = ordered_models(rows) if by_model else ["Overall"]
    lookup = (
        {(row["model"], row["method"]): row for row in rows}
        if by_model
        else {("Overall", row["method"]): row for row in rows}
    )
    percentage = suffix == "%"
    max_value = nice_max(max(float(row[value_col]) for row in rows), percentage)

    cell_w = 150
    cell_h = 56
    label_w = 230
    header_h = 104
    width = label_w + cell_w * len(methods) + 50
    height = header_h + cell_h * len(models) + 44

    subtitle = "Cell values by LLM and generation strategy" if by_model else "Overall strategy comparison"
    parts = line_bar_common_svg_start(width, height, title, subtitle)

    for col, method in enumerate(methods):
        x = label_w + col * cell_w
        parts.append(
            f'<text class="label" x="{x + cell_w / 2:.1f}" y="88" text-anchor="middle">'
            f"{html.escape(method)}</text>"
        )

    for row_idx, model in enumerate(models):
        y = header_h + row_idx * cell_h
        parts.append(f'<text class="label" x="{label_w - 14}" y="{y + 35:.1f}" text-anchor="end">{html.escape(model)}</text>')
        for col, method in enumerate(methods):
            x = label_w + col * cell_w
            row = lookup.get((model, method))
            value = float(row[value_col]) if row else 0.0
            label = f"{value:.1f}{suffix}" if percentage else f"{value:.2f}"
            fill = heatmap_color(value, max_value, percentage)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{fill}" '
                f'stroke="#fff" stroke-width="2"><title>{html.escape(model)} | {html.escape(method)}: {label}</title></rect>'
            )
            parts.append(f'<text class="value" x="{x + cell_w / 2:.1f}" y="{y + 34:.1f}" text-anchor="middle">{label}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def stacked_bar_svg(
    rows: list[dict[str, str]],
    title: str,
    scope: str,
) -> str:
    by_model = scope == "by-model"
    key_fields = ("model", "method") if by_model else ("method",)
    groups = []
    seen = set()
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        if key not in seen:
            seen.add(key)
            groups.append(key)

    def group_label(key: tuple[str, ...]) -> str:
        return f"{key[0]} | {key[1]}" if by_model else key[0]

    groups = sorted(
        groups,
        key=lambda key: (
            MODEL_ORDER.index(key[0]) if by_model and key[0] in MODEL_ORDER else 99,
            METHOD_ORDER.index(key[-1]) if key[-1] in METHOD_ORDER else 99,
            key,
        ),
    )
    types = sorted({row["violation_type"] for row in rows})
    totals = {
        key: sum(int(row["count"]) for row in rows if tuple(row[field] for field in key_fields) == key)
        for key in groups
    }
    max_total = max(totals.values()) if totals else 1

    width = max(1120, 82 * len(groups) + 220)
    height = 660
    margin_left = 80
    margin_right = 40
    margin_top = 92
    margin_bottom = 170
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    bar_gap = 10
    bar_w = (plot_w - bar_gap * (len(groups) - 1)) / max(1, len(groups))
    lookup = {
        (*tuple(row[field] for field in key_fields), row["violation_type"]): int(row["count"])
        for row in rows
    }

    subtitle = "Violation type distribution by LLM and strategy" if by_model else "Violation type distribution by strategy"
    parts = line_bar_common_svg_start(width, height, title, subtitle)

    def y_for(value: float) -> float:
        return margin_top + plot_h - (value / max_total * plot_h)

    for idx in range(6):
        tick = max_total * idx / 5
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{tick:.0f}</text>')

    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}"/>')

    for group_idx, key in enumerate(groups):
        x = margin_left + group_idx * (bar_w + bar_gap)
        cumulative = 0
        for violation in types:
            value = lookup.get((*key, violation), 0)
            if value == 0:
                continue
            y_top = y_for(cumulative + value)
            y_bottom = y_for(cumulative)
            fill = VIOLATION_COLORS.get(violation, "#888")
            parts.append(
                f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{y_bottom - y_top:.1f}" '
                f'fill="{fill}"><title>{html.escape(group_label(key))} | {html.escape(violation)}: {value}</title></rect>'
            )
            cumulative += value
        parts.append(
            f'<text class="label" x="{x + bar_w / 2:.1f}" y="{margin_top + plot_h + 18}" '
            f'text-anchor="end" transform="rotate(-38 {x + bar_w / 2:.1f} {margin_top + plot_h + 18})">'
            f"{html.escape(group_label(key))}</text>"
        )

    legend_x = margin_left
    legend_y = height - 70
    cursor_x = legend_x
    cursor_y = legend_y
    for violation in types:
        fill = VIOLATION_COLORS.get(violation, "#888")
        label_w = len(violation) * 7 + 44
        if cursor_x + label_w > width - margin_right:
            cursor_x = legend_x
            cursor_y += 22
        parts.append(f'<rect x="{cursor_x}" y="{cursor_y}" width="14" height="14" fill="{fill}" rx="2"/>')
        parts.append(f'<text class="legend" x="{cursor_x + 20}" y="{cursor_y + 12}">{html.escape(violation)}</text>')
        cursor_x += label_w

    parts.append("</svg>")
    return "\n".join(parts)


def render_chart(
    rows: list[dict[str, str]],
    chart_type: str,
    title: str,
    value_col: str,
    scope: str,
    suffix: str,
) -> str:
    if chart_type == "bar":
        return grouped_bar_svg(rows, title, value_col, scope, suffix)
    if chart_type == "line":
        return line_svg(rows, title, value_col, scope, suffix)
    if chart_type == "heatmap":
        return heatmap_svg(rows, title, value_col, scope, suffix)
    raise ValueError(f"Unsupported chart type: {chart_type}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualize structural-validity RQ results as SVG charts."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing CSV files produced by analyze_structural_validity_rq.py.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--chart-type",
        choices=["bar", "line", "heatmap", "stacked-bar"],
        required=True,
    )
    parser.add_argument(
        "--metric",
        choices=["plantuml", "structural", "violations", "violation-types", "all"],
        default="all",
    )
    parser.add_argument(
        "--scope",
        choices=["by-model"],
        default="by-model",
        help="Model-stratified values only.",
    )
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.chart_type == "stacked-bar" and args.metric not in {"violation-types", "all"}:
        raise ValueError("--chart-type stacked-bar is only supported with --metric violation-types or --metric all")

    metrics = list(METRIC_CONFIG) if args.metric == "all" else [args.metric]
    if args.chart_type == "stacked-bar" and args.metric == "all":
        metrics = ["violation-types"]

    for metric in metrics:
        if metric == "violation-types":
            filename = (
                "violation_type_distribution_by_model_method.csv"
                if args.scope == "by-model"
                else "violation_type_distribution_by_method.csv"
            )
            rows = read_csv(input_dir / filename)
            svg = stacked_bar_svg(
                rows=rows,
                title="Structural Violation Type Distribution",
                scope=args.scope,
            )
            output_path = output_dir / f"violation_types_{args.scope}_{args.chart_type}.svg"
            output_path.write_text(svg, encoding="utf-8")
            print(f"Wrote {output_path}")
            continue

        if args.chart_type == "stacked-bar":
            continue

        config = METRIC_CONFIG[metric]
        file_key = "by_model_file" if args.scope == "by-model" else "overall_file"
        rows = read_csv(input_dir / config[file_key])
        svg = render_chart(
            rows=rows,
            chart_type=args.chart_type,
            title=config["title"],
            value_col=config["value_col"],
            scope=args.scope,
            suffix=config["suffix"],
        )
        output_path = output_dir / f"{metric}_{args.scope}_{args.chart_type}.svg"
        output_path.write_text(svg, encoding="utf-8")
        print(f"Wrote {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
