from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path


JUDGES = ["deepseek", "llama", "prometheus"]
CRITERIA = [
    "completeness",
    "correctness",
    "understandability",
    "terminological_alignment",
]
JUDGE_TO_GENERATOR = {
    "deepseek": "DeepSeek_R1_14B",
    "llama": "Llama_3.1_8B",
}


def parse_score(value: str) -> int | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if not number.is_integer():
        return None
    integer = int(number)
    if integer < 1 or integer > 5:
        return None
    return integer


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rank_average(values: list[int]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 1
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg_rank = (position + (position + (j - i) - 1)) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg_rank
        position += j - i
        i = j
    return ranks


def pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    dx = [v - mean_x for v in x]
    dy = [v - mean_y for v in y]
    denom_x = math.sqrt(sum(v * v for v in dx))
    denom_y = math.sqrt(sum(v * v for v in dy))
    if denom_x == 0 or denom_y == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / (denom_x * denom_y)


def spearman(values_a: list[int], values_b: list[int]) -> float | None:
    if len(values_a) < 2:
        return None
    return pearson(rank_average(values_a), rank_average(values_b))


def mae(values_a: list[int], values_b: list[int]) -> float | None:
    diffs = [abs(a - b) for a, b in zip(values_a, values_b)]
    return mean(diffs)


def exact_agreement(values_a: list[int], values_b: list[int]) -> float | None:
    if not values_a:
        return None
    matches = sum(1 for a, b in zip(values_a, values_b) if a == b)
    return 100.0 * matches / len(values_a)


def within_one_agreement(values_a: list[int], values_b: list[int]) -> float | None:
    if not values_a:
        return None
    matches = sum(1 for a, b in zip(values_a, values_b) if abs(a - b) <= 1)
    return 100.0 * matches / len(values_a)


def mean_signed_error(values_a: list[int], values_b: list[int]) -> float | None:
    diffs = [a - b for a, b in zip(values_a, values_b)]
    return mean(diffs)


def weighted_cohen_kappa(values_a: list[int], values_b: list[int], min_rating: int = 1, max_rating: int = 5) -> float | None:
    n = len(values_a)
    if n == 0:
        return None
    categories = list(range(min_rating, max_rating + 1))
    size = len(categories)
    index = {cat: i for i, cat in enumerate(categories)}

    observed = [[0.0 for _ in categories] for _ in categories]
    for a, b in zip(values_a, values_b):
        observed[index[a]][index[b]] += 1.0
    observed = [[cell / n for cell in row] for row in observed]

    hist_a = [0.0 for _ in categories]
    hist_b = [0.0 for _ in categories]
    for a in values_a:
        hist_a[index[a]] += 1.0 / n
    for b in values_b:
        hist_b[index[b]] += 1.0 / n

    expected = [
        [hist_a[i] * hist_b[j] for j in range(size)]
        for i in range(size)
    ]

    if size == 1:
        return None

    weights = [
        [((i - j) ** 2) / ((size - 1) ** 2) for j in range(size)]
        for i in range(size)
    ]
    observed_weighted = sum(weights[i][j] * observed[i][j] for i in range(size) for j in range(size))
    expected_weighted = sum(weights[i][j] * expected[i][j] for i in range(size) for j in range(size))
    if expected_weighted == 0:
        return None
    return 1.0 - (observed_weighted / expected_weighted)


def format_metric(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def paired_scores(rows: list[dict[str, str]], judge_column: str, reference_column: str) -> tuple[list[int], list[int]]:
    judge_scores: list[int] = []
    ref_scores: list[int] = []
    for row in rows:
        judge_score = parse_score(row.get(judge_column, ""))
        ref_score = parse_score(row.get(reference_column, ""))
        if judge_score is None or ref_score is None:
            continue
        judge_scores.append(judge_score)
        ref_scores.append(ref_score)
    return judge_scores, ref_scores


def metric_row(rows: list[dict[str, str]], judge_column: str, reference_column: str) -> dict[str, str]:
    judge_scores, ref_scores = paired_scores(rows, judge_column, reference_column)
    return {
        "n_valid": str(len(judge_scores)),
        "spearman_correlation": format_metric(spearman(judge_scores, ref_scores)),
        "mean_absolute_error": format_metric(mae(judge_scores, ref_scores)),
        "exact_agreement_percent": format_metric(exact_agreement(judge_scores, ref_scores)),
        "within_one_point_agreement_percent": format_metric(within_one_agreement(judge_scores, ref_scores)),
        "weighted_cohen_kappa": format_metric(weighted_cohen_kappa(judge_scores, ref_scores)),
        "mean_signed_error": format_metric(mean_signed_error(judge_scores, ref_scores)),
    }


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze LLM-as-a-Judge results against human scores."
    )
    parser.add_argument(
        "--input-csv",
        required=True,
        help="Normalized input CSV with one row per diagram and criterion.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/plantuml_pipeline/llm_judge/analysis",
        help="Directory for output CSVs.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)

    with input_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    overall_rows: list[dict[str, str]] = []
    criterion_rows: list[dict[str, str]] = []
    repair_rows: list[dict[str, str]] = []
    inter_judge_rows: list[dict[str, str]] = []
    bias_rows: list[dict[str, str]] = []

    for judge in JUDGES:
        result = metric_row(rows, f"{judge}_score", "human_score")
        overall_rows.append({"judge": judge, **result})

    for criterion in CRITERIA:
        criterion_subset = [row for row in rows if (row.get("criterion") or "").strip() == criterion]
        for judge in JUDGES:
            result = metric_row(criterion_subset, f"{judge}_score", "human_score")
            criterion_rows.append({"criterion": criterion, "judge": judge, **result})

    repair_strategies = sorted({(row.get("repair_strategy") or "").strip() for row in rows if (row.get("repair_strategy") or "").strip()})
    for strategy in repair_strategies:
        strategy_subset = [row for row in rows if (row.get("repair_strategy") or "").strip() == strategy]
        for judge in JUDGES:
            result = metric_row(strategy_subset, f"{judge}_score", "human_score")
            repair_rows.append({"repair_strategy": strategy, "judge": judge, **result})

    judge_pairs = [
        ("deepseek", "llama"),
        ("deepseek", "prometheus"),
        ("llama", "prometheus"),
    ]
    for judge_a, judge_b in judge_pairs:
        result = metric_row(rows, f"{judge_a}_score", f"{judge_b}_score")
        inter_judge_rows.append(
            {
                "judge_a": judge_a,
                "judge_b": judge_b,
                **result,
            }
        )

    for judge in JUDGES:
        same_generator = JUDGE_TO_GENERATOR.get(judge)
        if same_generator is None:
            bias_rows.append(
                {
                    "judge": judge,
                    "same_model_generator": "",
                    "n_valid_same_model": "0",
                    "n_valid_other_models": "0",
                    "mae_same_model": "",
                    "mae_other_models": "",
                    "mean_signed_error_same_model": "",
                    "mean_signed_error_other_models": "",
                    "exact_agreement_same_model_percent": "",
                    "exact_agreement_other_models_percent": "",
                    "within_one_same_model_percent": "",
                    "within_one_other_models_percent": "",
                    "bias_note": "not_applicable",
                }
            )
            continue

        same_rows = [row for row in rows if (row.get("generator_model") or "").strip() == same_generator]
        other_rows = [row for row in rows if (row.get("generator_model") or "").strip() != same_generator]
        same_scores, same_human = paired_scores(same_rows, f"{judge}_score", "human_score")
        other_scores, other_human = paired_scores(other_rows, f"{judge}_score", "human_score")
        bias_rows.append(
            {
                "judge": judge,
                "same_model_generator": same_generator,
                "n_valid_same_model": str(len(same_scores)),
                "n_valid_other_models": str(len(other_scores)),
                "mae_same_model": format_metric(mae(same_scores, same_human)),
                "mae_other_models": format_metric(mae(other_scores, other_human)),
                "mean_signed_error_same_model": format_metric(mean_signed_error(same_scores, same_human)),
                "mean_signed_error_other_models": format_metric(mean_signed_error(other_scores, other_human)),
                "exact_agreement_same_model_percent": format_metric(exact_agreement(same_scores, same_human)),
                "exact_agreement_other_models_percent": format_metric(exact_agreement(other_scores, other_human)),
                "within_one_same_model_percent": format_metric(within_one_agreement(same_scores, same_human)),
                "within_one_other_models_percent": format_metric(within_one_agreement(other_scores, other_human)),
                "bias_note": "",
            }
        )

    write_csv(
        output_dir / "judge_overall_results.csv",
        overall_rows,
        [
            "judge",
            "n_valid",
            "spearman_correlation",
            "mean_absolute_error",
            "exact_agreement_percent",
            "within_one_point_agreement_percent",
            "weighted_cohen_kappa",
            "mean_signed_error",
        ],
    )
    write_csv(
        output_dir / "judge_criterion_results.csv",
        criterion_rows,
        [
            "criterion",
            "judge",
            "n_valid",
            "spearman_correlation",
            "mean_absolute_error",
            "exact_agreement_percent",
            "within_one_point_agreement_percent",
            "weighted_cohen_kappa",
            "mean_signed_error",
        ],
    )
    write_csv(
        output_dir / "judge_repair_strategy_results.csv",
        repair_rows,
        [
            "repair_strategy",
            "judge",
            "n_valid",
            "spearman_correlation",
            "mean_absolute_error",
            "exact_agreement_percent",
            "within_one_point_agreement_percent",
            "weighted_cohen_kappa",
            "mean_signed_error",
        ],
    )
    write_csv(
        output_dir / "inter_judge_results.csv",
        inter_judge_rows,
        [
            "judge_a",
            "judge_b",
            "n_valid",
            "spearman_correlation",
            "mean_absolute_error",
            "exact_agreement_percent",
            "within_one_point_agreement_percent",
            "weighted_cohen_kappa",
            "mean_signed_error",
        ],
    )
    write_csv(
        output_dir / "self_evaluation_bias.csv",
        bias_rows,
        [
            "judge",
            "same_model_generator",
            "n_valid_same_model",
            "n_valid_other_models",
            "mae_same_model",
            "mae_other_models",
            "mean_signed_error_same_model",
            "mean_signed_error_other_models",
            "exact_agreement_same_model_percent",
            "exact_agreement_other_models_percent",
            "within_one_same_model_percent",
            "within_one_other_models_percent",
            "bias_note",
        ],
    )

    print(f"Wrote outputs to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
