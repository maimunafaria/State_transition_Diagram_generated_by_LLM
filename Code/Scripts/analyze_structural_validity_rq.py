#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METRICS_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "metrics"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "plantuml_pipeline" / "rq_structural_validity"
DEFAULT_METHODS = ("Zero-shot", "Few-shot", "RAG")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def run_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row["model"],
        row["method"],
        row["run_id"],
        row["case_id"],
        row["run_file"],
    )


def percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100.0), 2) if denominator else 0.0


def format_p_value(value: float) -> str:
    if value < 1e-8:
        return "<1e-8"
    return f"{value:.8f}".rstrip("0").rstrip(".")


def method_rows(
    rows: list[dict[str, str]],
    methods: tuple[str, ...],
) -> list[dict[str, str]]:
    method_set = set(methods)
    return [row for row in rows if row["method"] in method_set]


def summarize_pass_rates(
    rows: list[dict[str, str]],
    valid_field: str = "valid",
) -> list[dict[str, object]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[row["method"]]["total"] += 1
        grouped[row["method"]]["valid" if bool_value(row[valid_field]) else "invalid"] += 1

    output: list[dict[str, object]] = []
    for method in sorted(grouped):
        total = grouped[method]["total"]
        valid = grouped[method]["valid"]
        invalid = grouped[method]["invalid"]
        output.append(
            {
                "method": method,
                "total": total,
                "valid": valid,
                "invalid": invalid,
                "validity_percent": percent(valid, total),
            }
        )
    return output


def summarize_pass_rates_by(
    rows: list[dict[str, object]],
    group_fields: tuple[str, ...],
    valid_field: str = "valid",
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        grouped[key]["total"] += 1
        grouped[key]["valid" if bool_value(row[valid_field]) else "invalid"] += 1

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        total = grouped[key]["total"]
        valid = grouped[key]["valid"]
        invalid = grouped[key]["invalid"]
        output.append(
            {
                **dict(zip(group_fields, key)),
                "total": total,
                "valid": valid,
                "invalid": invalid,
                "validity_percent": percent(valid, total),
            }
        )
    return output


def split_issues(issue_text: str) -> list[str]:
    return [part.strip() for part in issue_text.split("|") if part.strip()]


def violation_type(issue: str) -> str:
    clean = issue.strip()
    mappings = [
        (r"^missing_initial_state_transition", "missing_initial_state"),
        (r"^multiple_initial_state_transitions", "multiple_initial_states"),
        (r"^missing_final_state_transition", "missing_final_state"),
        (r"^duplicate_transitions_detected", "duplicate_transitions"),
        (r"^unreachable_states_detected", "unreachable_states"),
        (r"^unreachable:", "unreachable_state_detail"),
        (r"^orphan_states_detected", "orphan_states"),
        (r"^orphan:", "orphan_state_detail"),
        (r"^choice_node_without_outgoing_transitions", "invalid_choice_node"),
        (r"^choice_node_without_guarded_outgoing_transitions", "invalid_choice_guards"),
        (r"^fork_without_multiple_outgoing_branches", "invalid_fork_node"),
        (r"^join_without_multiple_incoming_branches", "invalid_join_node"),
        (r"^history_state_used_without_composite_state", "invalid_history_state"),
        (r"^candidate_line_\d+:", "parse_warning"),
        (r"^plantuml_syntax_error", "plantuml_syntax_error"),
        (r"^plantuml_command_not_found", "plantuml_check_unavailable"),
    ]
    for pattern, label in mappings:
        if re.search(pattern, clean):
            return label
    return re.sub(r"[^a-z0-9]+", "_", clean.lower()).strip("_") or "unknown"


def countable_violation_types(issues: list[str]) -> list[str]:
    details_to_skip = {"unreachable_state_detail", "orphan_state_detail"}
    return [kind for kind in map(violation_type, issues) if kind not in details_to_skip]


def build_diagram_level_rows(
    plantuml_rows: list[dict[str, str]],
    state_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    plantuml_by_key = {run_key(row): row for row in plantuml_rows}
    diagram_rows: list[dict[str, object]] = []
    for state_row in state_rows:
        key = run_key(state_row)
        plantuml_row = plantuml_by_key.get(key)
        if not plantuml_row:
            continue
        issues = split_issues(state_row.get("issues", ""))
        violation_types = countable_violation_types(issues)
        plantuml_valid = bool_value(plantuml_row["valid"])
        structural_valid = plantuml_valid and bool_value(state_row["valid"])
        diagram_rows.append(
            {
                "model": state_row["model"],
                "method": state_row["method"],
                "run_id": state_row["run_id"],
                "case_id": state_row["case_id"],
                "run_file": state_row["run_file"],
                "plantuml_valid": plantuml_valid,
                "structural_valid": structural_valid,
                "violation_count": len(violation_types) if plantuml_valid else "",
                "violation_types": ";".join(violation_types) if plantuml_valid else "",
                "path": state_row["path"],
            }
        )
    return diagram_rows


def summarize_violation_counts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row["plantuml_valid"]:
            grouped[str(row["method"])].append(int(row["violation_count"]))

    output: list[dict[str, object]] = []
    for method in sorted(grouped):
        values = grouped[method]
        output.append(
            {
                "method": method,
                "plantuml_valid_diagrams": len(values),
                "mean_violations": round(mean(values), 4) if values else 0.0,
                "median_violations": round(median(values), 4) if values else 0.0,
                "max_violations": max(values) if values else 0,
                "zero_violation_diagrams": sum(1 for value in values if value == 0),
            }
        )
    return output


def summarize_violation_counts_by(
    rows: list[dict[str, object]],
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for row in rows:
        if row["plantuml_valid"]:
            key = tuple(row[field] for field in group_fields)
            grouped[key].append(int(row["violation_count"]))

    output: list[dict[str, object]] = []
    for key in sorted(grouped):
        values = grouped[key]
        output.append(
            {
                **dict(zip(group_fields, key)),
                "plantuml_valid_diagrams": len(values),
                "mean_violations": round(mean(values), 4) if values else 0.0,
                "median_violations": round(median(values), 4) if values else 0.0,
                "max_violations": max(values) if values else 0,
                "zero_violation_diagrams": sum(1 for value in values if value == 0),
            }
        )
    return output


def summarize_violation_types(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    denominator_by_method: Counter[str] = Counter()
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if not row["plantuml_valid"]:
            continue
        method = str(row["method"])
        denominator_by_method[method] += 1
        for kind in str(row["violation_types"]).split(";"):
            if kind:
                counts[(method, kind)] += 1

    output: list[dict[str, object]] = []
    for (method, kind), count in sorted(counts.items()):
        total = denominator_by_method[method]
        output.append(
            {
                "method": method,
                "violation_type": kind,
                "count": count,
                "plantuml_valid_diagrams": total,
                "frequency_percent": percent(count, total),
            }
        )
    return output


def summarize_violation_types_by(
    rows: list[dict[str, object]],
    group_fields: tuple[str, ...],
) -> list[dict[str, object]]:
    denominator_by_group: Counter[tuple[object, ...]] = Counter()
    counts: Counter[tuple[object, ...]] = Counter()
    for row in rows:
        if not row["plantuml_valid"]:
            continue
        group_key = tuple(row[field] for field in group_fields)
        denominator_by_group[group_key] += 1
        for kind in str(row["violation_types"]).split(";"):
            if kind:
                counts[(*group_key, kind)] += 1

    output: list[dict[str, object]] = []
    for key, count in sorted(counts.items()):
        group_key = key[:-1]
        kind = key[-1]
        total = denominator_by_group[group_key]
        output.append(
            {
                **dict(zip(group_fields, group_key)),
                "violation_type": kind,
                "count": count,
                "plantuml_valid_diagrams": total,
                "frequency_percent": percent(count, total),
            }
        )
    return output


def chi_square_sf(statistic: float, df: int) -> float | None:
    # Closed forms for the degrees of freedom used by the planned comparisons.
    if df == 1:
        return math.erfc(math.sqrt(statistic / 2.0))
    if df == 2:
        return math.exp(-statistic / 2.0)
    return None


def rank_values(values: list[float]) -> tuple[list[float], list[int]]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    tie_sizes: list[int] = []
    idx = 0
    while idx < len(indexed):
        end = idx + 1
        while end < len(indexed) and indexed[end][1] == indexed[idx][1]:
            end += 1
        average_rank = (idx + 1 + end) / 2.0
        for original_idx, _value in indexed[idx:end]:
            ranks[original_idx] = average_rank
        tie_size = end - idx
        if tie_size > 1:
            tie_sizes.append(tie_size)
        idx = end
    return ranks, tie_sizes


def chi_square_test(rows: list[dict[str, str]], valid_field: str = "valid") -> dict[str, object]:
    grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if bool_value(row[valid_field]):
            grouped[row["method"]][0] += 1
        else:
            grouped[row["method"]][1] += 1

    methods = sorted(grouped)
    table = [grouped[method] for method in methods]
    result: dict[str, object] = {
        "test": "chi-square independence",
        "methods": ";".join(methods),
        "table_valid_invalid": ";".join(f"{v}/{i}" for v, i in table),
    }
    row_totals = [sum(row) for row in table]
    col_totals = [sum(row[col] for row in table) for col in range(2)]
    grand_total = sum(row_totals)
    statistic = 0.0
    for row_idx, row in enumerate(table):
        for col_idx, observed in enumerate(row):
            expected = row_totals[row_idx] * col_totals[col_idx] / grand_total
            if expected:
                statistic += ((observed - expected) ** 2) / expected
    df = (len(table) - 1) * (len(table[0]) - 1)
    p_value = chi_square_sf(statistic, df)
    if p_value is None:
        result.update(
            {
                "statistic": round(float(statistic), 6),
                "df": df,
                "p_value": "",
                "note": "p-value omitted because this script only implements chi-square survival for df=1 or df=2.",
            }
        )
        return result
    result.update(
        {
            "statistic": round(float(statistic), 6),
            "df": int(df),
            "p_value": format_p_value(float(p_value)),
            "note": "",
        }
    )
    return result


def fisher_pairwise_tests(rows: list[dict[str, str]], valid_field: str = "valid") -> list[dict[str, object]]:
    grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        if bool_value(row[valid_field]):
            grouped[row["method"]][0] += 1
        else:
            grouped[row["method"]][1] += 1

    output: list[dict[str, object]] = []
    for a, b in itertools.combinations(sorted(grouped), 2):
        table = [grouped[a], grouped[b]]
        odds_ratio, p_value = fisher_exact_two_sided(table)
        row: dict[str, object] = {
            "test": "Fisher exact pairwise",
            "method_a": a,
            "method_b": b,
            "table_a_b_valid_invalid": f"{grouped[a][0]}/{grouped[a][1]};{grouped[b][0]}/{grouped[b][1]}",
            "odds_ratio": round(float(odds_ratio), 6) if math.isfinite(float(odds_ratio)) else str(odds_ratio),
            "p_value": format_p_value(float(p_value)),
            "note": "",
        }
        output.append(row)
    return output


def fisher_exact_two_sided(table: list[list[int]]) -> tuple[float, float]:
    a, b = table[0]
    c, d = table[1]
    row1 = a + b
    row2 = c + d
    col1 = a + c
    total = row1 + row2

    def hypergeom(x: int) -> float:
        return (
            math.comb(col1, x)
            * math.comb(total - col1, row1 - x)
            / math.comb(total, row1)
        )

    observed_prob = hypergeom(a)
    min_x = max(0, row1 - (total - col1))
    max_x = min(row1, col1)
    p_value = sum(
        prob
        for x in range(min_x, max_x + 1)
        for prob in [hypergeom(x)]
        if prob <= observed_prob + 1e-12
    )
    if b * c == 0:
        odds_ratio = math.inf if a * d > 0 else 0.0
    else:
        odds_ratio = (a * d) / (b * c)
    return odds_ratio, min(p_value, 1.0)


def kruskal_wallis_test(rows: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row["plantuml_valid"]:
            grouped[str(row["method"])].append(int(row["violation_count"]))

    methods = sorted(grouped)
    result: dict[str, object] = {
        "test": "Kruskal-Wallis",
        "methods": ";".join(methods),
        "n_by_method": ";".join(f"{method}:{len(grouped[method])}" for method in methods),
    }
    values: list[float] = []
    labels: list[str] = []
    for method in methods:
        for value in grouped[method]:
            values.append(float(value))
            labels.append(method)
    ranks, tie_sizes = rank_values(values)
    total_n = len(values)
    rank_sums: Counter[str] = Counter()
    for label, rank in zip(labels, ranks):
        rank_sums[label] += rank
    h = (12 / (total_n * (total_n + 1))) * sum(
        (rank_sums[method] ** 2) / len(grouped[method]) for method in methods
    ) - 3 * (total_n + 1)
    tie_correction = 1.0 - (
        sum((tie ** 3) - tie for tie in tie_sizes) / ((total_n ** 3) - total_n)
        if total_n > 1
        else 0.0
    )
    statistic = h / tie_correction if tie_correction else h
    df = len(methods) - 1
    p_value = chi_square_sf(statistic, df)
    if p_value is None:
        result.update(
            {
                "statistic": round(float(statistic), 6),
                "df": df,
                "p_value": "",
                "note": "p-value omitted because this script only implements chi-square survival for df=1 or df=2.",
            }
        )
        return result
    result.update(
        {
            "statistic": round(float(statistic), 6),
            "df": df,
            "p_value": format_p_value(float(p_value)),
            "note": "",
        }
    )
    return result


def dunn_posthoc(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    records = [
        (str(row["method"]), float(row["violation_count"]))
        for row in rows
        if row["plantuml_valid"]
    ]
    methods = sorted({method for method, _value in records})
    values = [value for _method, value in records]
    labels = [method for method, _value in records]
    ranks, tie_sizes = rank_values(values)
    total_n = len(values)
    rank_sums: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for label, rank in zip(labels, ranks):
        rank_sums[label] += rank
        counts[label] += 1

    tie_term = sum((tie ** 3) - tie for tie in tie_sizes)
    variance = (total_n * (total_n + 1) / 12.0) - (
        tie_term / (12.0 * (total_n - 1)) if total_n > 1 else 0.0
    )
    raw_rows: list[dict[str, object]] = []
    for a, b in itertools.combinations(methods, 2):
        mean_rank_a = rank_sums[a] / counts[a]
        mean_rank_b = rank_sums[b] / counts[b]
        z_value = (mean_rank_a - mean_rank_b) / math.sqrt(
            variance * ((1 / counts[a]) + (1 / counts[b]))
        )
        p_value = math.erfc(abs(z_value) / math.sqrt(2))
        raw_rows.append(
            {
                "method_a": a,
                "method_b": b,
                "z": z_value,
                "p_value_raw": p_value,
            }
        )

    ordered = sorted(enumerate(raw_rows), key=lambda item: float(item[1]["p_value_raw"]))
    adjusted_by_index: dict[int, float] = {}
    previous = 0.0
    total_tests = len(raw_rows)
    for rank_idx, (original_idx, row) in enumerate(ordered, start=1):
        adjusted = min(float(row["p_value_raw"]) * (total_tests - rank_idx + 1), 1.0)
        adjusted = max(adjusted, previous)
        adjusted_by_index[original_idx] = adjusted
        previous = adjusted

    output: list[dict[str, object]] = []
    for idx, row in enumerate(raw_rows):
        output.append(
            {
                "method_a": row["method_a"],
                "method_b": row["method_b"],
                "z": round(float(row["z"]), 6),
                "p_value_raw": format_p_value(float(row["p_value_raw"])),
                "p_value_holm": format_p_value(float(adjusted_by_index[idx])),
                "note": "",
            }
        )
    return output


def per_model_stats(
    plantuml_rows: list[dict[str, str]],
    structural_rows: list[dict[str, object]],
    diagram_rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    models = sorted({row["model"] for row in plantuml_rows})
    stats_rows: list[dict[str, object]] = []
    fisher_rows: list[dict[str, object]] = []
    dunn_rows: list[dict[str, object]] = []

    for model in models:
        model_plantuml_rows = [row for row in plantuml_rows if row["model"] == model]
        model_structural_rows = [row for row in structural_rows if row["model"] == model]
        model_diagram_rows = [row for row in diagram_rows if row["model"] == model]

        stats_rows.extend(
            [
                {
                    "model": model,
                    "metric": "PlantUML syntax validity",
                    **chi_square_test(model_plantuml_rows),
                },
                {
                    "model": model,
                    "metric": "Structural validity",
                    **chi_square_test(model_structural_rows),
                },
                {
                    "model": model,
                    "metric": "Structural violation count",
                    **kruskal_wallis_test(model_diagram_rows),
                },
            ]
        )
        fisher_rows.extend(
            [{"model": model, "metric": "PlantUML syntax validity", **row} for row in fisher_pairwise_tests(model_plantuml_rows)]
            + [{"model": model, "metric": "Structural validity", **row} for row in fisher_pairwise_tests(model_structural_rows)]
        )
        dunn_rows.extend(
            {"model": model, **row}
            for row in dunn_posthoc(model_diagram_rows)
        )

    return stats_rows, fisher_rows, dunn_rows


def write_markdown_summary(
    path: Path,
    methods: tuple[str, ...],
    plantuml_summary: list[dict[str, object]],
    structural_summary: list[dict[str, object]],
    violation_summary: list[dict[str, object]],
    stats_rows: list[dict[str, object]],
    model_plantuml_summary: list[dict[str, object]],
    model_structural_summary: list[dict[str, object]],
    model_violation_summary: list[dict[str, object]],
    model_stats_rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def table(rows: list[dict[str, object]], fields: list[str]) -> str:
        lines = [
            "| " + " | ".join(fields) + " |",
            "| " + " | ".join("---" for _ in fields) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
        return "\n".join(lines)

    content = [
        "# Structural Validity RQ Analysis",
        "",
        f"Compared methods: {', '.join(methods)}.",
        "",
        "Structural validity and violation counts are computed only on diagrams that passed PlantUML syntax checking.",
        "",
        "## PlantUML Syntax Validity",
        table(plantuml_summary, ["method", "total", "valid", "invalid", "validity_percent"]),
        "",
        "## Structural Validity on PlantUML-Valid Diagrams",
        table(structural_summary, ["method", "total", "valid", "invalid", "validity_percent"]),
        "",
        "## Violation Counts",
        table(
            violation_summary,
            [
                "method",
                "plantuml_valid_diagrams",
                "mean_violations",
                "median_violations",
                "max_violations",
                "zero_violation_diagrams",
            ],
        ),
        "",
        "## Statistical Tests",
        table(stats_rows, sorted({key for row in stats_rows for key in row})),
        "",
        "## By LLM: PlantUML Syntax Validity",
        table(model_plantuml_summary, ["model", "method", "total", "valid", "invalid", "validity_percent"]),
        "",
        "## By LLM: Structural Validity on PlantUML-Valid Diagrams",
        table(model_structural_summary, ["model", "method", "total", "valid", "invalid", "validity_percent"]),
        "",
        "## By LLM: Violation Counts",
        table(
            model_violation_summary,
            [
                "model",
                "method",
                "plantuml_valid_diagrams",
                "mean_violations",
                "median_violations",
                "max_violations",
                "zero_violation_diagrams",
            ],
        ),
        "",
        "## By LLM: Statistical Tests",
        table(model_stats_rows, sorted({key for row in model_stats_rows for key in row})),
        "",
    ]
    path.write_text("\n".join(content), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze how zero-shot, few-shot, and RAG affect structural validity."
    )
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--method",
        action="append",
        default=[],
        help="Method label to include. Repeatable. Defaults to Zero-shot, Few-shot, RAG.",
    )
    parser.add_argument(
        "--pairwise-fisher",
        action="store_true",
        help="Also write pairwise Fisher exact tests for pass/fail rates.",
    )
    args = parser.parse_args()

    metrics_dir = args.metrics_dir.resolve()
    output_dir = args.output_dir.resolve()
    methods = tuple(args.method) if args.method else DEFAULT_METHODS

    plantuml_rows = method_rows(read_csv(metrics_dir / "plantuml_validity_cases.csv"), methods)
    state_rows = method_rows(read_csv(metrics_dir / "state_rules_validity_cases.csv"), methods)

    diagram_rows = build_diagram_level_rows(plantuml_rows, state_rows)
    structural_rows = [
        {
            **row,
            "valid": str(row["structural_valid"]),
        }
        for row in diagram_rows
        if row["plantuml_valid"]
    ]

    plantuml_summary = summarize_pass_rates(plantuml_rows)
    structural_summary = summarize_pass_rates(structural_rows)
    violation_count_summary = summarize_violation_counts(diagram_rows)
    violation_type_summary = summarize_violation_types(diagram_rows)
    model_plantuml_summary = summarize_pass_rates_by(plantuml_rows, ("model", "method"))
    model_structural_summary = summarize_pass_rates_by(structural_rows, ("model", "method"))
    model_violation_count_summary = summarize_violation_counts_by(diagram_rows, ("model", "method"))
    model_violation_type_summary = summarize_violation_types_by(diagram_rows, ("model", "method"))
    model_stats_rows, model_fisher_rows, model_dunn_rows = per_model_stats(
        plantuml_rows,
        structural_rows,
        diagram_rows,
    )

    stats_rows = [
        {"metric": "PlantUML syntax validity", **chi_square_test(plantuml_rows)},
        {"metric": "Structural validity", **chi_square_test(structural_rows)},
        {"metric": "Structural violation count", **kruskal_wallis_test(diagram_rows)},
    ]

    write_csv(
        output_dir / "diagram_level_structural_validity.csv",
        diagram_rows,
        [
            "model",
            "method",
            "run_id",
            "case_id",
            "run_file",
            "plantuml_valid",
            "structural_valid",
            "violation_count",
            "violation_types",
            "path",
        ],
    )
    write_csv(
        output_dir / "plantuml_syntax_validity_by_method.csv",
        plantuml_summary,
        ["method", "total", "valid", "invalid", "validity_percent"],
    )
    write_csv(
        output_dir / "plantuml_syntax_validity_by_model_method.csv",
        model_plantuml_summary,
        ["model", "method", "total", "valid", "invalid", "validity_percent"],
    )
    write_csv(
        output_dir / "structural_validity_by_method_on_plantuml_valid.csv",
        structural_summary,
        ["method", "total", "valid", "invalid", "validity_percent"],
    )
    write_csv(
        output_dir / "structural_validity_by_model_method_on_plantuml_valid.csv",
        model_structural_summary,
        ["model", "method", "total", "valid", "invalid", "validity_percent"],
    )
    write_csv(
        output_dir / "violation_count_summary_by_method.csv",
        violation_count_summary,
        [
            "method",
            "plantuml_valid_diagrams",
            "mean_violations",
            "median_violations",
            "max_violations",
            "zero_violation_diagrams",
        ],
    )
    write_csv(
        output_dir / "violation_count_summary_by_model_method.csv",
        model_violation_count_summary,
        [
            "model",
            "method",
            "plantuml_valid_diagrams",
            "mean_violations",
            "median_violations",
            "max_violations",
            "zero_violation_diagrams",
        ],
    )
    write_csv(
        output_dir / "violation_type_distribution_by_method.csv",
        violation_type_summary,
        ["method", "violation_type", "count", "plantuml_valid_diagrams", "frequency_percent"],
    )
    write_csv(
        output_dir / "violation_type_distribution_by_model_method.csv",
        model_violation_type_summary,
        [
            "model",
            "method",
            "violation_type",
            "count",
            "plantuml_valid_diagrams",
            "frequency_percent",
        ],
    )
    write_csv(
        output_dir / "statistical_tests.csv",
        stats_rows,
        sorted({key for row in stats_rows for key in row}),
    )
    write_csv(
        output_dir / "statistical_tests_by_model.csv",
        model_stats_rows,
        sorted({key for row in model_stats_rows for key in row}),
    )

    if args.pairwise_fisher:
        fisher_rows = (
            [{"metric": "PlantUML syntax validity", **row} for row in fisher_pairwise_tests(plantuml_rows)]
            + [{"metric": "Structural validity", **row} for row in fisher_pairwise_tests(structural_rows)]
        )
        write_csv(
            output_dir / "pairwise_fisher_tests.csv",
            fisher_rows,
            sorted({key for row in fisher_rows for key in row}),
        )
        write_csv(
            output_dir / "pairwise_fisher_tests_by_model.csv",
            model_fisher_rows,
            sorted({key for row in model_fisher_rows for key in row}),
        )

    dunn_rows = dunn_posthoc(diagram_rows)
    write_csv(
        output_dir / "dunn_posthoc_violation_counts.csv",
        dunn_rows,
        sorted({key for row in dunn_rows for key in row}),
    )
    write_csv(
        output_dir / "dunn_posthoc_violation_counts_by_model.csv",
        model_dunn_rows,
        sorted({key for row in model_dunn_rows for key in row}),
    )
    write_markdown_summary(
        output_dir / "summary.md",
        methods,
        plantuml_summary,
        structural_summary,
        violation_count_summary,
        stats_rows,
        model_plantuml_summary,
        model_structural_summary,
        model_violation_count_summary,
        model_stats_rows,
    )

    print(f"Wrote RQ analysis tables to: {output_dir}")
    print(f"Summary: {output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
