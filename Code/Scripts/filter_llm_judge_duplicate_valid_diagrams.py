#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


REPAIR_METHODS = {"baseline_repair", "syntax_grounded_repair"}
RAW_METHODS = {"rag", "few_shot", "zero_shot", "one_shot", "cot", "chain_of_thought"}
SELECTED_RAW_METHOD = {
    "Qwen_2.5_7B": "rag",
    "Mistral": "rag",
    "DeepSeek_R1_14B": "few_shot",
    "Llama_3.1_8B": "few_shot",
}


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def diagram_key(row: dict) -> tuple[str, str, str]:
    return row["generation_model"], row["case_id"], row["diagram_id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove repair diagrams that duplicate already-judged raw diagrams for the same model+case.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--mode",
        choices=("any_raw", "selected_best_raw"),
        default="selected_best_raw",
        help="Duplicate rule: any_raw removes repair if any raw method exists for same model+case; selected_best_raw removes only if that model's selected raw method exists.",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = input_dir / "judge_scores_long.csv"
    jsonl_path = input_dir / "combined_judgements.jsonl"
    manifest_path = input_dir / "experiment_manifest.json"

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
        fieldnames = list(csv_rows[0].keys()) if csv_rows else []

    jsonl_rows = list(read_jsonl(jsonl_path))

    raw_by_model_case: dict[tuple[str, str], list[dict]] = defaultdict(list)
    repair_rows: list[dict] = []
    all_diagram_info: dict[tuple[str, str, str], dict] = {}

    for row in csv_rows:
        key = (row["generation_model"], row["case_id"])
        all_diagram_info[diagram_key(row)] = row
        method = row["generation_method"]
        if method in RAW_METHODS:
            raw_by_model_case[key].append(row)
        elif method in REPAIR_METHODS:
            repair_rows.append(row)

    diagrams_to_remove: set[tuple[str, str, str]] = set()
    removal_report: list[dict] = []

    # Remove repair diagrams only when the same model+case already has a raw judged diagram.
    for row in repair_rows:
        model_case = (row["generation_model"], row["case_id"])
        raw_rows = raw_by_model_case.get(model_case, [])
        if args.mode == "any_raw":
            qualifying_raw_rows = raw_rows
        else:
            selected_raw_method = SELECTED_RAW_METHOD.get(row["generation_model"])
            qualifying_raw_rows = [r for r in raw_rows if r["generation_method"] == selected_raw_method]

        if qualifying_raw_rows:
            dkey = diagram_key(row)
            if dkey not in diagrams_to_remove:
                raw_methods = sorted({r["generation_method"] for r in qualifying_raw_rows})
                diagrams_to_remove.add(dkey)
                removal_report.append(
                    {
                        "diagram_id": row["diagram_id"],
                        "case_id": row["case_id"],
                        "generation_model": row["generation_model"],
                        "generation_method": row["generation_method"],
                        "source_run_id": row["source_run_id"],
                        "removed_because": f"{args.mode}_duplicate_of_existing_raw_diagram",
                        "raw_methods_present": "|".join(raw_methods),
                    }
                )

    filtered_csv_rows = [row for row in csv_rows if diagram_key(row) not in diagrams_to_remove]
    filtered_jsonl_rows = [row for row in jsonl_rows if diagram_key(row) not in diagrams_to_remove]

    with (output_dir / "judge_scores_long.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered_csv_rows)

    write_jsonl(output_dir / "combined_judgements.jsonl", filtered_jsonl_rows)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    removed_count = len(removal_report)
    kept_diagram_count = len({diagram_key(row) for row in filtered_csv_rows})
    original_diagram_count = len({diagram_key(row) for row in csv_rows})
    manifest["diagram_count_original"] = original_diagram_count
    manifest["diagram_count_filtered"] = kept_diagram_count
    manifest["removed_duplicate_valid_diagrams"] = removed_count
    if args.mode == "any_raw":
        manifest["filter_rule"] = "Remove baseline_repair and syntax_grounded_repair diagrams when the same generation_model and case_id already have any raw judged diagram."
    else:
        manifest["filter_rule"] = "Remove baseline_repair and syntax_grounded_repair diagrams when the same generation_model and case_id already have that model's selected best raw judged diagram."
        manifest["selected_raw_method_by_model"] = SELECTED_RAW_METHOD
    (output_dir / "experiment_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with (output_dir / "removed_duplicates.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "diagram_id",
            "case_id",
            "generation_model",
            "generation_method",
            "source_run_id",
            "removed_because",
            "raw_methods_present",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(removal_report)

    by_method = Counter(row["generation_method"] for row in removal_report)
    by_model = Counter(row["generation_model"] for row in removal_report)
    summary_lines = [
        f"Original unique diagrams: {original_diagram_count}",
        f"Removed duplicate-valid diagrams: {removed_count}",
        f"Remaining unique diagrams: {kept_diagram_count}",
        "",
        "Removed by method:",
    ]
    summary_lines.extend(f"- {name}: {count}" for name, count in sorted(by_method.items()))
    summary_lines.append("")
    summary_lines.append("Removed by model:")
    summary_lines.extend(f"- {name}: {count}" for name, count in sorted(by_model.items()))
    (output_dir / "filter_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print("\n".join(summary_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
