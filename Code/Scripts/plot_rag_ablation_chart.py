#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "results" / "plantuml_pipeline" / "runs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "charts_ablation"
RUN_FILE_RE = re.compile(r"^run_\d+\.puml$")

ABLATION_LABELS = {
    "rag": "Full RAG",
    "rag__examples_only": "Examples Only",
    "rag__rules_only": "Rules Only",
    "rag__theory_only": "Theory Only",
}


def summarize_run_dir(run_dir: Path) -> dict[str, object]:
    sys.path.insert(0, str((PROJECT_ROOT / "Code" / "Scripts").resolve()))
    from plantuml_pipeline.parser import parse_and_validate_puml_text

    total = 0
    plantuml_valid = 0
    state_valid = 0

    for puml_file in sorted(run_dir.rglob("*.puml")):
        if not RUN_FILE_RE.match(puml_file.name):
            continue
        _, validation = parse_and_validate_puml_text(puml_file.read_text(encoding="utf-8"))
        total += 1
        if validation.valid:
            plantuml_valid += 1
        issues = list(validation.errors) + list(validation.warnings)
        if validation.valid and not issues:
            state_valid += 1

    return {
        "total": total,
        "plantuml_valid": plantuml_valid,
        "plantuml_invalid": total - plantuml_valid,
        "state_valid": state_valid,
        "state_invalid": total - state_valid,
        "plantuml_percent": round((plantuml_valid / total * 100.0), 2) if total else 0.0,
        "state_percent": round((state_valid / total * 100.0), 2) if total else 0.0,
    }


def build_svg(rows: list[dict[str, object]], title: str) -> str:
    width = 1040
    height = 560
    margin_left = 90
    margin_right = 40
    margin_top = 90
    margin_bottom = 120
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    group_gap = 36
    group_w = (plot_w - group_gap * (len(rows) - 1)) / max(1, len(rows))
    bar_gap = 12
    bar_w = (group_w - bar_gap) / 2

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
        ".group { font-size: 13px; font-weight: 700; }",
        ".value { font-size: 11px; fill: #222; }",
        ".legend { font-size: 12px; }",
        "</style>",
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text class="title" x="{margin_left}" y="34">{html.escape(title)}</text>',
        '<text class="subtitle" x="90" y="56">Blue: PlantUML validity. Red: strict state-rule validity.</text>',
    ]

    for tick in range(0, 101, 20):
        y = y_for(tick)
        parts.append(f'<line class="grid" x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end">{tick}%</text>')

    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_h}"/>')
    parts.append(f'<line class="axis" x1="{margin_left}" y1="{margin_top + plot_h}" x2="{width - margin_right}" y2="{margin_top + plot_h}"/>')

    for idx, row in enumerate(rows):
        group_x = margin_left + idx * (group_w + group_gap)
        plant = float(row["plantuml_percent"])
        state = float(row["state_percent"])
        bars = [
            ("#4E79A7", plant, group_x, "PlantUML"),
            ("#E15759", state, group_x + bar_w + bar_gap, "State-rule"),
        ]
        for color, value, x, label in bars:
            y = y_for(value)
            bar_h = margin_top + plot_h - y
            tooltip = html.escape(f'{row["ablation"]} | {label}: {value:.2f}%')
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="2" fill="{color}"><title>{tooltip}</title></rect>'
            )
            parts.append(
                f'<text class="value" x="{x + bar_w / 2:.1f}" y="{max(y - 5, margin_top - 8):.1f}" text-anchor="middle">{value:.0f}%</text>'
            )
        parts.append(
            f'<text class="group" x="{group_x + group_w / 2:.1f}" y="{margin_top + plot_h + 28}" text-anchor="middle">{html.escape(str(row["ablation"]))}</text>'
        )

    legend_y = height - 52
    parts.append(f'<rect x="{margin_left}" y="{legend_y}" width="14" height="14" fill="#4E79A7" rx="2"/>')
    parts.append(f'<text class="legend" x="{margin_left + 20}" y="{legend_y + 12}">PlantUML Validity</text>')
    parts.append(f'<rect x="{margin_left + 210}" y="{legend_y}" width="14" height="14" fill="#E15759" rx="2"/>')
    parts.append(f'<text class="legend" x="{margin_left + 230}" y="{legend_y + 12}">Strict State-Rule Validity</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a simple RAG ablation chart for one model.")
    parser.add_argument("--model-tag", required=True, help="Model run-id tag, e.g. mistral or llama31_8b_instruct")
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    runs_root = args.runs_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    suffixes = ["rag", "rag__examples_only", "rag__rules_only", "rag__theory_only"]
    rows: list[dict[str, object]] = []
    for suffix in suffixes:
        run_dir = runs_root / f"open_source__{args.model_tag}__{suffix}"
        if not run_dir.exists():
            continue
        summary = summarize_run_dir(run_dir)
        rows.append(
            {
                "ablation": ABLATION_LABELS.get(suffix, suffix),
                "run_id": run_dir.name,
                **summary,
            }
        )

    if not rows:
        raise FileNotFoundError(f"No ablation run folders found for model tag: {args.model_tag}")

    csv_path = output_dir / f"{args.model_tag}_rag_ablation_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "ablation",
                "run_id",
                "total",
                "plantuml_valid",
                "plantuml_invalid",
                "plantuml_percent",
                "state_valid",
                "state_invalid",
                "state_percent",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    title = f"{args.model_tag.replace('_', ' ').title()} RAG Ablation"
    svg = build_svg(rows, title=title)
    svg_path = output_dir / f"{args.model_tag}_rag_ablation_validity.svg"
    svg_path.write_text(svg, encoding="utf-8")

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {svg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
