from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path


MODEL_MAP = {
    "Qwen 2.5 7B": "Qwen_2.5_7B",
    "Mistral": "Mistral",
    "DeepSeek R1 14B": "DeepSeek_R1_14B",
    "Llama 3.1 8B": "Llama_3.1_8B",
}


def case_num(case_id: str) -> str:
    match = re.search(r"case_(\d+)", case_id)
    return f"case_{int(match.group(1)):02d}" if match else case_id


def to_float(value: str) -> float | None:
    text = (value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    return float(text)


def pick_two(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def evaluator_sort_key(row: dict[str, str]):
        raw = (row.get("evaluator_id") or "").strip()
        try:
            return (0, float(raw))
        except ValueError:
            return (1, raw)

    return sorted(rows, key=evaluator_sort_key)[:2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build clean human-evaluation CSVs aligned to the 99 valid target diagrams."
    )
    parser.add_argument(
        "--valid-root",
        default="valid_diagrams_from_untitled_raw_deduped",
        help="Folder containing the 99 target diagrams.",
    )
    parser.add_argument(
        "--human-csv",
        default="results/plantuml_pipeline/llm_judge/human_scores_from_xlsx3/human_scores_clean.csv",
        help="Cleaned human ratings CSV extracted from the spreadsheet.",
    )
    parser.add_argument(
        "--output-dir",
        default="results/plantuml_pipeline/llm_judge/human_scores_valid99_clean",
        help="Output directory for compare-friendly CSV files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    valid_root = Path(args.valid_root)
    human_csv = Path(args.human_csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_rows: list[dict[str, str]] = []
    target_keys: set[tuple[str, str, str]] = set()

    for llm_dir in sorted(p for p in valid_root.iterdir() if p.is_dir()):
        for method_dir in sorted(p for p in llm_dir.iterdir() if p.is_dir()):
            for case_dir in sorted(p for p in method_dir.iterdir() if p.is_dir()):
                key = (case_num(case_dir.name), llm_dir.name, method_dir.name)
                target_keys.add(key)
                target_rows.append(
                    {
                        "case_num": key[0],
                        "case_id_full": case_dir.name,
                        "generation_model": llm_dir.name,
                        "generation_method": method_dir.name,
                    }
                )

    grouped_human: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    with human_csv.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            model = MODEL_MAP.get((row.get("generation_model") or "").strip())
            method = (row.get("generation_method") or "").strip()
            if not model:
                continue
            key = (case_num(row.get("case_id") or ""), model, method)
            if key in target_keys:
                grouped_human[key].append(row)

    wide_rows: list[dict[str, object]] = []
    long_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    for target in sorted(target_rows, key=lambda x: (x["generation_model"], x["generation_method"], x["case_num"])):
        key = (target["case_num"], target["generation_model"], target["generation_method"])
        all_ratings = grouped_human.get(key, [])
        selected = pick_two(all_ratings) if len(all_ratings) >= 2 else []

        if len(all_ratings) < 2:
            missing_rows.append(
                {
                    "case_num": target["case_num"],
                    "case_id_full": target["case_id_full"],
                    "generation_model": target["generation_model"],
                    "generation_method": target["generation_method"],
                    "available_human_evaluations": len(all_ratings),
                }
            )

        wide_row: dict[str, object] = {
            "case_num": target["case_num"],
            "case_id_full": target["case_id_full"],
            "generation_model": target["generation_model"],
            "generation_method": target["generation_method"],
            "available_human_evaluations": len(all_ratings),
            "selected_human_evaluations": len(selected),
            "selected_evaluator_ids": "|".join((r.get("evaluator_id") or "").strip() for r in selected),
        }

        metric_names = [
            ("completeness", "completeness_score", "completeness_justification"),
            ("correctness", "correctness_score", "correctness_justification"),
            ("understandability", "understandability_score", "understandability_justification"),
            ("terminology_alignment", "terminology_alignment_score", "terminology_alignment_justification"),
        ]

        for idx in range(2):
            prefix = f"human{idx + 1}"
            row = selected[idx] if idx < len(selected) else None
            wide_row[f"{prefix}_evaluator_id"] = (row.get("evaluator_id") or "").strip() if row else ""
            for metric_label, score_field, justification_field in metric_names:
                wide_row[f"{prefix}_{metric_label}_score"] = (row.get(score_field) or "").strip() if row else ""
                wide_row[f"{prefix}_{metric_label}_justification"] = (
                    (row.get(justification_field) or "").strip() if row else ""
                )

        for metric_label, score_field, _ in metric_names:
            values = [to_float(r.get(score_field, "")) for r in selected]
            numeric = [v for v in values if v is not None]
            wide_row[f"mean_{metric_label}_score"] = (
                round(sum(numeric) / len(numeric), 4) if numeric else ""
            )

        wide_rows.append(wide_row)

        for idx, row in enumerate(selected, start=1):
            long_rows.append(
                {
                    "case_num": target["case_num"],
                    "case_id_full": target["case_id_full"],
                    "generation_model": target["generation_model"],
                    "generation_method": target["generation_method"],
                    "selected_slot": idx,
                    "evaluator_id": (row.get("evaluator_id") or "").strip(),
                    "completeness_score": (row.get("completeness_score") or "").strip(),
                    "correctness_score": (row.get("correctness_score") or "").strip(),
                    "understandability_score": (row.get("understandability_score") or "").strip(),
                    "terminology_alignment_score": (row.get("terminology_alignment_score") or "").strip(),
                    "completeness_justification": (row.get("completeness_justification") or "").strip(),
                    "correctness_justification": (row.get("correctness_justification") or "").strip(),
                    "understandability_justification": (row.get("understandability_justification") or "").strip(),
                    "terminology_alignment_justification": (
                        (row.get("terminology_alignment_justification") or "").strip()
                    ),
                }
            )

    wide_path = output_dir / "human_scores_valid99_two_raters_wide.csv"
    with wide_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(wide_rows[0].keys()))
        writer.writeheader()
        writer.writerows(wide_rows)

    long_path = output_dir / "human_scores_valid99_two_raters_long.csv"
    with long_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(long_rows[0].keys()))
        writer.writeheader()
        writer.writerows(long_rows)

    missing_path = output_dir / "human_scores_valid99_missing.csv"
    with missing_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(missing_rows[0].keys()))
        writer.writeheader()
        writer.writerows(missing_rows)

    summary_path = output_dir / "summary.txt"
    summary_path.write_text(
        "\n".join(
            [
                f"Target diagrams: {len(target_rows)}",
                f"Diagrams with at least 2 human evaluations kept for comparison: {sum(1 for r in wide_rows if int(r['selected_human_evaluations']) == 2)}",
                f"Diagrams missing 2-human coverage: {len(missing_rows)}",
                "Selection rule for 3-human diagrams: keep the two lowest evaluator_id values (deterministic).",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote wide CSV: {wide_path}")
    print(f"Wrote long CSV: {long_path}")
    print(f"Wrote missing CSV: {missing_path}")
    print(f"Wrote summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
