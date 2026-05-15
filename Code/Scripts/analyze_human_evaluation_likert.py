#!/usr/bin/env python3
"""Analyze human Likert-scale diagram evaluations.

Inputs:
  results/evaluation_diagram_responses_long_form.csv

Outputs:
  results/human_evaluation_likert/
"""

from __future__ import annotations

import csv
import itertools
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


INPUT = Path("results/evaluation_diagram_responses_long_form.csv")
OUT = Path("results/human_evaluation_likert")
CHARTS = OUT / "charts"

CRITERIA = [
    "completeness",
    "correctness",
    "understandability",
    "terminology_alignment",
]
GROUP_COLS = ["method", "llm_used"]
SCORES = [1, 2, 3, 4, 5]


def read_rows() -> list[dict[str, str]]:
    with INPUT.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def numeric_scores(rows: list[dict[str, str]], criterion: str) -> list[int]:
    vals = []
    for row in rows:
        try:
            vals.append(int(float(row[criterion])))
        except Exception:
            pass
    return vals


def percentile(sorted_vals: list[int], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[lo])
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def iqr(vals: list[int]) -> tuple[float, float, float]:
    ordered = sorted(vals)
    q1 = percentile(ordered, 0.25)
    q3 = percentile(ordered, 0.75)
    return q1, q3, q3 - q1


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    out = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        for k in range(i, j):
            out[indexed[k][0]] = avg_rank
        i = j
    return out


def gammaincc(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x)."""
    if x <= 0:
        return 1.0
    eps = 1e-14
    max_iter = 1000
    gln = math.lgamma(a)
    if x < a + 1:
        ap = a
        summ = 1.0 / a
        delta = summ
        for _ in range(max_iter):
            ap += 1
            delta *= x / ap
            summ += delta
            if abs(delta) < abs(summ) * eps:
                p = summ * math.exp(-x + a * math.log(x) - gln)
                return max(0.0, min(1.0, 1.0 - p))
        p = summ * math.exp(-x + a * math.log(x) - gln)
        return max(0.0, min(1.0, 1.0 - p))

    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, max_iter + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            q = math.exp(-x + a * math.log(x) - gln) * h
            return max(0.0, min(1.0, q))
    q = math.exp(-x + a * math.log(x) - gln) * h
    return max(0.0, min(1.0, q))


def chi_square_sf(x: float, df: int) -> float:
    return gammaincc(df / 2.0, x / 2.0)


def kruskal_wallis(groups: dict[str, list[int]]) -> dict[str, object]:
    groups = {k: v for k, v in groups.items() if v}
    all_values = []
    labels = []
    for name, vals in groups.items():
        for val in vals:
            all_values.append(val)
            labels.append(name)
    n = len(all_values)
    k = len(groups)
    if n == 0 or k < 2:
        return {"h_statistic": "", "df": "", "p_value": "", "significant": ""}
    all_ranks = ranks(all_values)
    rank_sums = defaultdict(float)
    counts = Counter(labels)
    for label, rank in zip(labels, all_ranks):
        rank_sums[label] += rank
    h = (12 / (n * (n + 1))) * sum((rank_sums[g] ** 2) / counts[g] for g in groups) - 3 * (n + 1)
    tie_counts = Counter(all_values)
    tie_correction = 1 - sum(t**3 - t for t in tie_counts.values()) / (n**3 - n) if n > 1 else 1
    if tie_correction > 0:
        h /= tie_correction
    df = k - 1
    p = chi_square_sf(h, df)
    return {
        "h_statistic": round(h, 6),
        "df": df,
        "p_value": round(p, 8),
        "significant": "yes" if p < 0.05 else "no",
    }


def normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


def dunn_posthoc(groups: dict[str, list[int]], alpha: float = 0.05) -> list[dict[str, object]]:
    groups = {k: v for k, v in groups.items() if v}
    all_values = []
    labels = []
    for name, vals in groups.items():
        for val in vals:
            all_values.append(val)
            labels.append(name)
    n = len(all_values)
    if len(groups) < 2 or n < 2:
        return []
    all_ranks = ranks(all_values)
    rank_sums = defaultdict(float)
    counts = Counter(labels)
    for label, rank in zip(labels, all_ranks):
        rank_sums[label] += rank
    mean_ranks = {g: rank_sums[g] / counts[g] for g in groups}
    tie_counts = Counter(all_values)
    tie_correction = 1 - sum(t**3 - t for t in tie_counts.values()) / (n**3 - n)
    base_var = (n * (n + 1) / 12) * tie_correction

    raw = []
    for g1, g2 in itertools.combinations(sorted(groups), 2):
        se = math.sqrt(base_var * (1 / counts[g1] + 1 / counts[g2]))
        z = (mean_ranks[g1] - mean_ranks[g2]) / se if se else 0.0
        p = normal_two_sided_p(z)
        raw.append(
            {
                "group_1": g1,
                "group_2": g2,
                "mean_rank_1": round(mean_ranks[g1], 4),
                "mean_rank_2": round(mean_ranks[g2], 4),
                "z": round(z, 6),
                "raw_p_value": p,
            }
        )

    ordered = sorted(enumerate(raw), key=lambda x: x[1]["raw_p_value"])
    m = len(raw)
    adjusted = [0.0] * m
    running = 0.0
    for rank_idx, (orig_idx, row) in enumerate(ordered):
        holm_p = min(1.0, row["raw_p_value"] * (m - rank_idx))
        running = max(running, holm_p)
        adjusted[orig_idx] = running
    for idx, row in enumerate(raw):
        row["holm_adjusted_p_value"] = round(adjusted[idx], 8)
        row["significant"] = "yes" if adjusted[idx] < alpha else "no"
        row["raw_p_value"] = round(row["raw_p_value"], 8)
    return raw


def descriptive_tables(rows: list[dict[str, str]]) -> None:
    for group_col in GROUP_COLS:
        out = []
        groups = sorted({r[group_col] for r in rows})
        for group in groups:
            group_rows = [r for r in rows if r[group_col] == group]
            for criterion in CRITERIA:
                vals = numeric_scores(group_rows, criterion)
                q1, q3, iqr_val = iqr(vals)
                counts = Counter(vals)
                out.append(
                    {
                        group_col: group,
                        "criterion": criterion,
                        "n": len(vals),
                        "median": median(vals) if vals else "",
                        "mean_supplementary": round(mean(vals), 4) if vals else "",
                        "q1": round(q1, 4) if vals else "",
                        "q3": round(q3, 4) if vals else "",
                        "iqr": round(iqr_val, 4) if vals else "",
                        "score_1_count": counts[1],
                        "score_2_count": counts[2],
                        "score_3_count": counts[3],
                        "score_4_count": counts[4],
                        "score_5_count": counts[5],
                    }
                )
        write_csv(OUT / f"descriptive_stats_by_{group_col}.csv", out)


def distribution_tables(rows: list[dict[str, str]]) -> None:
    for group_col in GROUP_COLS:
        out = []
        for group in sorted({r[group_col] for r in rows}):
            group_rows = [r for r in rows if r[group_col] == group]
            for criterion in CRITERIA:
                vals = numeric_scores(group_rows, criterion)
                counts = Counter(vals)
                total = len(vals)
                for score in SCORES:
                    out.append(
                        {
                            group_col: group,
                            "criterion": criterion,
                            "score": score,
                            "count": counts[score],
                            "percent": round(counts[score] / total * 100, 4) if total else 0,
                            "n": total,
                        }
                    )
        write_csv(OUT / f"likert_distribution_by_{group_col}.csv", out)


def statistical_tests(rows: list[dict[str, str]]) -> None:
    for group_col in GROUP_COLS:
        tests = []
        posthoc = []
        for criterion in CRITERIA:
            groups = defaultdict(list)
            for row in rows:
                try:
                    groups[row[group_col]].append(int(float(row[criterion])))
                except Exception:
                    pass
            result = kruskal_wallis(groups)
            tests.append(
                {
                    "grouping": group_col,
                    "criterion": criterion,
                    "test": "Kruskal-Wallis",
                    "groups": "; ".join(f"{k} (n={len(v)})" for k, v in sorted(groups.items())),
                    **result,
                    "interpretation": (
                        f"Significant difference in {criterion} ratings across {group_col} groups."
                        if result.get("significant") == "yes"
                        else f"No statistically significant difference in {criterion} ratings across {group_col} groups."
                    ),
                }
            )
            if result.get("significant") == "yes":
                for row in dunn_posthoc(groups):
                    posthoc.append({"grouping": group_col, "criterion": criterion, **row})
        write_csv(OUT / f"kruskal_wallis_by_{group_col}.csv", tests)
        write_csv(OUT / f"dunn_posthoc_by_{group_col}.csv", posthoc)


def svg_escape(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def short_label(label: str) -> str:
    return (
        label.replace("Llama 3.1 8B Instruct", "Llama")
        .replace("DeepSeek R1 14B", "DeepSeek")
        .replace("Qwen 2.5 7B Instruct", "Qwen")
        .replace("terminology_alignment", "Terminology")
        .replace("understandability", "Understand.")
        .replace("completeness", "Completeness")
        .replace("correctness", "Correctness")
    )


def likert_chart(rows: list[dict[str, str]], group_col: str, criterion: str) -> None:
    palette = {
        1: "#b2182b",
        2: "#ef8a62",
        3: "#f7f7f7",
        4: "#67a9cf",
        5: "#2166ac",
    }
    groups = sorted({r[group_col] for r in rows})
    width = 1050
    bar_h = 30
    gap = 20
    left = 230
    right = 60
    top = 70
    chart_w = width - left - right
    height = top + len(groups) * (bar_h + gap) + 90
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">{svg_escape(short_label(criterion))} Distribution by {svg_escape(group_col)}</text>',
    ]
    for i, score in enumerate(SCORES):
        x = left + i * 105
        parts.append(f'<rect x="{x}" y="44" width="16" height="16" fill="{palette[score]}" stroke="#444" stroke-width="0.5"/>')
        parts.append(f'<text x="{x+22}" y="57" font-family="Arial" font-size="12">Score {score}</text>')
    for idx, group in enumerate(groups):
        y = top + idx * (bar_h + gap)
        vals = numeric_scores([r for r in rows if r[group_col] == group], criterion)
        counts = Counter(vals)
        total = len(vals)
        parts.append(f'<text x="{left-12}" y="{y+20}" text-anchor="end" font-family="Arial" font-size="13">{svg_escape(short_label(group))}</text>')
        x = left
        for score in SCORES:
            pct = counts[score] / total if total else 0
            w = pct * chart_w
            if w > 0:
                parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{bar_h}" fill="{palette[score]}" stroke="white" stroke-width="1"/>')
                if w > 42:
                    parts.append(f'<text x="{x+w/2}" y="{y+20}" text-anchor="middle" font-family="Arial" font-size="11" fill="{"#111" if score == 3 else "white"}">{counts[score]}</text>')
            x += w
        parts.append(f'<rect x="{left}" y="{y}" width="{chart_w}" height="{bar_h}" fill="none" stroke="#333" stroke-width="0.7"/>')
        parts.append(f'<text x="{left+chart_w+8}" y="{y+20}" font-family="Arial" font-size="12">n={total}</text>')
    for pct in [0, 25, 50, 75, 100]:
        x = left + chart_w * pct / 100
        parts.append(f'<line x1="{x}" y1="{top-8}" x2="{x}" y2="{height-55}" stroke="#ddd" stroke-width="0.8"/>')
        parts.append(f'<text x="{x}" y="{height-30}" text-anchor="middle" font-family="Arial" font-size="12">{pct}%</text>')
    parts.append("</svg>")
    (CHARTS / f"{criterion}_by_{group_col}_likert_stacked.svg").write_text("\n".join(parts), encoding="utf-8")


def median_chart(rows: list[dict[str, str]], group_col: str) -> None:
    groups = sorted({r[group_col] for r in rows})
    width = 1120
    left = 210
    top = 70
    cell_w = 165
    cell_h = 42
    height = top + len(groups) * cell_h + 80
    colors = {1: "#b2182b", 2: "#ef8a62", 3: "#f7f7f7", 4: "#67a9cf", 5: "#2166ac"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">Median Likert Score by {svg_escape(group_col)}</text>',
    ]
    for c_idx, criterion in enumerate(CRITERIA):
        x = left + c_idx * cell_w
        parts.append(f'<text x="{x+cell_w/2}" y="{top-15}" text-anchor="middle" font-family="Arial" font-size="13" font-weight="700">{svg_escape(short_label(criterion))}</text>')
    for r_idx, group in enumerate(groups):
        y = top + r_idx * cell_h
        parts.append(f'<text x="{left-12}" y="{y+27}" text-anchor="end" font-family="Arial" font-size="13">{svg_escape(short_label(group))}</text>')
        for c_idx, criterion in enumerate(CRITERIA):
            vals = numeric_scores([r for r in rows if r[group_col] == group], criterion)
            med = median(vals) if vals else 0
            rounded = int(round(med))
            fill = colors.get(rounded, "#eee")
            x = left + c_idx * cell_w
            text_fill = "white" if rounded in (1, 2, 5) else "#111"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h-4}" fill="{fill}" stroke="#fff"/>')
            parts.append(f'<text x="{x+cell_w/2}" y="{y+26}" text-anchor="middle" font-family="Arial" font-size="15" font-weight="700" fill="{text_fill}">{med:g}</text>')
    parts.append("</svg>")
    (CHARTS / f"median_scores_by_{group_col}_heatmap.svg").write_text("\n".join(parts), encoding="utf-8")


def charts(rows: list[dict[str, str]]) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    for group_col in GROUP_COLS:
        for criterion in CRITERIA:
            likert_chart(rows, group_col, criterion)
        median_chart(rows, group_col)


def summary_markdown(rows: list[dict[str, str]]) -> None:
    lines = [
        "# Human Evaluation Likert Analysis",
        "",
        f"Input rows: {len(rows)} evaluator responses.",
        "",
        "Recommended reporting: medians and IQR for Likert scores, 100% stacked Likert distributions, Kruskal-Wallis tests, and Dunn-Holm posthoc comparisons only when Kruskal-Wallis is significant.",
        "",
        "Generated files:",
        "- `descriptive_stats_by_method.csv`",
        "- `descriptive_stats_by_llm_used.csv`",
        "- `likert_distribution_by_method.csv`",
        "- `likert_distribution_by_llm_used.csv`",
        "- `kruskal_wallis_by_method.csv`",
        "- `kruskal_wallis_by_llm_used.csv`",
        "- `dunn_posthoc_by_method.csv`",
        "- `dunn_posthoc_by_llm_used.csv`",
        "- `charts/*.svg`",
        "",
        "Interpretation note: means are included only as supplementary descriptive values; medians and IQR are preferable for Likert-scale data.",
    ]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_rows()
    descriptive_tables(rows)
    distribution_tables(rows)
    statistical_tests(rows)
    charts(rows)
    summary_markdown(rows)
    print(f"input_rows={len(rows)}")
    print(f"output_dir={OUT}")
    print(f"charts_dir={CHARTS}")


if __name__ == "__main__":
    main()
