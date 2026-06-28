from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MODEL_ORDER = ["DeepSeek_R1_14B", "Llama_3.1_8B", "Mistral", "Qwen_2.5_7B"]
MODEL_LABELS = {
    "DeepSeek_R1_14B": "DeepSeek R1 14B",
    "Llama_3.1_8B": "Llama 3.1 8B",
    "Mistral": "Mistral 7B",
    "Qwen_2.5_7B": "Qwen 2.5 7B",
}
METHOD_ORDER = ["raw", "baseline_repair", "syntax_grounded_repair"]
METHOD_LABELS = {
    "raw": "Base Method",
    "baseline_repair": "Baseline Repair",
    "syntax_grounded_repair": "Syntax-Grounded Repair",
}
METHOD_COLORS = {
    "raw": "#4E79A7",
    "baseline_repair": "#F28E2B",
    "syntax_grounded_repair": "#59A14F",
}
RAW_METHOD_BY_MODEL = {
    "DeepSeek_R1_14B": "few_shot",
    "Llama_3.1_8B": "few_shot",
    "Mistral": "rag",
    "Qwen_2.5_7B": "rag",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def plot_grouped_bars(
    series: dict[str, list[float]],
    title: str,
    ylabel: str,
    out_path: Path,
    annotate: bool = True,
) -> None:
    models = [MODEL_LABELS[m] for m in MODEL_ORDER]
    x = np.arange(len(models))
    width = 0.24

    plt.figure(figsize=(10, 5.8))
    for i, method in enumerate(METHOD_ORDER):
        values = series[method]
        offset = (i - 1) * width
        bars = plt.bar(x + offset, values, width=width, color=METHOD_COLORS[method], label=METHOD_LABELS[method])
        if annotate:
            for bar, value in zip(bars, values):
                plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{value:.1f}", ha="center", va="bottom", fontsize=9)

    plt.xticks(x, models, rotation=0)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.ylim(0, max(max(v) for v in series.values()) + 12)
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close()


def build_validity_summary_figure(validity_csv: Path, out_dir: Path) -> dict[str, dict[str, float]]:
    rows = read_csv(validity_csv)
    values: dict[str, dict[str, float]] = {m: {} for m in MODEL_ORDER}
    for row in rows:
        llm = row["llm_name"]
        method = row["method_name"]
        if llm not in values:
            continue
        mapped_method = "raw" if method in {"few_shot", "rag"} else method
        values[llm][mapped_method] = float(row["strict_valid_percent"])

    series = {
        method: [values[model].get(method, 0.0) for model in MODEL_ORDER]
        for method in METHOD_ORDER
    }
    plot_grouped_bars(
        series,
        "Syntax + Structural Validity Across Base and Repair Methods",
        "Strictly Valid Diagrams (%)",
        out_dir / "figure_01_validity_base_vs_repairs.png",
    )
    return values


def build_state_f1_figure(semantic_csv: Path, out_dir: Path) -> dict[str, dict[str, float]]:
    rows = read_csv(semantic_csv)
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        llm = row["llm_name"]
        method = row["method_name"]
        if llm not in MODEL_ORDER:
            continue
        if method not in {"few_shot", "rag", "baseline_repair", "syntax_grounded_repair"}:
            continue
        grouped.setdefault((llm, method), []).append(float(row["semantic_state_f1"]))

    values: dict[str, dict[str, float]] = {m: {} for m in MODEL_ORDER}
    for model in MODEL_ORDER:
        raw_method = RAW_METHOD_BY_MODEL[model]
        raw_scores = grouped.get((model, raw_method), [])
        values[model]["raw"] = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0
        for method in ("baseline_repair", "syntax_grounded_repair"):
            scores = grouped.get((model, method), [])
            values[model][method] = sum(scores) / len(scores) if scores else 0.0

    series = {
        method: [100.0 * values[model].get(method, 0.0) for model in MODEL_ORDER]
        for method in METHOD_ORDER
    }
    plot_grouped_bars(
        series,
        "Relaxed Semantic State F1 Across Base and Repair Methods",
        "Mean Relaxed State F1 (%)",
        out_dir / "figure_02_relaxed_state_f1_base_vs_repairs.png",
    )
    return values


def build_stability_figures(stability_csv: Path, out_dir: Path) -> list[dict[str, str]]:
    rows = read_csv(stability_csv)
    rows = [row for row in rows if row["llm"] in MODEL_ORDER]
    rows.sort(key=lambda r: MODEL_ORDER.index(r["llm"]))

    models = [MODEL_LABELS[row["llm"]] for row in rows]
    means = [100.0 * float(row["mean_state_f1"]) for row in rows]
    sds = [100.0 * float(row["state_f1_run_sd"]) for row in rows]

    plt.figure(figsize=(8.8, 5.6))
    x = np.arange(len(models))
    bars = plt.bar(x, means, yerr=sds, capsize=6, color="#4E79A7")
    for bar, mean_value, sd_value in zip(bars, means, sds):
        plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{mean_value:.1f}", ha="center", va="bottom", fontsize=9)
    plt.xticks(x, models)
    plt.ylabel("Mean Relaxed State F1 (%)")
    plt.title("Model Stability Across Three Independent Runs")
    plt.tight_layout()
    plt.savefig(out_dir / "figure_03_stability_mean_state_f1.png", dpi=220)
    plt.close()

    syntax_consistency = [float(row["syntax_consistent_cases_percent"]) for row in rows]
    structural_consistency = [float(row["structural_consistent_cases_percent"]) for row in rows]
    width = 0.34
    plt.figure(figsize=(9.2, 5.6))
    bars1 = plt.bar(x - width / 2, syntax_consistency, width=width, color="#59A14F", label="Syntax consistency")
    bars2 = plt.bar(x + width / 2, structural_consistency, width=width, color="#E15759", label="Structural consistency")
    for bars in (bars1, bars2):
        for bar in bars:
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{bar.get_height():.1f}", ha="center", va="bottom", fontsize=9)
    plt.xticks(x, models)
    plt.ylabel("Consistent Cases (%)")
    plt.title("Syntax and Structural Consistency Across Runs")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(out_dir / "figure_04_stability_consistency.png", dpi=220)
    plt.close()
    return rows


def build_error_resolution_figure(error_txt: Path, out_dir: Path) -> list[dict[str, str]]:
    text = error_txt.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\|\s*(.*?)\s*\|\s*([0-9.]+)% \((\d+)/(\d+)\)\s*\|\s*([0-9.]+)% \((\d+)/(\d+)\)\s*\|\s*(.*?)\s*\|"
    )
    rows = []
    for match in pattern.finditer(text):
        error_type = match.group(1).strip()
        if error_type.lower().startswith("overall"):
            continue
        rows.append(
            {
                "error_type": error_type,
                "baseline_pct": float(match.group(2)),
                "baseline_solved": int(match.group(3)),
                "baseline_total": int(match.group(4)),
                "syntax_pct": float(match.group(5)),
                "syntax_solved": int(match.group(6)),
                "syntax_total": int(match.group(7)),
                "better_method": match.group(8).strip(),
            }
        )

    labels = [row["error_type"] for row in rows]
    y = np.arange(len(labels))
    baseline = [row["baseline_pct"] for row in rows]
    syntax = [row["syntax_pct"] for row in rows]

    plt.figure(figsize=(10.8, 7.0))
    plt.barh(y + 0.18, baseline, height=0.34, color="#F28E2B", label="Baseline Repair")
    plt.barh(y - 0.18, syntax, height=0.34, color="#59A14F", label="Syntax-Grounded Repair")
    plt.yticks(y, labels)
    plt.xlabel("Error Resolution Rate (%)")
    plt.title("Repair Success by Structural Error Type")
    plt.legend(frameon=False, loc="lower right")
    plt.tight_layout()
    plt.savefig(out_dir / "figure_05_error_resolution_by_type.png", dpi=220)
    plt.close()
    return rows


def build_valid99_composition_figure(dedup_summary_csv: Path, human_summary_txt: Path, out_dir: Path) -> dict[str, int]:
    rows = read_csv(dedup_summary_csv)
    total_valid99 = sum(int(row["valid_count"]) for row in rows)

    summary_text = human_summary_txt.read_text(encoding="utf-8")
    at_least_2 = int(re.search(r"kept for comparison: (\d+)", summary_text).group(1))
    missing = int(re.search(r"missing 2-human coverage: (\d+)", summary_text).group(1))

    labels = ["Valid diagrams\nafter raw-overlap removal", "With 2 human\nratings", "Missing human\ncoverage"]
    values = [total_valid99, at_least_2, missing]
    colors = ["#4E79A7", "#59A14F", "#E15759"]

    plt.figure(figsize=(8.4, 5.2))
    bars = plt.bar(labels, values, color=colors)
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 1, str(value), ha="center", va="bottom", fontsize=11)
    plt.ylabel("Diagram Count")
    plt.title("Composition of the Final Human/LLM Evaluation Set")
    plt.tight_layout()
    plt.savefig(out_dir / "figure_06_valid99_human_coverage.png", dpi=220)
    plt.close()
    return {"total_valid99": total_valid99, "human_two_raters": at_least_2, "human_missing": missing}


def write_results_notes(
    out_path: Path,
    validity_values: dict[str, dict[str, float]],
    state_f1_values: dict[str, dict[str, float]],
    stability_rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
    valid99_info: dict[str, int],
) -> None:
    lines: list[str] = []
    lines.append("# Results and Analysis Chapter Notes")
    lines.append("")
    lines.append("## Included scope")
    lines.append("- Base methods: Qwen RAG, Mistral RAG, DeepSeek Few-shot, and Llama Few-shot")
    lines.append("- Repair methods: Baseline Repair and Syntax-Grounded Repair")
    lines.append("- Strict syntax + structural validity")
    lines.append("- Relaxed semantic state F1")
    lines.append("- Stability across three independent runs")
    lines.append("- Human-vs-LLM judge experiment setup (final agreement results can be inserted later)")
    lines.append("- Repair error analysis")
    lines.append("")

    lines.append("## Key numerical findings")
    lines.append("")
    lines.append("### Strict syntax + structural validity")
    for model in MODEL_ORDER:
        vals = validity_values[model]
        lines.append(
            f"- {MODEL_LABELS[model]}: base {vals['raw']:.2f}%, baseline repair {vals['baseline_repair']:.2f}%, syntax-grounded repair {vals['syntax_grounded_repair']:.2f}%."
        )
    lines.append("")

    lines.append("### Relaxed semantic state F1")
    for model in MODEL_ORDER:
        vals = state_f1_values[model]
        lines.append(
            f"- {MODEL_LABELS[model]}: base {vals['raw']:.3f}, baseline repair {vals['baseline_repair']:.3f}, syntax-grounded repair {vals['syntax_grounded_repair']:.3f}."
        )
    lines.append("")

    lines.append("### Stability (base methods across 3 runs)")
    for row in stability_rows:
        lines.append(
            f"- {MODEL_LABELS[row['llm']]}: mean state F1 {float(row['mean_state_f1']):.3f}, run-level SD {float(row['state_f1_run_sd']):.3f}, mean case-wise SD {float(row['mean_case_state_f1_sd']):.3f}, syntax consistency {float(row['syntax_consistent_cases_percent']):.2f}%, structural consistency {float(row['structural_consistent_cases_percent']):.2f}%."
        )
    lines.append("")

    lines.append("### Error analysis")
    for row in error_rows:
        lines.append(
            f"- {row['error_type']}: baseline {row['baseline_pct']:.2f}% vs syntax-grounded {row['syntax_pct']:.2f}% (better: {row['better_method']})."
        )
    lines.append("")

    lines.append("### Human/LLM judge dataset preparation")
    lines.append(
        f"- Final valid set after removing repair diagrams that overlap with already-valid raw diagrams: {valid99_info['total_valid99']} diagrams."
    )
    lines.append(
        f"- Diagrams with at least two human ratings currently available: {valid99_info['human_two_raters']}."
    )
    lines.append(
        f"- Diagrams still missing 2-human coverage: {valid99_info['human_missing']}."
    )
    lines.append("")

    lines.append("## Suggested figures")
    lines.append("1. `figure_01_validity_base_vs_repairs.png`: strict syntax + structural validity across base and repair methods.")
    lines.append("2. `figure_02_relaxed_state_f1_base_vs_repairs.png`: relaxed semantic state F1 across base and repair methods.")
    lines.append("3. `figure_03_stability_mean_state_f1.png`: mean state F1 with run-level standard deviation.")
    lines.append("4. `figure_04_stability_consistency.png`: syntax and structural consistency percentages across runs.")
    lines.append("5. `figure_05_error_resolution_by_type.png`: repair success by structural error type.")
    lines.append("6. `figure_06_valid99_human_coverage.png`: composition of the final valid human/LLM evaluation set.")
    lines.append("")

    lines.append("## Figure captions draft")
    lines.append("- Figure 1. Strict syntax and structural validity percentages for the four selected LLMs under the base, baseline repair, and syntax-grounded repair settings.")
    lines.append("- Figure 2. Mean relaxed semantic state F1 for the same four LLMs before and after repair.")
    lines.append("- Figure 3. Mean semantic state F1 across three independent runs, with error bars showing run-level standard deviation.")
    lines.append("- Figure 4. Percentage of cases whose syntax-validity and structural-validity outcomes remained consistent across three runs.")
    lines.append("- Figure 5. Error-type-wise repair success rates for baseline and syntax-grounded repair.")
    lines.append("- Figure 6. Final composition of the 99-diagram human/LLM judge comparison subset.")
    lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build figures and notes for the Results and Analysis chapter.")
    parser.add_argument("--validity-csv", default="valid_diagrams_from_untitled_raw_deduped/valid_diagram_summary.csv")
    parser.add_argument("--dedup-summary-csv", default="valid_diagrams_from_untitled_raw_deduped/dedup_summary.csv")
    parser.add_argument("--semantic-csv", default="results/plantuml_pipeline/semantic_state_matching/semantic_state_matches_324.csv")
    parser.add_argument("--stability-csv", default="results/plantuml_pipeline/semantic_state_matching/model_stability_summary_semantic.csv")
    parser.add_argument("--error-txt", default="results/plantuml_pipeline/repair_success_percentage_by_error.txt")
    parser.add_argument("--human-summary-txt", default="results/plantuml_pipeline/llm_judge/human_scores_valid99_clean/summary.txt")
    parser.add_argument("--output-dir", default="results/plantuml_pipeline/results_doc_assets")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.output_dir)
    ensure_dir(out_dir)

    validity_values = build_validity_summary_figure(Path(args.validity_csv), out_dir)
    state_f1_values = build_state_f1_figure(Path(args.semantic_csv), out_dir)
    stability_rows = build_stability_figures(Path(args.stability_csv), out_dir)
    error_rows = build_error_resolution_figure(Path(args.error_txt), out_dir)
    valid99_info = build_valid99_composition_figure(
        Path(args.dedup_summary_csv),
        Path(args.human_summary_txt),
        out_dir,
    )
    write_results_notes(
        out_dir / "results_and_analysis_notes.md",
        validity_values,
        state_f1_values,
        stability_rows,
        error_rows,
        valid99_info,
    )

    print(f"Wrote results-doc assets to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
