#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

from analyze_llm_judge_results import metric_row


CRITERIA = (
    "completeness",
    "correctness",
    "understandability",
    "terminological_alignment",
)
HUMAN_SCORE_FIELDS = {
    "completeness": "completeness_score",
    "correctness": "correctness_score",
    "understandability": "understandability_score",
    "terminological_alignment": "terminology_alignment_score",
}
JUDGE_ALIASES = {
    "deepseek-r1:14b": "deepseek",
    "llama3.1:8b-instruct-q4_K_M": "llama",
    "ggozad/prometheus2": "prometheus",
}
LONG_FIELDS = (
    "package_diagram_id",
    "judge_diagram_id",
    "case_id",
    "generation_model",
    "generation_method",
    "human_slot",
    "evaluator_id",
    "rating_source",
    "source_generation_method",
    "source_evaluation_id",
    "completeness_score",
    "correctness_score",
    "understandability_score",
    "terminology_alignment_score",
    "completeness_justification",
    "correctness_justification",
    "understandability_justification",
    "terminology_alignment_justification",
)
COVERAGE_FIELDS = (
    "package_diagram_id",
    "judge_diagram_id",
    "case_id",
    "generation_model",
    "generation_method",
    "human_rating_count",
    "human_coverage_source",
)
ANALYSIS_INPUT_FIELDS = (
    "diagram_id",
    "case_id",
    "criterion",
    "human_score",
    "human_mean_score",
    "human_rating_count",
    "deepseek_score",
    "llama_score",
    "prometheus_score",
    "generator_model",
    "repair_strategy",
)
INTER_RATER_FIELDS = (
    "scope",
    "criterion",
    "n_valid",
    "spearman_correlation",
    "mean_absolute_error",
    "exact_agreement_percent",
    "within_one_point_agreement_percent",
    "weighted_cohen_kappa",
    "mean_signed_error",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    fields: tuple[str, ...],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def score(value: str, context: str) -> int:
    text = (value or "").strip()
    try:
        parsed = int(float(text))
    except ValueError as exc:
        raise ValueError(f"Invalid score for {context}: {value!r}") from exc
    if str(float(text)) != str(float(parsed)):
        raise ValueError(f"Non-integral score for {context}: {value!r}")
    if parsed not in range(1, 6):
        raise ValueError(f"Score outside 1-5 for {context}: {parsed}")
    return parsed


def optional_score(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        parsed = int(float(text))
    except ValueError:
        return ""
    return str(parsed) if parsed in range(1, 6) else ""


def half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def rendered_image_hash(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Rendered diagram not found: {path}")
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        payload = (
            rgba.width.to_bytes(4, "big")
            + rgba.height.to_bytes(4, "big")
            + rgba.tobytes()
        )
    return hashlib.sha256(payload).hexdigest()


def human_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row["case_id_full"].strip(),
        row["generation_model"].strip(),
        row["generation_method"].strip(),
    )


def final_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row["case_id"].strip(),
        row["representative_model"].strip(),
        row["representative_method"].strip(),
    )


def judge_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row["case_id"].strip(),
        row["generation_model"].strip(),
        row["generation_method"].strip(),
    )


def normalize_old_rating(
    row: dict[str, str],
    target: dict[str, str],
    slot: int,
    rating_source: str,
    source_method: str,
) -> dict[str, Any]:
    return {
        "package_diagram_id": target["diagram_id"],
        "judge_diagram_id": target["judge_diagram_id"],
        "case_id": target["case_id"],
        "generation_model": target["representative_model"],
        "generation_method": target["representative_method"],
        "human_slot": slot,
        "evaluator_id": row.get("evaluator_id", "").strip(),
        "rating_source": rating_source,
        "source_generation_method": source_method,
        "source_evaluation_id": "",
        "completeness_score": score(
            row.get("completeness_score", ""),
            f"{target['diagram_id']} completeness",
        ),
        "correctness_score": score(
            row.get("correctness_score", ""),
            f"{target['diagram_id']} correctness",
        ),
        "understandability_score": score(
            row.get("understandability_score", ""),
            f"{target['diagram_id']} understandability",
        ),
        "terminology_alignment_score": score(
            row.get("terminology_alignment_score", ""),
            f"{target['diagram_id']} terminology",
        ),
        "completeness_justification": row.get(
            "completeness_justification", ""
        ).strip(),
        "correctness_justification": row.get(
            "correctness_justification", ""
        ).strip(),
        "understandability_justification": row.get(
            "understandability_justification", ""
        ).strip(),
        "terminology_alignment_justification": row.get(
            "terminology_alignment_justification", ""
        ).strip(),
    }


def normalize_new_rating(
    row: dict[str, str],
    target: dict[str, str],
    evaluation_id: str,
) -> dict[str, Any]:
    return {
        "package_diagram_id": target["diagram_id"],
        "judge_diagram_id": target["judge_diagram_id"],
        "case_id": target["case_id"],
        "generation_model": target["representative_model"],
        "generation_method": target["representative_method"],
        "human_slot": 1,
        "evaluator_id": "new_human_01",
        "rating_source": "new_human",
        "source_generation_method": target["representative_method"],
        "source_evaluation_id": evaluation_id,
        "completeness_score": score(
            row.get("completeness", ""),
            f"{evaluation_id} completeness",
        ),
        "correctness_score": score(
            row.get("correctness", ""),
            f"{evaluation_id} correctness",
        ),
        "understandability_score": score(
            row.get("under", ""),
            f"{evaluation_id} understandability",
        ),
        "terminology_alignment_score": score(
            row.get("terminology", ""),
            f"{evaluation_id} terminology",
        ),
        "completeness_justification": "",
        "correctness_justification": "",
        "understandability_justification": "",
        "terminology_alignment_justification": "",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Combine existing and newly supplied human ratings for the final "
            "97 valid diagrams, then align them with the latest three-judge CSV."
        )
    )
    parser.add_argument(
        "--new-human-csv",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--new-human-mapping",
        type=Path,
        default=Path(
            "final_results/need_to_validate_by_human/PRIVATE_mapping.csv"
        ),
    )
    parser.add_argument(
        "--final-diagrams-csv",
        type=Path,
        default=Path(
            "final_results/valid_diagrams/unique_valid_diagrams.csv"
        ),
    )
    parser.add_argument(
        "--final-valid-root",
        type=Path,
        default=Path("final_results/valid_diagrams"),
    )
    parser.add_argument(
        "--old-human-long-csv",
        type=Path,
        default=Path(
            "results/plantuml_pipeline/llm_judge/human_scores_valid99_clean/"
            "human_scores_valid99_two_raters_long.csv"
        ),
    )
    parser.add_argument(
        "--old-evaluated-root",
        type=Path,
        default=Path("valid_diagrams_from_untitled_raw_deduped"),
    )
    parser.add_argument(
        "--judge-scores-csv",
        type=Path,
        default=Path(
            "final_results/llm_judge/"
            "three_judge_reference_free_final_valid97/judge_scores_long.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "final_results/llm_judge/final_human_comparison"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    final_diagrams = read_csv(args.final_diagrams_csv)
    old_human_rows = read_csv(args.old_human_long_csv)
    new_human_rows = read_csv(args.new_human_csv)
    new_mapping_rows = read_csv(args.new_human_mapping)
    judge_rows = read_csv(args.judge_scores_csv)

    if len(final_diagrams) != 97:
        raise ValueError(
            f"Expected 97 final diagrams, found {len(final_diagrams)}"
        )
    if len(new_human_rows) != 37:
        raise ValueError(
            f"Expected 37 new human ratings, found {len(new_human_rows)}"
        )

    judge_rows_by_key: dict[
        tuple[str, str, str],
        list[dict[str, str]],
    ] = defaultdict(list)
    for row in judge_rows:
        judge_rows_by_key[judge_key(row)].append(row)

    final_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in final_diagrams:
        key = final_key(row)
        matching_judges = judge_rows_by_key.get(key, [])
        diagram_ids = {
            item["diagram_id"].strip()
            for item in matching_judges
            if item.get("diagram_id", "").strip()
        }
        if len(diagram_ids) != 1:
            raise ValueError(
                f"Expected one judge diagram ID for {key}, found {diagram_ids}"
            )
        row["judge_diagram_id"] = next(iter(diagram_ids))
        final_by_key[key] = row

    old_by_key: dict[
        tuple[str, str, str],
        list[dict[str, str]],
    ] = defaultdict(list)
    for row in old_human_rows:
        old_by_key[human_key(row)].append(row)

    new_by_evaluation_id = {
        row["diagram"].strip(): row for row in new_human_rows
    }
    if len(new_by_evaluation_id) != len(new_human_rows):
        raise ValueError("Duplicate diagram IDs in the new human CSV")
    mapping_by_evaluation_id = {
        row["evaluation_id"].strip(): row for row in new_mapping_rows
    }
    if set(new_by_evaluation_id) != set(mapping_by_evaluation_id):
        missing_scores = sorted(
            set(mapping_by_evaluation_id) - set(new_by_evaluation_id)
        )
        unexpected_scores = sorted(
            set(new_by_evaluation_id) - set(mapping_by_evaluation_id)
        )
        raise ValueError(
            "New human/mapping IDs differ. "
            f"Missing={missing_scores}, unexpected={unexpected_scores}"
        )

    new_by_key: dict[tuple[str, str, str], tuple[str, dict[str, str]]] = {}
    for evaluation_id, mapping in mapping_by_evaluation_id.items():
        key = (
            mapping["case_id"].strip(),
            mapping["model"].strip(),
            mapping["method"].strip(),
        )
        if key in new_by_key:
            raise ValueError(f"Duplicate new-human target key: {key}")
        new_by_key[key] = (
            evaluation_id,
            new_by_evaluation_id[evaluation_id],
        )

    # Index previously evaluated rendered diagrams. This recovers code-different
    # but visually identical final diagrams without asking a human to rate twice.
    old_render_index: dict[
        tuple[str, str, str],
        list[tuple[str, tuple[str, str, str]]],
    ] = defaultdict(list)
    for key, ratings in old_by_key.items():
        if len(ratings) < 2:
            continue
        case_id, model, method = key
        png_path = (
            args.old_evaluated_root
            / model
            / method
            / case_id
            / "diagram.png"
        )
        if not png_path.is_file():
            continue
        old_render_index[
            (case_id, model, rendered_image_hash(png_path))
        ].append((method, key))

    final_long_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()

    for target in sorted(
        final_diagrams,
        key=lambda row: (
            row["case_id"],
            row["representative_model"],
            row["representative_method"],
        ),
    ):
        key = final_key(target)
        ratings: list[dict[str, Any]] = []
        coverage_source = ""

        exact_old = old_by_key.get(key, [])
        if len(exact_old) >= 2:
            coverage_source = "existing_exact"
            ratings = [
                normalize_old_rating(
                    row,
                    target,
                    slot=index,
                    rating_source=coverage_source,
                    source_method=key[2],
                )
                for index, row in enumerate(exact_old[:2], start=1)
            ]
        elif key in new_by_key:
            coverage_source = "new_human"
            evaluation_id, new_row = new_by_key[key]
            expected_case_prefix = "_".join(
                target["case_id"].split("_")[:2]
            )
            if new_row["case"].strip() != expected_case_prefix:
                raise ValueError(
                    f"Case mismatch for {evaluation_id}: "
                    f"{new_row['case']} vs {target['case_id']}"
                )
            ratings = [
                normalize_new_rating(
                    new_row,
                    target,
                    evaluation_id,
                )
            ]
        else:
            final_png = Path(target["png_path"])
            render_key = (
                target["case_id"],
                target["representative_model"],
                rendered_image_hash(final_png),
            )
            matches = old_render_index.get(render_key, [])
            if len(matches) != 1:
                raise ValueError(
                    f"No unique human-rating source for final diagram {key}; "
                    f"render matches={matches}"
                )
            source_method, source_key = matches[0]
            coverage_source = "existing_render_equivalent"
            ratings = [
                normalize_old_rating(
                    row,
                    target,
                    slot=index,
                    rating_source=coverage_source,
                    source_method=source_method,
                )
                for index, row in enumerate(
                    old_by_key[source_key][:2],
                    start=1,
                )
            ]

        if not ratings:
            raise ValueError(f"No human ratings resolved for {key}")
        source_counts[coverage_source] += 1
        final_long_rows.extend(ratings)
        coverage_rows.append(
            {
                "package_diagram_id": target["diagram_id"],
                "judge_diagram_id": target["judge_diagram_id"],
                "case_id": target["case_id"],
                "generation_model": target["representative_model"],
                "generation_method": target["representative_method"],
                "human_rating_count": len(ratings),
                "human_coverage_source": coverage_source,
            }
        )

    ratings_by_diagram: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in final_long_rows:
        ratings_by_diagram[str(row["package_diagram_id"])].append(row)

    wide_rows: list[dict[str, Any]] = []
    analysis_input_rows: list[dict[str, Any]] = []
    inter_rater_input: list[dict[str, str]] = []

    for target in sorted(
        final_diagrams,
        key=lambda row: int(row["diagram_id"].split("_")[-1]),
    ):
        ratings = ratings_by_diagram[target["diagram_id"]]
        key = final_key(target)
        judge_by_alias: dict[str, dict[str, str]] = {}
        for judge_row in judge_rows_by_key[key]:
            alias = JUDGE_ALIASES.get(judge_row["judge_model"].strip())
            if alias:
                judge_by_alias[alias] = judge_row

        wide: dict[str, Any] = {
            "package_diagram_id": target["diagram_id"],
            "judge_diagram_id": target["judge_diagram_id"],
            "case_id": target["case_id"],
            "generation_model": target["representative_model"],
            "generation_method": target["representative_method"],
            "human_rating_count": len(ratings),
            "human_coverage_source": ratings[0]["rating_source"],
            "human_evaluator_ids": "|".join(
                str(row["evaluator_id"]) for row in ratings
            ),
        }

        for criterion in CRITERIA:
            score_field = HUMAN_SCORE_FIELDS[criterion]
            judge_score_field = f"{criterion}_score"
            values = [int(row[score_field]) for row in ratings]
            mean_value = sum(values) / len(values)
            consensus = half_up(mean_value)
            wide[f"human1_{criterion}_score"] = values[0]
            wide[f"human2_{criterion}_score"] = (
                values[1] if len(values) > 1 else ""
            )
            wide[f"mean_{criterion}_score"] = f"{mean_value:.4f}"
            wide[f"consensus_{criterion}_score"] = consensus

            judge_values: dict[str, str] = {}
            for alias in ("deepseek", "llama", "prometheus"):
                judge_row = judge_by_alias.get(alias)
                judge_values[alias] = (
                    optional_score(judge_row.get(judge_score_field, ""))
                    if judge_row
                    and judge_row.get("status", "").strip().lower() == "ok"
                    else ""
                )

            analysis_input_rows.append(
                {
                    "diagram_id": target["judge_diagram_id"],
                    "case_id": target["case_id"],
                    "criterion": criterion,
                    "human_score": consensus,
                    "human_mean_score": f"{mean_value:.4f}",
                    "human_rating_count": len(values),
                    "deepseek_score": judge_values["deepseek"],
                    "llama_score": judge_values["llama"],
                    "prometheus_score": judge_values["prometheus"],
                    "generator_model": target["representative_model"],
                    "repair_strategy": target["representative_method"],
                }
            )

            if len(values) == 2:
                inter_rater_input.append(
                    {
                        "criterion": criterion,
                        "human1_score": str(values[0]),
                        "human2_score": str(values[1]),
                    }
                )
        wide_rows.append(wide)

    wide_fields = tuple(wide_rows[0].keys())
    write_csv(
        args.output_dir / "human_scores_final97_long.csv",
        LONG_FIELDS,
        final_long_rows,
    )
    write_csv(
        args.output_dir / "human_scores_final97_wide.csv",
        wide_fields,
        wide_rows,
    )
    write_csv(
        args.output_dir / "human_scores_final97_coverage.csv",
        COVERAGE_FIELDS,
        coverage_rows,
    )
    write_csv(
        args.output_dir / "human_llm_final97_analysis_input.csv",
        ANALYSIS_INPUT_FIELDS,
        analysis_input_rows,
    )

    inter_rater_rows: list[dict[str, str]] = []
    overall = metric_row(
        inter_rater_input,
        "human1_score",
        "human2_score",
    )
    inter_rater_rows.append(
        {"scope": "overall", "criterion": "all", **overall}
    )
    for criterion in CRITERIA:
        subset = [
            row
            for row in inter_rater_input
            if row["criterion"] == criterion
        ]
        inter_rater_rows.append(
            {
                "scope": "criterion",
                "criterion": criterion,
                **metric_row(
                    subset,
                    "human1_score",
                    "human2_score",
                ),
            }
        )
    write_csv(
        args.output_dir / "human_inter_rater_results.csv",
        INTER_RATER_FIELDS,
        inter_rater_rows,
    )

    expected_analysis_rows = len(final_diagrams) * len(CRITERIA)
    if len(analysis_input_rows) != expected_analysis_rows:
        raise AssertionError(
            f"Expected {expected_analysis_rows} analysis rows, "
            f"found {len(analysis_input_rows)}"
        )
    if len({row["judge_diagram_id"] for row in coverage_rows}) != 97:
        raise AssertionError("Final human coverage does not span 97 diagrams")

    judge_status = Counter(
        (
            JUDGE_ALIASES.get(row["judge_model"].strip(), row["judge_model"]),
            row["status"].strip().lower(),
        )
        for row in judge_rows
    )
    summary_lines = [
        "Final human + LLM judge comparison package",
        f"Final unique diagrams: {len(final_diagrams)}",
        f"Human rating rows: {len(final_long_rows)}",
        "Human coverage: 97/97 diagrams",
        f"Two-human diagrams: {sum(int(row['human_rating_count']) == 2 for row in coverage_rows)}",
        f"One-human diagrams: {sum(int(row['human_rating_count']) == 1 for row in coverage_rows)}",
        f"Coverage sources: {dict(sorted(source_counts.items()))}",
        f"Criterion-level comparison rows: {len(analysis_input_rows)}",
        f"Judge statuses: {dict(sorted(judge_status.items()))}",
        "Human consensus rule: arithmetic mean, rounded half-up to the nearest Likert category.",
        "Prometheus failed rows remain missing and are excluded pairwise with n_valid reported.",
    ]
    (args.output_dir / "summary.txt").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )
    print("\n".join(summary_lines))
    print(f"Output directory: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
