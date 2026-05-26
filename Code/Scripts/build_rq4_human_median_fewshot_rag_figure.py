"""Build an RQ4 human-evaluation summary figure for Few-shot vs RAG.

The figure uses the exact median Likert score table already produced by the
human-evaluation pipeline and creates a compact grouped bar chart across models.
"""

from __future__ import annotations

import csv
import html
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results" / "human_evaluation_likert" / "exact_zero_one_few_rag_table_score_only_with_n.csv"
OUT_DIR = ROOT / "results" / "human_evaluation_likert" / "charts_summary"
OUT_CSV = OUT_DIR / "rq4_human_median_fewshot_rag_by_model.csv"
OUT_SVG = OUT_DIR / "rq4_human_median_fewshot_rag_by_model.svg"
OUT_PNG = OUT_DIR / "rq4_human_median_fewshot_rag_by_model.png"

METHODS = ["Few-shot", "RAG"]
MODELS = ["Llama", "Mistral", "DeepSeek", "Qwen"]
CRITERIA = [
    "Completeness",
    "Correctness",
    "Understandability",
    "Terminology alignment",
]
COLORS = {"Few-shot": "#4E79A7", "RAG": "#F28E2B"}


def parse_score_n(value: str) -> tuple[float | None, int | None]:
    if not value.strip():
        return None, None
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s+\(n=([0-9]+)\)\s*$", value)
    if not match:
        raise ValueError(f"Cannot parse score/n value: {value!r}")
    return float(match.group(1)), int(match.group(2))


def load_rows() -> list[dict[str, object]]:
    with INPUT.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    human_rows = [
        row
        for row in rows
        if row["Evaluation group"] == "Human (Likert scale 1-5)"
        and row["Metric"] in CRITERIA
    ]

    long_rows: list[dict[str, object]] = []
    for row in human_rows:
        criterion = row["Metric"]
        for method in METHODS:
            for model in MODELS:
                value, n = parse_score_n(row[f"{method} | {model}"])
                long_rows.append(
                    {
                        "criterion": criterion,
                        "method": method,
                        "model": model,
                        "median_likert_score": value,
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
    width = 1500
    height = 960
    margin_left = 90
    panel_w = 620
    panel_h = 330
    gap_x = 80
    gap_y = 92
    top = 112
    lefts = [margin_left, margin_left + panel_w + gap_x]
    tops = [top, top + panel_h + gap_y]
    plot_left_pad = 50
    plot_right_pad = 16
    plot_top_pad = 46
    plot_bottom_pad = 78

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(40, 42, "Human evaluation median Likert scores: Few-shot vs RAG", 22, "700"),
        text(
            40,
            70,
            "Grouped by model; bars show median human scores on the 1-5 Likert scale.",
            14,
            "400",
            fill="#52606d",
        ),
    ]

    legend_x = 835
    for idx, method in enumerate(METHODS):
        x = legend_x + idx * 140
        parts.append(f'<rect x="{x}" y="31" width="18" height="18" rx="3" fill="{COLORS[method]}"/>')
        parts.append(text(x + 26, 46, method, 13, "600"))

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
        parts.append(text(x0 + 16, y0 + 23, criterion, 15, "700"))

        for tick in range(0, 6):
            y = baseline - (tick / 5) * plot_h
            stroke = "#d9e2ec" if tick else "#9fb3c8"
            parts.append(
                f'<line x1="{plot_x0}" y1="{y:.1f}" x2="{plot_x0 + plot_w}" y2="{y:.1f}" '
                f'stroke="{stroke}" stroke-width="1"/>'
            )
            parts.append(text(plot_x0 - 10, y + 4, tick, 11, anchor="end", fill="#52606d"))

        group_w = plot_w / len(MODELS)
        bar_w = 30
        for m_idx, model in enumerate(MODELS):
            center = plot_x0 + group_w * m_idx + group_w / 2
            for method_idx, method in enumerate(METHODS):
                item = by_key[(criterion, method, model)]
                score = float(item["median_likert_score"])
                n = int(item["n"])
                x = center + (method_idx - 0.5) * (bar_w + 6)
                bar_h = (score / 5) * plot_h
                y = baseline - bar_h
                parts.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
                    f'fill="{COLORS[method]}" rx="2"/>'
                )
                parts.append(text(x + bar_w / 2, y - 6, f"{score:g}", 11, "700", "middle"))
                parts.append(
                    text(
                        x + bar_w / 2,
                        baseline + 48 + method_idx * 16,
                        f"n={n}",
                        13,
                        "600",
                        anchor="middle",
                        fill="#334e68",
                    )
                )
            parts.append(text(center, baseline + 23, model, 12, "600", "middle"))

        parts.append(text(x0 + 14, y0 + panel_h - 11, "Median score", 11, fill="#627d98"))

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
    print(f"Wrote {OUT_SVG}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
