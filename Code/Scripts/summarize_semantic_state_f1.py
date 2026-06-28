from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize semantic state precision, recall, and F1 by LLM and method."
    )
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()

    with args.input_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"No rows found in: {args.input_csv}")

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["llm_name"], row["method_name"])].append(row)

    summary: list[dict[str, object]] = []
    for (llm, method), group in sorted(grouped.items()):
        summary.append(
            {
                "llm_name": llm,
                "method_name": method,
                "cases": len(group),
                "mean_semantic_state_precision": round(
                    mean(
                        [
                            float(row["semantic_state_precision"])
                            for row in group
                        ]
                    ),
                    6,
                ),
                "mean_semantic_state_recall": round(
                    mean(
                        [
                            float(row["semantic_state_recall"])
                            for row in group
                        ]
                    ),
                    6,
                ),
                "mean_semantic_state_f1": round(
                    mean(
                        [float(row["semantic_state_f1"]) for row in group]
                    ),
                    6,
                ),
            }
        )

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    print("| LLM | Method | Cases | State precision | State recall | State F1 |")
    print("| --- | --- | ---: | ---: | ---: | ---: |")
    for row in summary:
        print(
            f"| {row['llm_name']} | {row['method_name']} | {row['cases']} | "
            f"{row['mean_semantic_state_precision']:.4f} | "
            f"{row['mean_semantic_state_recall']:.4f} | "
            f"{row['mean_semantic_state_f1']:.4f} |"
        )
    print(f"Summary CSV: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
