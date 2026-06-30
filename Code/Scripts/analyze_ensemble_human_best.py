#!/usr/bin/env python3
"""Compare ensemble selections with human-best candidates per case."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


CRITERION_MEAN_COLUMNS = (
    "mean_completeness_score",
    "mean_correctness_score",
    "mean_understandability_score",
    "mean_terminological_alignment_score",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def render_png(puml_path: Path, plantuml_command: str) -> None:
    subprocess.run(
        [plantuml_command, "-tpng", str(puml_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    png_path = puml_path.with_suffix(".png")
    if not png_path.exists():
        raise RuntimeError(f"PlantUML did not create expected PNG: {png_path}")


def candidate_path(valid_root: Path, candidate: dict[str, str]) -> Path:
    return (
        valid_root
        / candidate["model"]
        / candidate["method"]
        / candidate["case_id"]
        / "diagram.puml"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rank each case's candidates by mean human Likert score, export the "
            "human-best diagrams, and compare them with the ensemble selection."
        )
    )
    parser.add_argument(
        "--human-scores-csv",
        type=Path,
        default=Path(
            "final_results/llm_judge/final_human_comparison/"
            "human_scores_final97_wide.csv"
        ),
    )
    parser.add_argument(
        "--ensemble-results-csv",
        type=Path,
        default=Path("final_results/meta_ensemble/ensemble_results.csv"),
    )
    parser.add_argument(
        "--candidate-validation-csv",
        type=Path,
        default=Path("final_results/meta_ensemble/candidate_validation.csv"),
    )
    parser.add_argument(
        "--valid-diagrams-root",
        type=Path,
        default=Path("final_results/valid_diagrams"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("final_results/meta_ensemble/human_best_analysis"),
    )
    parser.add_argument("--plantuml-command", default="plantuml")
    parser.add_argument(
        "--tie-tolerance",
        type=float,
        default=1e-9,
        help="Maximum score difference treated as a human-best tie.",
    )
    args = parser.parse_args()

    human_rows = read_csv(args.human_scores_csv)
    ensemble_rows = read_csv(args.ensemble_results_csv)
    candidate_rows = read_csv(args.candidate_validation_csv)

    if len(human_rows) != 97 or len(candidate_rows) != 97:
        raise ValueError(
            "Expected 97 human-scored candidates and 97 validated candidates; "
            f"found {len(human_rows)} and {len(candidate_rows)}."
        )
    if len(ensemble_rows) != 27:
        raise ValueError(f"Expected 27 ensemble cases; found {len(ensemble_rows)}.")

    human_by_id = {row["package_diagram_id"]: row for row in human_rows}
    candidate_by_id = {row["candidate_id"]: row for row in candidate_rows}
    if set(human_by_id) != set(candidate_by_id):
        missing_human = sorted(set(candidate_by_id) - set(human_by_id))
        missing_candidate = sorted(set(human_by_id) - set(candidate_by_id))
        raise ValueError(
            "Human and candidate IDs do not align. "
            f"Missing human={missing_human}; missing candidate={missing_candidate}"
        )

    candidates_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for candidate in candidate_rows:
        if not parse_bool(candidate["syntax_valid"]) or not parse_bool(
            candidate["structural_valid"]
        ):
            raise ValueError(
                f"Candidate {candidate['candidate_id']} is not strictly valid."
            )
        path = candidate_path(args.valid_diagrams_root, candidate)
        if not path.exists():
            raise FileNotFoundError(f"Candidate diagram not found: {path}")
        actual_hash = sha256(path)
        if candidate["content_sha256"] and actual_hash != candidate["content_sha256"]:
            raise ValueError(
                f"Content hash mismatch for {candidate['candidate_id']}: {path}"
            )
        candidate["_local_path"] = str(path)
        candidate["_content_sha256"] = actual_hash
        human = human_by_id[candidate["candidate_id"]]
        criterion_means = [float(human[column]) for column in CRITERION_MEAN_COLUMNS]
        candidate["_human_score"] = f"{mean(criterion_means):.6f}"
        candidates_by_case[candidate["case_id"]].append(candidate)

    ensemble_by_case = {row["case_id"]: row for row in ensemble_rows}
    if set(candidates_by_case) != set(ensemble_by_case):
        raise ValueError("Candidate and ensemble case sets do not match.")

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    diagrams_root = args.output_dir / "human_best_diagrams"
    diagrams_root.mkdir(parents=True, exist_ok=True)

    agreement_rows: list[dict[str, object]] = []
    human_best_rows: list[dict[str, object]] = []

    for case_id in sorted(candidates_by_case):
        candidates = sorted(
            candidates_by_case[case_id], key=lambda row: row["candidate_id"]
        )
        best_score = max(float(row["_human_score"]) for row in candidates)
        human_best = [
            row
            for row in candidates
            if abs(float(row["_human_score"]) - best_score) <= args.tie_tolerance
        ]
        ensemble = ensemble_by_case[case_id]
        selected_id = ensemble["selected_candidate_id"]
        selected = candidate_by_id[selected_id]
        selected_human_score = float(candidate_by_id[selected_id]["_human_score"])

        best_ids = [row["candidate_id"] for row in human_best]
        best_hashes = {row["_content_sha256"] for row in human_best}
        id_match = selected_id in best_ids
        content_match = selected["_content_sha256"] in best_hashes

        case_dir = diagrams_root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        for index, best in enumerate(human_best, start=1):
            filename = "human_best.puml" if index == 1 else f"human_best_tie_{index:02d}.puml"
            destination = case_dir / filename
            shutil.copy2(Path(best["_local_path"]), destination)
            render_png(destination, args.plantuml_command)

            human_best_rows.append(
                {
                    "case_id": case_id,
                    "human_best_rank": index,
                    "human_best_tie_count": len(human_best),
                    "candidate_id": best["candidate_id"],
                    "model": best["model"],
                    "method": best["method"],
                    "human_mean_score": f"{best_score:.6f}",
                    "human_rating_count": human_by_id[best["candidate_id"]][
                        "human_rating_count"
                    ],
                    "puml_path": str(destination),
                    "png_path": str(destination.with_suffix(".png")),
                }
            )

        metadata = {
            "case_id": case_id,
            "human_score_definition": (
                "Mean of the four criterion-level human mean scores."
            ),
            "human_best_score": best_score,
            "human_best_candidate_ids": best_ids,
            "human_best_tie_count": len(human_best),
            "representative_human_best_candidate_id": human_best[0]["candidate_id"],
            "ensemble_selected_candidate_id": selected_id,
            "ensemble_selected_model": selected["model"],
            "ensemble_selected_method": selected["method"],
            "ensemble_matches_human_best_id": id_match,
            "ensemble_matches_human_best_content": content_match,
        }
        (case_dir / "selection_metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

        agreement_rows.append(
            {
                "case_id": case_id,
                "candidate_count": len(candidates),
                "human_best_candidate_ids": json.dumps(
                    best_ids, separators=(",", ":")
                ),
                "human_best_models": json.dumps(
                    [row["model"] for row in human_best], separators=(",", ":")
                ),
                "human_best_methods": json.dumps(
                    [row["method"] for row in human_best], separators=(",", ":")
                ),
                "human_best_score": f"{best_score:.6f}",
                "human_best_tie_count": len(human_best),
                "ensemble_selected_candidate_id": selected_id,
                "ensemble_selected_model": selected["model"],
                "ensemble_selected_method": selected["method"],
                "ensemble_selected_human_score": f"{selected_human_score:.6f}",
                "human_score_gap_from_best": f"{best_score - selected_human_score:.6f}",
                "ensemble_matches_human_best_id": str(id_match).lower(),
                "ensemble_matches_human_best_content": str(content_match).lower(),
                "selection_method": ensemble["selection_method"],
                "fallback_used": ensemble["fallback_used"],
                "selected_state_f1": ensemble["selected_state_f1"],
            }
        )

    write_csv(
        args.output_dir / "human_best_candidates.csv",
        human_best_rows,
        [
            "case_id",
            "human_best_rank",
            "human_best_tie_count",
            "candidate_id",
            "model",
            "method",
            "human_mean_score",
            "human_rating_count",
            "puml_path",
            "png_path",
        ],
    )
    write_csv(
        args.output_dir / "human_ensemble_agreement.csv",
        agreement_rows,
        [
            "case_id",
            "candidate_count",
            "human_best_candidate_ids",
            "human_best_models",
            "human_best_methods",
            "human_best_score",
            "human_best_tie_count",
            "ensemble_selected_candidate_id",
            "ensemble_selected_model",
            "ensemble_selected_method",
            "ensemble_selected_human_score",
            "human_score_gap_from_best",
            "ensemble_matches_human_best_id",
            "ensemble_matches_human_best_content",
            "selection_method",
            "fallback_used",
            "selected_state_f1",
        ],
    )

    case_count = len(agreement_rows)
    id_matches = sum(
        row["ensemble_matches_human_best_id"] == "true" for row in agreement_rows
    )
    content_matches = sum(
        row["ensemble_matches_human_best_content"] == "true"
        for row in agreement_rows
    )
    tied_cases = sum(int(row["human_best_tie_count"]) > 1 for row in agreement_rows)
    unique_best_rows = [
        row for row in agreement_rows if int(row["human_best_tie_count"]) == 1
    ]
    unique_best_matches = sum(
        row["ensemble_matches_human_best_content"] == "true"
        for row in unique_best_rows
    )
    score_gaps = [float(row["human_score_gap_from_best"]) for row in agreement_rows]
    exact_score_matches = sum(abs(value) <= args.tie_tolerance for value in score_gaps)

    summary_rows = [
        {"metric": "case_count", "value": case_count},
        {"metric": "human_best_tied_cases", "value": tied_cases},
        {"metric": "human_best_unique_cases", "value": len(unique_best_rows)},
        {"metric": "ensemble_human_best_id_matches", "value": id_matches},
        {
            "metric": "ensemble_human_best_id_agreement_percent",
            "value": f"{100 * id_matches / case_count:.6f}",
        },
        {"metric": "ensemble_human_best_content_matches", "value": content_matches},
        {
            "metric": "ensemble_human_best_content_agreement_percent",
            "value": f"{100 * content_matches / case_count:.6f}",
        },
        {
            "metric": "unique_human_best_content_matches",
            "value": unique_best_matches,
        },
        {
            "metric": "unique_human_best_content_agreement_percent",
            "value": (
                f"{100 * unique_best_matches / len(unique_best_rows):.6f}"
                if unique_best_rows
                else ""
            ),
        },
        {"metric": "ensemble_equal_human_score_cases", "value": exact_score_matches},
        {
            "metric": "mean_human_score_gap_from_best",
            "value": f"{mean(score_gaps):.6f}",
        },
        {
            "metric": "max_human_score_gap_from_best",
            "value": f"{max(score_gaps):.6f}",
        },
    ]
    write_csv(
        args.output_dir / "human_ensemble_agreement_summary.csv",
        summary_rows,
        ["metric", "value"],
    )

    selected_models = Counter(
        row["ensemble_selected_model"]
        for row in agreement_rows
        if row["ensemble_matches_human_best_content"] == "true"
    )
    selected_methods = Counter(
        row["ensemble_selected_method"]
        for row in agreement_rows
        if row["ensemble_matches_human_best_content"] == "true"
    )
    summary_text = "\n".join(
        [
            "Human-best versus ensemble selection",
            f"Cases: {case_count}",
            f"Human-best tied cases: {tied_cases}",
            (
                "Tie-aware candidate agreement: "
                f"{content_matches}/{case_count} "
                f"({100 * content_matches / case_count:.2f}%)"
            ),
            (
                "Unique-human-best agreement: "
                f"{unique_best_matches}/{len(unique_best_rows)} "
                f"({100 * unique_best_matches / len(unique_best_rows):.2f}%)"
                if unique_best_rows
                else "Unique-human-best agreement: not applicable"
            ),
            f"Mean human-score gap from best: {mean(score_gaps):.4f}",
            f"Maximum human-score gap from best: {max(score_gaps):.4f}",
            f"Matching selected models: {dict(selected_models)}",
            f"Matching selected methods: {dict(selected_methods)}",
            (
                "Human score: arithmetic mean of completeness, correctness, "
                "understandability, and terminological-alignment human means."
            ),
            (
                "A tie-aware match is counted when the ensemble candidate is any "
                "candidate sharing the maximum human score for that case."
            ),
        ]
    )
    (args.output_dir / "summary.txt").write_text(
        summary_text + "\n", encoding="utf-8"
    )
    print(summary_text)
    print(f"Output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
