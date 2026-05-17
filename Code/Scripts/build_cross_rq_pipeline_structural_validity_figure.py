"""Build a cross-RQ pipeline performance chart.

The chart compares structural validity before and after the repair stage for
the model-specific strategy that was sent into the repair pipeline.
"""

from __future__ import annotations

import csv
import html
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROMPTING_LONG = ROOT / "results" / "human_evaluation_likert" / "charts_summary" / "prompting_strategy_long.csv"
REPAIR_LONG = ROOT / "results" / "human_evaluation_likert" / "charts_summary" / "repair_long.csv"
OUT_DIR = ROOT / "results" / "plantuml_pipeline" / "charts_summary"
OUT_CSV = OUT_DIR / "cross_rq_pipeline_structural_validity.csv"
OUT_SVG = OUT_DIR / "cross_rq_pipeline_structural_validity.svg"
OUT_PNG = OUT_DIR / "cross_rq_pipeline_structural_validity.png"

MODEL_ORDER = ["llama", "mistral", "deepseek", "qwen"]
MODEL_LABELS = {
    "llama": "Llama",
    "mistral": "Mistral",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
}
BASELINE_METHOD = {
    "llama": "Few-shot",
    "mistral": "RAG",
    "deepseek": "Few-shot",
    "qwen": "RAG",
}
COLORS = {"Baseline": "#4E79A7", "After repair": "#59A14F"}


def read_long_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def load_rows() -> list[dict[str, object]]:
    prompting = read_long_csv(PROMPTING_LONG)
    repair = read_long_csv(REPAIR_LONG)

    baseline_lookup = {}
    for row in prompting:
        if (
            row["evaluation_group"] == "Automatic (accuracy)"
            and row["metric"] == "Structural validity"
        ):
            baseline_lookup[(row["model"], row["method"])] = row

    repair_lookup = {}
    for row in repair:
        if (
            row["evaluation_group"] == "Automatic (accuracy)"
            and row["metric"] == "Structural validity"
            and row["method"] == "Repair"
        ):
            repair_lookup[row["model"]] = row

    rows: list[dict[str, object]] = []
    for model in MODEL_ORDER:
        baseline_method = BASELINE_METHOD[model]
        baseline_row = baseline_lookup[(model, baseline_method)]
        repair_row = repair_lookup[model]
        baseline_value = float(baseline_row["value"])
        repair_value = float(repair_row["value"])
        baseline_n = int(baseline_row["n"])
        baseline_total = int(baseline_row["total"])
        repair_n = int(repair_row["n"])
        repair_total = int(repair_row["total"])
        rows.append(
            {
                "model": MODEL_LABELS[model],
                "baseline_method": baseline_method,
                "baseline_structural_validity_percent": baseline_value,
                "baseline_n": baseline_n,
                "baseline_total": baseline_total,
                "after_repair_structural_validity_percent": repair_value,
                "after_repair_n": repair_n,
                "after_repair_total": repair_total,
                "absolute_change_points": round(repair_value - baseline_value, 2),
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
    width = 1180
    height = 700
    left = 116
    top = 158
    plot_w = 930
    plot_h = 370
    baseline_y = top + plot_h
    group_w = plot_w / len(rows)
    bar_w = 54

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        text(42, 42, "Cross-RQ pipeline performance: structural validity after repair", 22, "700"),
        text(
            42,
            70,
            "Baseline is each model's repair-target strategy; values show structurally valid diagrams out of 27.",
            14,
            fill="#52606d",
        ),
    ]

    legend_x = 42
    for idx, label in enumerate(["Baseline", "After repair"]):
        x = legend_x + idx * 145
        parts.append(f'<rect x="{x}" y="92" width="18" height="18" rx="3" fill="{COLORS[label]}"/>')
        parts.append(text(x + 26, 107, label, 13, "600"))

    for tick in range(0, 101, 20):
        y = baseline_y - (tick / 100) * plot_h
        stroke = "#d9e2ec" if tick else "#9fb3c8"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1"/>')
        parts.append(text(left - 10, y + 4, f"{tick}%", 12, anchor="end", fill="#52606d"))

    for idx, row in enumerate(rows):
        center = left + group_w * idx + group_w / 2
        values = [
            ("Baseline", float(row["baseline_structural_validity_percent"]), int(row["baseline_n"])),
            ("After repair", float(row["after_repair_structural_validity_percent"]), int(row["after_repair_n"])),
        ]
        for bar_idx, (label, value, n) in enumerate(values):
            x = center + (bar_idx - 0.5) * (bar_w + 12)
            h = (value / 100) * plot_h
            y = baseline_y - h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" '
                f'rx="3" fill="{COLORS[label]}"/>'
            )
            parts.append(text(x + bar_w / 2, y - 8, f"{value:.2f}%", 11, "700", "middle"))

        change = float(row["absolute_change_points"])
        change_label = (
            f"+{change:.2f} percentage points"
            if change >= 0
            else f"{change:.2f} percentage points"
        )
        parts.append(text(center, baseline_y + 20, str(row["model"]), 13, "700", "middle"))
        parts.append(text(center, baseline_y + 38, f"Baseline n={int(row['baseline_n'])}/27", 12, "600", "middle", "#334e68"))
        parts.append(text(center, baseline_y + 56, f"Repair n={int(row['after_repair_n'])}/27", 12, "600", "middle", "#334e68"))
        parts.append(text(center, baseline_y + 78, f"{row['baseline_method']} -> Repair", 11, anchor="middle", fill="#52606d"))
        parts.append(text(center, baseline_y + 98, change_label, 11, "700", "middle", fill="#2f855a" if change >= 0 else "#c53030"))

    parts.append(text(42, top - 24, "Structural validity (%)", 13, "700", fill="#52606d"))
    parts.append(text(left + plot_w / 2, height - 32, "Model", 13, "700", "middle", "#52606d"))
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
