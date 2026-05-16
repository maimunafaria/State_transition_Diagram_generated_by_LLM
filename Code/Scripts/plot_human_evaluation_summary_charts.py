#!/usr/bin/env python3
"""Create SVG charts for human-evaluation and automatic-validity summary tables.

The script reads the compact `exact_*_with_n.csv` result tables and writes
publication-friendly SVG charts plus long-form chart data CSVs.

Outputs:
  results/human_evaluation_likert/charts_summary/*.svg
  results/human_evaluation_likert/charts_summary/*.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HUMAN_DIR = ROOT / "results" / "human_evaluation_likert"
DEFAULT_OUT = HUMAN_DIR / "charts_summary"

METRIC_ORDER = [
    "Completeness",
    "Correctness",
    "Understandability",
    "Terminology alignment",
]

MODEL_ORDER = ["llama", "mistral", "deepseek", "qwen"]
MODEL_LABEL = {
    "llama": "Llama",
    "mistral": "Mistral",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
}

PROMPT_METHOD_ORDER = ["Zero-shot", "One-shot", "Few-shot", "RAG"]
RAG_METHOD_ORDER = [
    "Rag (fully)",
    "Rag (only rules)",
    "Rag (only example)",
    "Rag (only theory)",
]
REPAIR_ITERATION_ORDER = [
    "Repair at zero iterations",
    "Repair at once",
    "Repair at two iterations",
    "Repair at three iterations",
    "Repair at four iterations",
    "Repair at five iterations",
]
REPAIR_ITERATION_BAR_ORDER = [
    "Repair at once",
    "Repair at two iterations",
    "Repair at three iterations",
    "Repair at four iterations",
    "Repair at five iterations",
]

PALETTE = {
    "llama": "#4E79A7",
    "mistral": "#F28E2B",
    "deepseek": "#59A14F",
    "qwen": "#E15759",
    "structural": "#4E79A7",
    "syntactic": "#E15759",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_value(text: str) -> tuple[float | None, int | None, int | None]:
    """Return numeric score/percent plus n numerator and denominator if present."""
    text = (text or "").strip()
    if not text:
        return None, None, None
    value_match = re.match(r"(-?\d+(?:\.\d+)?)%?", text)
    value = float(value_match.group(1)) if value_match else None
    n_match = re.search(r"n=(\d+)(?:/(\d+))?", text)
    if not n_match:
        return value, None, None
    numerator = int(n_match.group(1))
    denominator = int(n_match.group(2)) if n_match.group(2) else None
    return value, numerator, denominator


def split_col(col: str) -> tuple[str, str]:
    if " | " not in col:
        return col, ""
    method, model = col.split(" | ", 1)
    return method.strip(), model.strip().lower()


def table_to_long(path: Path, table_name: str) -> list[dict[str, object]]:
    rows = read_csv(path)
    out: list[dict[str, object]] = []
    for row in rows:
        group = row["Evaluation group"]
        metric = row["Metric"]
        for col, cell in row.items():
            if col in {"Evaluation group", "Metric"}:
                continue
            method, model = split_col(col)
            value, n, total = parse_value(cell)
            out.append(
                {
                    "table": table_name,
                    "evaluation_group": group,
                    "metric": metric,
                    "method": method,
                    "model": model,
                    "value": "" if value is None else value,
                    "n": "" if n is None else n,
                    "total": "" if total is None else total,
                    "raw": cell,
                }
            )
    return out


def order_items(items: set[str], preferred: list[str]) -> list[str]:
    ordered = [item for item in preferred if item in items]
    ordered.extend(sorted(items - set(ordered)))
    return ordered


def svg_frame(width: int, height: int, title: str, subtitle: str = "") -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>",
        "text { font-family: Arial, Helvetica, sans-serif; fill: #222; }",
        ".title { font-size: 24px; font-weight: 700; }",
        ".subtitle { font-size: 13px; fill: #555; }",
        ".panel { font-size: 15px; font-weight: 700; }",
        ".axis { stroke: #333; stroke-width: 1.2; }",
        ".grid { stroke: #ddd; stroke-width: 1; }",
        ".label { font-size: 12px; }",
        ".tick { font-size: 11px; fill: #555; }",
        ".value { font-size: 11px; font-weight: 700; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="40" y="34">{html.escape(title)}</text>',
        f'<text class="subtitle" x="40" y="56">{html.escape(subtitle)}</text>' if subtitle else "",
    ]


def text_width(text: str, char_px: float = 7.0) -> float:
    return len(text) * char_px


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
    if not lines:
        return [text]
    return lines


def add_wrapped_text(
    parts: list[str],
    text: str,
    *,
    x: float,
    y: float,
    max_chars: int,
    class_name: str = "label",
    anchor: str = "middle",
    line_h: int = 14,
) -> None:
    lines = wrap_label(text, max_chars=max_chars)
    for idx, line in enumerate(lines):
        parts.append(
            f'<text class="{class_name}" x="{x:.1f}" y="{y + idx * line_h:.1f}" text-anchor="{anchor}">{html.escape(line)}</text>'
        )


def score_color(value: float | None) -> str:
    if value is None:
        return "#f2f2f2"
    ratio = max(0.0, min((value - 1.0) / 4.0, 1.0))
    r = int(238 - 125 * ratio)
    g = int(245 - 40 * ratio)
    b = int(248 - 130 * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def heatmap_panels(
    rows: list[dict[str, object]],
    *,
    title: str,
    subtitle: str,
    methods: list[str],
    models: list[str],
    output_path: Path,
) -> None:
    lookup = {
        (str(r["method"]), str(r["model"]), str(r["metric"])): r
        for r in rows
        if r["evaluation_group"] == "Human (Likert scale 1-5)"
    }
    cell_w = 102
    cell_h = 42
    metric_w = 168
    panel_gap = 42
    top = 122
    left = 40
    panel_w = metric_w + len(models) * cell_w
    width = left * 2 + len(methods) * panel_w + (len(methods) - 1) * panel_gap
    height = top + 34 + len(METRIC_ORDER) * cell_h + 74
    parts = svg_frame(width, height, title, subtitle)

    for p_idx, method in enumerate(methods):
        x0 = left + p_idx * (panel_w + panel_gap)
        add_wrapped_text(parts, method, x=x0, y=top - 54, max_chars=22, class_name="panel", anchor="start", line_h=16)
        for m_idx, model in enumerate(models):
            x = x0 + metric_w + m_idx * cell_w
            parts.append(f'<text class="label" x="{x + cell_w / 2}" y="{top - 18}" text-anchor="middle">{html.escape(MODEL_LABEL.get(model, model))}</text>')
        for r_idx, metric in enumerate(METRIC_ORDER):
            y = top + r_idx * cell_h
            parts.append(f'<text class="label" x="{x0 + metric_w - 8}" y="{y + 26}" text-anchor="end">{html.escape(metric)}</text>')
            for m_idx, model in enumerate(models):
                x = x0 + metric_w + m_idx * cell_w
                item = lookup.get((method, model, metric))
                value = float(item["value"]) if item and item["value"] != "" else None
                raw = str(item["raw"]) if item else ""
                fill = score_color(value)
                parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{fill}" stroke="#fff"><title>{html.escape(method)} | {MODEL_LABEL.get(model, model)} | {metric}: {html.escape(raw)}</title></rect>')
                label = "" if value is None else f"{value:g}"
                n_label = "" if not item or item["n"] == "" else f"n={item['n']}"
                parts.append(f'<text class="value" x="{x + cell_w / 2}" y="{y + 20}" text-anchor="middle">{label}</text>')
                parts.append(f'<text class="tick" x="{x + cell_w / 2}" y="{y + 34}" text-anchor="middle">{n_label}</text>')
    parts.append('<text class="tick" x="40" y="{}">Darker cells indicate higher median Likert score.</text>'.format(height - 20))
    parts.append("</svg>")
    output_path.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def average_scores(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        if r["evaluation_group"] != "Human (Likert scale 1-5)" or r["value"] == "":
            continue
        grouped[(str(r["method"]), str(r["model"]))].append(float(r["value"]))
    out = []
    for (method, model), vals in sorted(grouped.items()):
        if vals:
            out.append({"method": method, "model": model, "average_score": round(sum(vals) / len(vals), 4)})
    return out


def grouped_bar_average(
    avg_rows: list[dict[str, object]],
    *,
    title: str,
    subtitle: str,
    methods: list[str],
    models: list[str],
    output_path: Path,
) -> None:
    lookup = {(str(r["method"]), str(r["model"])): float(r["average_score"]) for r in avg_rows}
    group_w_target = 210
    width = max(1120, 140 + group_w_target * len(methods))
    height = 620
    ml, mr, mt, mb = 78, 48, 92, 178
    plot_w = width - ml - mr
    plot_h = height - mt - mb
    group_gap = 48
    group_w = (plot_w - group_gap * (len(methods) - 1)) / max(1, len(methods))
    bar_gap = 8
    bar_w = max(14, (group_w - bar_gap * (len(models) - 1)) / max(1, len(models)))

    def y_for(value: float) -> float:
        return mt + plot_h - ((value - 1) / 4 * plot_h)

    parts = svg_frame(width, height, title, subtitle)
    for tick in [1, 2, 3, 4, 5]:
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{ml}" y1="{y}" x2="{width - mr}" y2="{y}"/>')
        parts.append(f'<text class="tick" x="{ml - 12}" y="{y + 4}" text-anchor="end">{tick}</text>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{ml}" y1="{mt + plot_h}" x2="{width - mr}" y2="{mt + plot_h}"/>')

    for g_idx, method in enumerate(methods):
        x0 = ml + g_idx * (group_w + group_gap)
        for m_idx, model in enumerate(models):
            value = lookup.get((method, model))
            if value is None:
                continue
            x = x0 + m_idx * (bar_w + bar_gap)
            y = y_for(value)
            color = PALETTE.get(model, "#777")
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{mt + plot_h - y:.1f}" fill="{color}" rx="2"><title>{html.escape(method)} | {MODEL_LABEL.get(model, model)} average: {value:.2f}</title></rect>')
            parts.append(f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 6, mt - 8):.1f}" text-anchor="middle">{value:.2f}</text>')
        add_wrapped_text(
            parts,
            method,
            x=x0 + group_w / 2,
            y=mt + plot_h + 30,
            max_chars=18,
            class_name="label",
            anchor="middle",
            line_h=14,
        )

    lx = ml
    ly = height - 56
    for model in models:
        parts.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{PALETTE.get(model, "#777")}" rx="2"/>')
        parts.append(f'<text class="legend" x="{lx + 20}" y="{ly + 12}">{html.escape(MODEL_LABEL.get(model, model))}</text>')
        lx += max(116, int(text_width(MODEL_LABEL.get(model, model))) + 46)
    parts.append("</svg>")
    output_path.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def percent_color(value: float | None) -> str:
    if value is None:
        return "#f2f2f2"
    ratio = max(0.0, min(value / 100.0, 1.0))
    r = int(242 - 145 * ratio)
    g = int(246 - 70 * ratio)
    b = int(248 - 80 * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def automatic_validity_heatmap(
    rows: list[dict[str, object]],
    *,
    title: str,
    subtitle: str,
    methods: list[str],
    models: list[str],
    output_path: Path,
) -> None:
    metrics = ["Structural validity", "Syntactic validity"]
    lookup = {
        (str(r["method"]), str(r["model"]), str(r["metric"])): r
        for r in rows
        if r["evaluation_group"] == "Automatic (accuracy)"
    }
    cell_w = 102
    cell_h = 40
    label_w = 142
    panel_gap = 42
    top = 122
    left = 40
    panel_w = label_w + len(models) * cell_w
    width = left * 2 + len(methods) * panel_w + (len(methods) - 1) * panel_gap
    height = top + len(metrics) * cell_h + 84
    parts = svg_frame(width, height, title, subtitle)
    for p_idx, method in enumerate(methods):
        x0 = left + p_idx * (panel_w + panel_gap)
        add_wrapped_text(parts, method, x=x0, y=top - 54, max_chars=22, class_name="panel", anchor="start", line_h=16)
        for m_idx, model in enumerate(models):
            x = x0 + label_w + m_idx * cell_w
            parts.append(f'<text class="label" x="{x + cell_w / 2}" y="{top - 18}" text-anchor="middle">{html.escape(MODEL_LABEL.get(model, model))}</text>')
        for r_idx, metric in enumerate(metrics):
            y = top + r_idx * cell_h
            parts.append(f'<text class="label" x="{x0 + label_w - 8}" y="{y + 25}" text-anchor="end">{html.escape(metric.replace(" validity", ""))}</text>')
            for m_idx, model in enumerate(models):
                x = x0 + label_w + m_idx * cell_w
                item = lookup.get((method, model, metric))
                value = float(item["value"]) if item and item["value"] != "" else None
                raw = str(item["raw"]) if item else ""
                parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{percent_color(value)}" stroke="#fff"><title>{html.escape(method)} | {MODEL_LABEL.get(model, model)} | {metric}: {html.escape(raw)}</title></rect>')
                label = "" if value is None else f"{value:.0f}%"
                parts.append(f'<text class="value" x="{x + cell_w / 2}" y="{y + 24}" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    output_path.write_text("\n".join(p for p in parts if p), encoding="utf-8")


def build_chart_set(table_path: Path, table_name: str, method_order: list[str], out_dir: Path, prefix: str) -> None:
    rows = table_to_long(table_path, table_name)
    write_csv(out_dir / f"{prefix}_long.csv", rows)
    human_methods = order_items({str(r["method"]) for r in rows}, method_order)
    models = order_items({str(r["model"]) for r in rows if r["model"]}, MODEL_ORDER)
    heatmap_panels(
        rows,
        title=f"{table_name}: Human Likert Scores",
        subtitle="Median score with sample size in each cell",
        methods=human_methods,
        models=models,
        output_path=out_dir / f"{prefix}_human_score_heatmap.svg",
    )
    avg = average_scores(rows)
    write_csv(out_dir / f"{prefix}_average_human_scores.csv", avg)
    bar_methods = REPAIR_ITERATION_BAR_ORDER if prefix == "repair_iterations" else human_methods
    grouped_bar_average(
        avg,
        title=f"{table_name}: Average Human Score",
        subtitle="Average of completeness, correctness, understandability, and terminology medians",
        methods=bar_methods,
        models=models,
        output_path=out_dir / f"{prefix}_average_human_score_bars.svg",
    )
    automatic_validity_heatmap(
        rows,
        title=f"{table_name}: Automatic Validity",
        subtitle="Structural and syntactic validity percentages",
        methods=human_methods,
        models=models,
        output_path=out_dir / f"{prefix}_automatic_validity_heatmap.svg",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--main-table",
        type=Path,
        default=HUMAN_DIR / "exact_zero_one_few_rag_table_score_only_with_n_from_xlsx.csv",
        help="Main Zero/One/Few/RAG table. Defaults to the workbook-updated table if present.",
    )
    args = parser.parse_args()

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    main_table = args.main_table
    if not main_table.exists():
        main_table = HUMAN_DIR / "exact_zero_one_few_rag_table_score_only_with_n.csv"

    chart_specs = [
        (main_table, "Prompting Strategy", PROMPT_METHOD_ORDER, "prompting_strategy"),
        (HUMAN_DIR / "exact_rag_ablation_table_score_only_with_n.csv", "RAG Ablation", RAG_METHOD_ORDER, "rag_ablation"),
        (HUMAN_DIR / "exact_repair_table_score_only_with_n.csv", "Repair", ["Repair"], "repair"),
        (
            HUMAN_DIR / "exact_repair_iterations_0_1_2_3_4_5_table_score_only_with_n.csv",
            "Repair Iterations",
            REPAIR_ITERATION_ORDER,
            "repair_iterations",
        ),
    ]
    for table_path, table_name, method_order, prefix in chart_specs:
        if table_path.exists():
            build_chart_set(table_path, table_name, method_order, out_dir, prefix)
        else:
            print(f"missing: {table_path}")

    print(f"wrote charts to: {out_dir}")


if __name__ == "__main__":
    main()
