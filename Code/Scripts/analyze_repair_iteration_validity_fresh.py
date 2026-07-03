from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.parser import parse_and_validate_puml_text
from validate_run_folder_fresh import configure_plantuml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_ROOT = PROJECT_ROOT / "final_results" / "runs"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "final_results" / "paper_tables"

REPAIR_FOLDERS = {
    "baseline": {
        "Llama": (
            "open_source__llama31_8b_instruct__few_shot_"
            "validation_generator_critic_repair"
        ),
        "Mistral": "open_source__mistral__rag_validation_generator_critic_repair",
        "DeepSeek": (
            "open_source__deepseek_r1_14b__few_shot_"
            "validation_generator_critic_repair"
        ),
        "Qwen": (
            "open_source__qwen25_7b_instruct__rag_"
            "validation_generator_critic_repair"
        ),
    },
    "syntax_grounded": {
        "Llama": (
            "open_source__llama31_8b_instruct__few_shot_"
            "validation_generator_critic_repair__syntax_grounded"
        ),
        "Mistral": (
            "open_source__mistral__rag_validation_generator_critic_repair"
            "__syntax_grounded"
        ),
        "DeepSeek": (
            "open_source__deepseek_r1_14b__few_shot_"
            "validation_generator_critic_repair__syntax_grounded_no_rules"
        ),
        "Qwen": (
            "open_source__qwen25_7b_instruct__rag_"
            "validation_generator_critic_repair"
            "__syntax_grounded_no_rules_original_rag"
        ),
    },
}


def validate_path(path: Path) -> bool:
    _, validation = parse_and_validate_puml_text(
        path.read_text(encoding="utf-8")
    )
    return bool(is_strict_state_diagram_valid(validation))


def validate_paths(paths: list[Path], workers: int) -> dict[Path, bool]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        flags = list(executor.map(validate_path, paths))
    return dict(zip(paths, flags))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Freshly calculate newly strict-valid and remaining-invalid diagrams "
            "after every repair attempt."
        )
    )
    parser.add_argument(
        "--repair-method",
        choices=tuple(REPAIR_FOLDERS),
        default="syntax_grounded",
    )
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--plantuml-jar", type=Path)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    configure_plantuml(args.plantuml_jar)
    runs_root = args.runs_root.expanduser().resolve()
    rows: list[dict[str, object]] = []

    for model, folder_name in REPAIR_FOLDERS[args.repair_method].items():
        run_dir = runs_root / folder_name
        if not run_dir.is_dir():
            raise SystemExit(f"Repair folder not found: {run_dir}")

        case_dirs = sorted(
            path
            for path in run_dir.iterdir()
            if path.is_dir() and path.name.startswith("case_")
        )
        initial_paths = {
            case_dir.name: case_dir / "run_01.initial.puml"
            for case_dir in case_dirs
        }
        missing_initial = [
            str(path) for path in initial_paths.values() if not path.is_file()
        ]
        if missing_initial:
            raise SystemExit(
                "Missing initial diagrams:\n" + "\n".join(missing_initial)
            )

        initial_validity = validate_paths(
            list(initial_paths.values()),
            args.workers,
        )
        initially_valid = {
            case_id
            for case_id, path in initial_paths.items()
            if initial_validity[path]
        }
        active = {case_dir.name for case_dir in case_dirs} - initially_valid
        cumulative_valid = len(initially_valid)

        for attempt in range(1, args.attempts + 1):
            entering = len(active)
            attempt_paths = {
                case_id: run_dir / case_id / f"run_01.repair_{attempt:02}.puml"
                for case_id in active
            }
            existing_paths = [
                path for path in attempt_paths.values() if path.is_file()
            ]
            attempt_validity = validate_paths(existing_paths, args.workers)
            newly_valid = {
                case_id
                for case_id, path in attempt_paths.items()
                if path.is_file() and attempt_validity[path]
            }
            active -= newly_valid
            cumulative_valid += len(newly_valid)

            rows.append(
                {
                    "repair_method": args.repair_method,
                    "model": model,
                    "round": f"R{attempt}",
                    "initially_structurally_valid": len(initially_valid),
                    "entering_round": entering,
                    "newly_structurally_valid": len(newly_valid),
                    "remaining_structurally_invalid": len(active),
                    "cumulative_structurally_valid": cumulative_valid,
                    "total_cases": len(case_dirs),
                }
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        args.output_dir
        / f"{args.repair_method}_iteration_validity.csv"
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved: {output_path}")
    for row in rows:
        print(
            f"{row['model']} {row['round']}: "
            f"n={row['entering_round']}, "
            f"valid={row['newly_structurally_valid']}, "
            f"invalid={row['remaining_structurally_invalid']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
