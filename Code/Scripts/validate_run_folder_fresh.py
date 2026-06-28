from __future__ import annotations

import argparse
import csv
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.parser import parse_and_validate_puml_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freshly calculate official PlantUML syntax validity and strict "
            "structural validity for every case in one run folder."
        )
    )
    parser.add_argument(
        "run_folder",
        type=Path,
        help="Run folder containing case_*/run_01.puml files.",
    )
    parser.add_argument(
        "--plantuml-jar",
        type=Path,
        help="Optional path to plantuml.jar when the plantuml command is unavailable.",
    )
    parser.add_argument(
        "--csv-output",
        type=Path,
        help="Optional destination for per-case validation results.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of diagrams to validate concurrently (default: 4).",
    )
    return parser


def configure_plantuml(plantuml_jar: Path | None) -> None:
    if plantuml_jar is not None:
        jar_path = plantuml_jar.expanduser().resolve()
        if not jar_path.is_file():
            raise SystemExit(f"PlantUML JAR not found: {jar_path}")
        if shutil.which("java") is None:
            raise SystemExit("Java is required to run the supplied PlantUML JAR.")
        os.environ["PLANTUML_JAR"] = str(jar_path)
        return

    configured_jar = os.getenv("PLANTUML_JAR", "").strip()
    if configured_jar:
        if not Path(configured_jar).expanduser().is_file():
            raise SystemExit(f"PLANTUML_JAR does not exist: {configured_jar}")
        if shutil.which("java") is None:
            raise SystemExit("Java is required to run PLANTUML_JAR.")
        return

    if shutil.which("plantuml") is None:
        raise SystemExit(
            "Official PlantUML compiler not found. Install the plantuml command "
            "or pass --plantuml-jar path/to/plantuml.jar."
        )


def validate_case(item: tuple[str, Path]) -> dict[str, object]:
    case_id, puml_path = item
    _, validation = parse_and_validate_puml_text(
        puml_path.read_text(encoding="utf-8")
    )
    return {
        "case_id": case_id,
        "puml_path": str(puml_path),
        "syntax_valid": bool(validation.valid),
        "structural_valid": bool(is_strict_state_diagram_valid(validation)),
        "errors": " | ".join(validation.errors),
        "warnings": " | ".join(validation.warnings),
    }


def main() -> int:
    args = build_parser().parse_args()
    configure_plantuml(args.plantuml_jar)

    run_folder = args.run_folder.expanduser().resolve()
    if not run_folder.is_dir():
        raise SystemExit(f"Run folder not found: {run_folder}")

    case_dirs = sorted(
        path
        for path in run_folder.iterdir()
        if path.is_dir() and path.name.startswith("case_")
    )
    if not case_dirs:
        raise SystemExit(f"No case_* folders found under: {run_folder}")

    missing = [
        case_dir.name
        for case_dir in case_dirs
        if not (case_dir / "run_01.puml").is_file()
    ]
    if missing:
        raise SystemExit(
            "Missing run_01.puml in: " + ", ".join(missing)
        )

    inputs = [
        (case_dir.name, case_dir / "run_01.puml")
        for case_dir in case_dirs
    ]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        rows = list(executor.map(validate_case, inputs))

    print("| Case | Syntax valid | Strict structural valid |")
    print("| --- | ---: | ---: |")
    for row in rows:
        print(
            f"| {row['case_id']} | "
            f"{'Yes' if row['syntax_valid'] else 'No'} | "
            f"{'Yes' if row['structural_valid'] else 'No'} |"
        )

    total = len(rows)
    syntax_count = sum(bool(row["syntax_valid"]) for row in rows)
    structural_count = sum(bool(row["structural_valid"]) for row in rows)

    print("\nSummary")
    print(f"Cases: {total}")
    print(
        f"Syntax validity: {syntax_count}/{total} "
        f"({100.0 * syntax_count / total:.2f}%)"
    )
    print(
        f"Strict structural validity: {structural_count}/{total} "
        f"({100.0 * structural_count / total:.2f}%)"
    )

    if args.csv_output is not None:
        csv_output = args.csv_output.expanduser().resolve()
        csv_output.parent.mkdir(parents=True, exist_ok=True)
        with csv_output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Per-case CSV: {csv_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
