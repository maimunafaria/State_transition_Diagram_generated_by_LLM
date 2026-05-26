"""Build aggregate human diagram-quality figure by model.

This chart is independent of prompting method: it aggregates all evaluated
human responses by LLM and reports median 1-5 Likert scores for the four human
evaluation dimensions.
"""

from __future__ import annotations

import csv
import html
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "results" / "human_evaluation_likert" / "descriptive_stats_by_llm_used.csv"
OUT_DIR = ROOT / "results" / "human_evaluation_likert" / "charts_summary"
OUT_CSV = OUT_DIR / "human_quality_median_by_model_aggregate.csv"
OUT_SVG = OUT_DIR / "human_quality_median_by_model_aggregate.svg"
OUT_PNG = OUT_DIR / "human_quality_median_by_model_aggregate.png"

MODEL_ORDER = [
    "Llama 3.1 8B Instruct",
    "Mistral",
    "DeepSeek R1 14B",
    "Qwen 2.5 7B Instruct",
]
MODEL_LABELS = {
    "Llama 3.1 8B Instruct": "Llama",
    "Mistral": "Mistral",
    "DeepSeek R1 14B": "DeepSeek",
    "Qwen 2.5 7B Instruct": "Qwen",
}
CRITERIA = [
    ("completeness", "Completeness"),
    ("correctness", "Correctness"),
    ("understandability", "Understandability"),
    ("terminology_alignment", "Terminology alignment"),
]
COLORS = {
    "Llama": "#4E79A7",
    "Mistral": "#F28E2B",
    "DeepSeek": "#59A14F",
    "Qwen": "#E15759",
}


def load_rows() -> list[dict[str, object]]:
    with INPUT.open(encoding="utf-8", newline="") as file:
        source_rows = list(csv.DictReader(file))
    lookup = {(row["llm_used"], row["criterion"]): row for row in source_rows}

    rows: list[dict[str, object]] = []
    for criterion_key, criterion_label in CRITERIA:
        for model in MODEL_ORDER:
            row = lookup[(model, criterion_key)]
            rows.append(
                {
                    "criterion": criterion_label,
                    "model": MODEL_LABELS[model],
                    "median_likert_score": float(row["median"]),
                    "n": int(row["n"]),
                    "q1": float(row["q1"]),
                    "q3": float(row["q3"]),
                }
            )
    return rows


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
    by_key = {(str(row["criterion"]), str(row["model"])): row for row in rows}
    width = 1360
    height = 740
    left = 96
    top = 162
    plot_w = 1110
    plot_h = 410
    baseline_y = top + plot_h
    group_w = plot_w / len(CRITERIA)
    bar_w = 34
    model_gap = 8

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(42, 42, "Human evaluation of diagram quality across four dimensions", 22, "700"),
        text(
            42,
            70,
            "Model-level aggregate across all evaluated diagrams; bars show median 1-5 Likert scores.",
            14,
            fill="#52606d",
        ),
    ]

    legend_x = 42
    for idx, model in enumerate(["Llama", "Mistral", "DeepSeek", "Qwen"]):
        x = legend_x + idx * 132
        parts.append(f'<rect x="{x}" y="94" width="18" height="18" rx="3" fill="{COLORS[model]}"/>')
        parts.append(text(x + 26, 109, model, 13, "600"))

    for tick in range(0, 6):
        y = baseline_y - (tick / 5) * plot_h
        stroke = "#d9e2ec" if tick else "#9fb3c8"
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" '
            f'stroke="{stroke}" stroke-width="1"/>'
        )
        parts.append(text(left - 12, y + 4, tick, 12, anchor="end", fill="#52606d"))

    for c_idx, (_, criterion) in enumerate(CRITERIA):
        center = left + group_w * c_idx + group_w / 2
        total_bar_w = (bar_w * len(MODEL_ORDER)) + (model_gap * (len(MODEL_ORDER) - 1))
        start_x = center - total_bar_w / 2
        for m_idx, model_full in enumerate(MODEL_ORDER):
            model = MODEL_LABELS[model_full]
            item = by_key[(criterion, model)]
            score = float(item["median_likert_score"])
            n = int(item["n"])
            x = start_x + m_idx * (bar_w + model_gap)
            h = (score / 5) * plot_h
            y = baseline_y - h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" '
                f'rx="3" fill="{COLORS[model]}"/>'
            )
            parts.append(text(x + bar_w / 2, y - 8, f"{score:g}", 12, "700", "middle"))
            parts.append(text(x + bar_w / 2, baseline_y + 48, f"n={n}", 11, "600", "middle", "#334e68"))
        parts.append(text(center, baseline_y + 23, criterion, 13, "700", "middle"))

    parts.append(text(42, top - 24, "Median Likert score", 13, "700", fill="#52606d"))
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
