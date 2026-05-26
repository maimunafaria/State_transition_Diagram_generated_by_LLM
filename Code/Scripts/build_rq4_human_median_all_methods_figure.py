"""Build an RQ4 human-evaluation figure for all evaluated methods.

This keeps the four-panel layout from the Few-shot vs RAG figure, but includes
One-shot, Few-shot, RAG, and Repair for each model.
"""

from __future__ import annotations

import csv
import html
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results" / "human_evaluation_likert" / "method_llm_result_matrix_median_iqr.csv"
OUT_DIR = ROOT / "results" / "human_evaluation_likert" / "charts_summary"
OUT_CSV = OUT_DIR / "rq4_human_median_all_methods_by_model.csv"
OUT_N_CSV = OUT_DIR / "rq4_human_median_all_methods_sample_sizes.csv"
OUT_SVG = OUT_DIR / "rq4_human_median_all_methods_by_model.svg"
OUT_PNG = OUT_DIR / "rq4_human_median_all_methods_by_model.png"

METHODS = ["One-shot", "Few-shot", "RAG", "Repair"]
MODELS = ["Llama", "Mistral", "DeepSeek", "Qwen"]
CRITERIA = [
    "Completeness",
    "Correctness",
    "Understandability",
    "Terminology alignment",
]
COLORS = {
    "One-shot": "#4E79A7",
    "Few-shot": "#F28E2B",
    "RAG": "#59A14F",
    "Repair": "#E15759",
}


def parse_median_n(value: str) -> tuple[float | None, int | None]:
    if not value.strip():
        return None, None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s+\([^)]+\),\s*n=([0-9]+)\s*$", value)
    if not match:
        raise ValueError(f"Cannot parse median/IQR value: {value!r}")
    return float(match.group(1)), int(match.group(2))


def load_rows() -> list[dict[str, object]]:
    with INPUT.open(encoding="utf-8", newline="") as file:
        source_rows = list(csv.DictReader(file))

    long_rows: list[dict[str, object]] = []
    for row in source_rows:
        if row["Evaluation group"] != "Human Likert (1-5)" or row["Metric"] not in CRITERIA:
            continue
        criterion = row["Metric"]
        for method in METHODS:
            for model in MODELS:
                median, n = parse_median_n(row[f"{method} | {model}"])
                long_rows.append(
                    {
                        "criterion": criterion,
                        "method": method,
                        "model": model,
                        "median_likert_score": median,
                        "n": n,
                    }
                )
    return long_rows


def write_csv(rows: list[dict[str, object]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    n_rows = [
        {
            "criterion": row["criterion"],
            "method": row["method"],
            "model": row["model"],
            "n": row["n"],
        }
        for row in rows
    ]
    with OUT_N_CSV.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(n_rows[0]))
        writer.writeheader()
        writer.writerows(n_rows)


def text(
    x: float,
    y: float,
    content: object,
    size: int = 13,
    weight: str = "400",
    anchor: str = "start",
    fill: str = "#1f2933",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="{fill}">{html.escape(str(content))}</text>'
    )


def render_svg(rows: list[dict[str, object]]) -> None:
    by_key = {
        (str(row["criterion"]), str(row["method"]), str(row["model"])): row
        for row in rows
    }
    width = 1900
    height = 1320
    margin_left = 90
    panel_w = 820
    panel_h = 390
    gap_x = 80
    gap_y = 116
    top = 148
    lefts = [margin_left, margin_left + panel_w + gap_x]
    tops = [top, top + panel_h + gap_y]
    plot_left_pad = 56
    plot_right_pad = 22
    plot_top_pad = 48
    plot_bottom_pad = 54

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(40, 42, "Human evaluation median Likert scores across prompting methods", 24, "700"),
        text(
            40,
            72,
            "Grouped by model and evaluation dimension; bars show median human scores on the 1-5 Likert scale.",
            15,
            "400",
            fill="#52606d",
        ),
    ]

    legend_x = 40
    for idx, method in enumerate(METHODS):
        x = legend_x + idx * 150
        parts.append(f'<rect x="{x}" y="100" width="18" height="18" rx="3" fill="{COLORS[method]}"/>')
        parts.append(text(x + 26, 115, method, 13, "600"))

    for c_idx, criterion in enumerate(CRITERIA):
        col = c_idx % 2
        row_idx = c_idx // 2
        x0 = lefts[col]
        y0 = tops[row_idx]
        plot_x0 = x0 + plot_left_pad
        plot_y0 = y0 + plot_top_pad
        plot_w = panel_w - plot_left_pad - plot_right_pad
        plot_h = panel_h - plot_top_pad - plot_bottom_pad
        baseline = plot_y0 + plot_h

        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{panel_w}" height="{panel_h}" '
            'fill="#ffffff" stroke="#d9e2ec" stroke-width="1"/>'
        )
        parts.append(text(x0 + 16, y0 + 24, criterion, 16, "700"))

        for tick in range(0, 6):
            y = baseline - (tick / 5) * plot_h
            stroke = "#d9e2ec" if tick else "#9fb3c8"
            parts.append(
                f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x0 + plot_w}" y2="{y:.1f}" '
                f'stroke="{stroke}" stroke-width="1"/>'
            )
            parts.append(text(plot_x0 - 10, y + 4, tick, 12, anchor="end", fill="#52606d"))

        group_w = plot_w / len(MODELS)
        bar_w = 20
        bar_gap = 5
        total_bar_w = (bar_w * len(METHODS)) + (bar_gap * (len(METHODS) - 1))
        for m_idx, model in enumerate(MODELS):
            center = plot_x0 + group_w * m_idx + group_w / 2
            start_x = center - total_bar_w / 2
            for method_idx, method in enumerate(METHODS):
                item = by_key[(criterion, method, model)]
                score = float(item["median_likert_score"])
                n = int(item["n"])
                x = start_x + method_idx * (bar_w + bar_gap)
                bar_h = (score / 5) * plot_h
                y = baseline - bar_h
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
                    f'fill="{COLORS[method]}" rx="2"/>'
                )
                parts.append(text(x + bar_w / 2, y - 6, f"{score:g}", 10, "700", "middle"))
            parts.append(text(center, baseline + 23, model, 12, "700", "middle"))

        parts.append(text(x0 + 14, y0 + panel_h - 12, "Median score", 11, fill="#627d98"))

    table_x = 90
    table_y = 1080
    cell_w = 150
    cell_h = 34
    first_col_w = 140
    table_rows = ["Llama", "Mistral", "DeepSeek", "Qwen"]
    n_lookup = {
        (str(row["model"]), str(row["method"])): int(row["n"])
        for row in rows
        if str(row["criterion"]) == "Completeness"
    }
    parts.append(text(table_x, table_y - 22, "Sample sizes (n), same across the four quality dimensions", 15, "700"))
    parts.append(
        f'<rect x="{table_x}" y="{table_y}" width="{first_col_w + cell_w * len(METHODS)}" '
        f'height="{cell_h * (len(table_rows) + 1)}" fill="#ffffff" stroke="#d9e2ec" stroke-width="1"/>'
    )
    parts.append(text(table_x + 14, table_y + 23, "Model", 12, "700"))
    for idx, method in enumerate(METHODS):
        x = table_x + first_col_w + idx * cell_w
        parts.append(f'<line x1="{x}" y1="{table_y}" x2="{x}" y2="{table_y + cell_h * (len(table_rows) + 1)}" stroke="#d9e2ec"/>')
        parts.append(text(x + cell_w / 2, table_y + 23, method, 12, "700", "middle"))
    parts.append(f'<line x1="{table_x}" y1="{table_y + cell_h}" x2="{table_x + first_col_w + cell_w * len(METHODS)}" y2="{table_y + cell_h}" stroke="#d9e2ec"/>')
    for row_idx, model in enumerate(table_rows):
        y = table_y + cell_h * (row_idx + 1)
        parts.append(f'<line x1="{table_x}" y1="{y + cell_h}" x2="{table_x + first_col_w + cell_w * len(METHODS)}" y2="{y + cell_h}" stroke="#eef2f7"/>')
        parts.append(text(table_x + 14, y + 23, model, 12, "600"))
        for method_idx, method in enumerate(METHODS):
            x = table_x + first_col_w + method_idx * cell_w
            parts.append(text(x + cell_w / 2, y + 23, n_lookup[(model, method)], 12, "600", "middle", "#334e68"))

    parts.append("</svg>")
    OUT_SVG.write_text("\n".join(parts), encoding="utf-8")


def convert_png() -> None:
    subprocess.run(
        ["rsvg-convert", "-f", "png", "-o", str(OUT_PNG), str(OUT_SVG)],
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> None:
    rows = load_rows()
    write_csv(rows)
    render_svg(rows)
    convert_png()
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_N_CSV}")
    print(f"Wrote {OUT_SVG}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
