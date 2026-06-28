from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from plantuml_pipeline.generation import is_strict_state_diagram_valid
from plantuml_pipeline.parser import parse_and_validate_puml_text
from validate_run_folder_fresh import configure_plantuml


RUN_SPECS = [
    (
        "Qwen_2.5_7B",
        "rag",
        "open_source__qwen25_7b_instruct__rag",
    ),
    (
        "Qwen_2.5_7B",
        "baseline_repair",
        "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
    ),
    (
        "Qwen_2.5_7B",
        "syntax_grounded_repair",
        "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair"
        "__syntax_grounded_no_rules_original_rag",
    ),
    (
        "Mistral",
        "rag",
        "open_source__mistral__rag",
    ),
    (
        "Mistral",
        "baseline_repair",
        "open_source__mistral__rag_validation_generator_critic_repair",
    ),
    (
        "Mistral",
        "syntax_grounded_repair",
        "open_source__mistral__rag_validation_generator_critic_repair"
        "__syntax_grounded",
    ),
    (
        "DeepSeek_R1_14B",
        "few_shot",
        "open_source__deepseek_r1_14b__few_shot",
    ),
    (
        "DeepSeek_R1_14B",
        "baseline_repair",
        "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
    ),
    (
        "DeepSeek_R1_14B",
        "syntax_grounded_repair",
        "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair"
        "__syntax_grounded_no_rules",
    ),
    (
        "Llama_3.1_8B",
        "few_shot",
        "open_source__llama31_8b_instruct__few_shot",
    ),
    (
        "Llama_3.1_8B",
        "baseline_repair",
        "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",
    ),
    (
        "Llama_3.1_8B",
        "syntax_grounded_repair",
        "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair"
        "__syntax_grounded",
    ),
]

MODEL_ORDER = {
    "Qwen_2.5_7B": 0,
    "Mistral": 1,
    "DeepSeek_R1_14B": 2,
    "Llama_3.1_8B": 3,
}
METHOD_ORDER = {
    "rag": 0,
    "few_shot": 0,
    "baseline_repair": 1,
    "syntax_grounded_repair": 2,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freshly validate final experiment diagrams, build a unique valid "
            "diagram package, and build the subset still needing human ratings."
        )
    )
    parser.add_argument("--runs-root", type=Path, default=Path("final_results/runs"))
    parser.add_argument("--dataset-root", type=Path, default=Path("dataset"))
    parser.add_argument(
        "--valid-output",
        type=Path,
        default=Path("final_results/valid_diagrams"),
    )
    parser.add_argument(
        "--human-output",
        type=Path,
        default=Path("final_results/need_to_validate_by_human"),
    )
    parser.add_argument(
        "--existing-evaluated-root",
        type=Path,
        default=Path("valid_diagrams_from_untitled_raw_deduped"),
        help="Previous package whose raw/baseline diagrams have human ratings.",
    )
    parser.add_argument(
        "--human-scores-csv",
        type=Path,
        default=Path(
            "results/plantuml_pipeline/llm_judge/human_scores_valid99_clean"
            "/human_scores_valid99_two_raters_wide.csv"
        ),
    )
    parser.add_argument("--plantuml-jar", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing output package folders.",
    )
    return parser


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rendered_image_hash(path: Path) -> str:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        payload = (
            rgba.width.to_bytes(4, "big")
            + rgba.height.to_bytes(4, "big")
            + rgba.tobytes()
        )
    return hashlib.sha256(payload).hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    seen_fields: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen_fields:
                seen_fields.add(field)
                fieldnames.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validation_task(item: dict[str, object]) -> dict[str, object]:
    puml_path = Path(str(item["source_path"]))
    _, validation = parse_and_validate_puml_text(
        puml_path.read_text(encoding="utf-8")
    )
    return {
        **item,
        "syntax_valid": bool(validation.valid),
        "structural_valid": bool(is_strict_state_diagram_valid(validation)),
        "errors": " | ".join(validation.errors),
        "warnings": " | ".join(validation.warnings),
    }


def plantuml_command() -> list[str]:
    jar = os.getenv("PLANTUML_JAR", "").strip()
    if jar:
        java = shutil.which("java")
        if not java:
            raise SystemExit("Java is required to render with PLANTUML_JAR.")
        return [java, "-jar", jar]
    plantuml = shutil.which("plantuml")
    if not plantuml:
        raise SystemExit("PlantUML command is unavailable.")
    return [plantuml]


def render_png(item: tuple[Path, list[str]]) -> Path:
    puml_path, command = item
    result = subprocess.run(
        [*command, "-tpng", "-charset", "UTF-8", str(puml_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    png_path = puml_path.with_suffix(".png")
    if result.returncode != 0 or not png_path.is_file():
        diagnostic = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part.strip()
        )
        raise RuntimeError(f"PNG rendering failed for {puml_path}: {diagnostic}")
    if png_path.stat().st_size < 8 or png_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"Invalid PNG generated for {puml_path}")
    return png_path


def prepare_output(path: Path, overwrite: bool) -> None:
    if path.exists():
        if not overwrite:
            raise SystemExit(
                f"Output already exists: {path}. Re-run with --overwrite to replace it."
            )
        shutil.rmtree(path)
    path.mkdir(parents=True)


def covered_human_hashes(
    evaluated_root: Path,
    scores_csv: Path,
) -> set[tuple[str, str, str]]:
    if not evaluated_root.is_dir() or not scores_csv.is_file():
        return set()

    covered: set[tuple[str, str, str]] = set()
    with scores_csv.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            try:
                selected = int(row.get("selected_human_evaluations") or 0)
            except ValueError:
                selected = 0
            if selected < 2:
                continue

            model = (row.get("generation_model") or "").strip()
            method = (row.get("generation_method") or "").strip()
            case_id = (row.get("case_id_full") or "").strip()
            png_path = evaluated_root / model / method / case_id / "diagram.png"
            if not png_path.is_file():
                continue
            covered.add((model, case_id, rendered_image_hash(png_path)))
    return covered


def main() -> int:
    args = build_parser().parse_args()
    configure_plantuml(args.plantuml_jar)

    runs_root = args.runs_root.expanduser().resolve()
    dataset_root = args.dataset_root.expanduser().resolve()
    valid_output = args.valid_output.expanduser().resolve()
    human_output = args.human_output.expanduser().resolve()
    evaluated_root = args.existing_evaluated_root.expanduser().resolve()
    scores_csv = args.human_scores_csv.expanduser().resolve()

    if not runs_root.is_dir():
        raise SystemExit(f"Runs root not found: {runs_root}")
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset root not found: {dataset_root}")

    prepare_output(valid_output, args.overwrite)
    prepare_output(human_output, args.overwrite)

    validation_inputs: list[dict[str, object]] = []
    for model, method, run_folder in RUN_SPECS:
        run_dir = runs_root / run_folder
        if not run_dir.is_dir():
            raise SystemExit(f"Required run folder not found: {run_dir}")
        case_dirs = sorted(
            path
            for path in run_dir.iterdir()
            if path.is_dir() and path.name.startswith("case_")
        )
        for case_dir in case_dirs:
            puml_path = case_dir / "run_01.puml"
            if not puml_path.is_file():
                raise SystemExit(f"Missing final diagram: {puml_path}")
            validation_inputs.append(
                {
                    "model": model,
                    "method": method,
                    "run_folder": run_folder,
                    "case_id": case_dir.name,
                    "source_path": str(puml_path),
                }
            )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        validation_rows = list(executor.map(validation_task, validation_inputs))

    strict_rows = [
        row
        for row in validation_rows
        if bool(row["syntax_valid"]) and bool(row["structural_valid"])
    ]
    for row in strict_rows:
        source_path = Path(str(row["source_path"]))
        row["content_sha256"] = content_hash(normalized_text(source_path))

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in strict_rows:
        grouped[
            (
                str(row["model"]),
                str(row["case_id"]),
                str(row["content_sha256"]),
            )
        ].append(row)

    unique_rows: list[dict[str, object]] = []
    all_source_rows: list[dict[str, object]] = []
    render_paths: list[Path] = []

    sorted_groups = sorted(
        grouped.items(),
        key=lambda item: (
            item[0][1],
            MODEL_ORDER.get(item[0][0], 99),
            min(
                METHOD_ORDER.get(str(row["method"]), 99)
                for row in item[1]
            ),
            item[0][2],
        ),
    )

    for index, ((_group_model, case_id, digest), sources) in enumerate(
        sorted_groups, start=1
    ):
        sources = sorted(
            sources,
            key=lambda row: (
                METHOD_ORDER.get(str(row["method"]), 99),
                MODEL_ORDER.get(str(row["model"]), 99),
            ),
        )
        representative = sources[0]
        diagram_id = f"valid_{index:03d}"
        model = str(representative["model"])
        method = str(representative["method"])
        target_dir = valid_output / model / method / case_id
        target_dir.mkdir(parents=True, exist_ok=True)

        source_path = Path(str(representative["source_path"]))
        diagram_path = target_dir / "diagram.puml"
        shutil.copy2(source_path, diagram_path)
        structured_requirement = dataset_root / case_id / "structured_requirement.txt"
        if not structured_requirement.is_file():
            raise SystemExit(
                f"Structured requirement not found: {structured_requirement}"
            )
        shutil.copy2(structured_requirement, target_dir / "requirement.txt")
        shutil.copy2(
            structured_requirement,
            target_dir / "structured_requirement.txt",
        )
        (target_dir / "diagram_id.txt").write_text(
            diagram_id + "\n", encoding="utf-8"
        )
        (target_dir / "source_run_id.txt").write_text(
            str(representative["run_folder"]) + "\n",
            encoding="utf-8",
        )
        equivalent_sources = [
            f"{row['model']} | {row['method']} | {row['run_folder']} | {row['source_path']}"
            for row in sources
        ]
        (target_dir / "equivalent_sources.txt").write_text(
            "\n".join(equivalent_sources) + "\n",
            encoding="utf-8",
        )
        render_paths.append(diagram_path)

        unique_row = {
            "diagram_id": diagram_id,
            "case_id": case_id,
            "representative_model": model,
            "representative_method": method,
            "content_sha256": digest,
            "equivalent_source_count": len(sources),
            "diagram_path": str(diagram_path),
            "png_path": str(diagram_path.with_suffix(".png")),
            "requirement_path": str(target_dir / "requirement.txt"),
        }
        unique_rows.append(unique_row)

        for row in sources:
            all_source_rows.append(
                {
                    "diagram_id": diagram_id,
                    "case_id": case_id,
                    "model": row["model"],
                    "method": row["method"],
                    "run_folder": row["run_folder"],
                    "source_path": row["source_path"],
                    "content_sha256": digest,
                    "is_representative": (
                        row["model"] == representative["model"]
                        and row["method"] == representative["method"]
                    ),
                }
            )

    command = plantuml_command()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        list(executor.map(render_png, [(path, command) for path in render_paths]))

    covered = covered_human_hashes(evaluated_root, scores_csv)
    needs_human = [
        row
        for row in unique_rows
        if (
            str(row["representative_model"]),
            str(row["case_id"]),
            rendered_image_hash(Path(str(row["png_path"]))),
        )
        not in covered
    ]

    human_mapping_rows: list[dict[str, object]] = []
    by_case_counter: Counter[str] = Counter()
    unique_by_id = {str(row["diagram_id"]): row for row in unique_rows}
    sources_by_id: dict[str, list[dict[str, object]]] = defaultdict(list)
    for source in all_source_rows:
        sources_by_id[str(source["diagram_id"])].append(source)

    for index, row in enumerate(needs_human, start=1):
        evaluation_id = f"diagram_{index:03d}"
        case_id = str(row["case_id"])
        by_case_counter[case_id] += 1
        case_dir = human_output / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        valid_diagram_path = Path(str(row["diagram_path"]))
        valid_png_path = valid_diagram_path.with_suffix(".png")
        shutil.copy2(
            dataset_root / case_id / "structured_requirement.txt",
            case_dir / "requirement.txt",
        )
        shutil.copy2(valid_diagram_path, case_dir / f"{evaluation_id}.puml")
        shutil.copy2(valid_png_path, case_dir / f"{evaluation_id}.png")

        source_descriptions = sources_by_id[str(row["diagram_id"])]
        human_mapping_rows.append(
            {
                "evaluation_id": evaluation_id,
                "case_id": case_id,
                "model": "|".join(
                    sorted({str(source["model"]) for source in source_descriptions})
                ),
                "method": "|".join(
                    sorted({str(source["method"]) for source in source_descriptions})
                ),
                "source_run_id": "|".join(
                    sorted(
                        {
                            str(source["run_folder"])
                            for source in source_descriptions
                        }
                    )
                ),
                "content_sha256": row["content_sha256"],
                "puml_path": str(case_dir / f"{evaluation_id}.puml"),
                "png_path": str(case_dir / f"{evaluation_id}.png"),
                "requirement_path": str(case_dir / "requirement.txt"),
            }
        )

    summary_counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in validation_rows:
        key = (str(row["model"]), str(row["method"]))
        summary_counts[key]["total"] += 1
        summary_counts[key]["syntax_valid"] += int(bool(row["syntax_valid"]))
        summary_counts[key]["structural_valid"] += int(
            bool(row["structural_valid"])
        )

    summary_rows: list[dict[str, object]] = []
    for model, method, run_folder in RUN_SPECS:
        counts = summary_counts[(model, method)]
        total = counts["total"]
        summary_rows.append(
            {
                "model": model,
                "method": method,
                "run_folder": run_folder,
                "cases": total,
                "syntax_valid": counts["syntax_valid"],
                "syntax_valid_percent": round(
                    100.0 * counts["syntax_valid"] / total, 2
                ),
                "strict_valid": counts["structural_valid"],
                "strict_valid_percent": round(
                    100.0 * counts["structural_valid"] / total, 2
                ),
            }
        )

    write_csv(valid_output / "validity_summary.csv", summary_rows)
    write_csv(valid_output / "validation_per_case.csv", validation_rows)
    write_csv(valid_output / "unique_valid_diagrams.csv", unique_rows)
    write_csv(valid_output / "all_valid_sources.csv", all_source_rows)
    write_csv(human_output / "PRIVATE_mapping.csv", human_mapping_rows)

    template_rows = [
        {
            "evaluation_id": row["evaluation_id"],
            "case_id": row["case_id"],
            "evaluator_id": "",
            "completeness_score": "",
            "completeness_justification": "",
            "correctness_score": "",
            "correctness_justification": "",
            "understandability_score": "",
            "understandability_justification": "",
            "terminology_alignment_score": "",
            "terminology_alignment_justification": "",
        }
        for row in human_mapping_rows
    ]
    write_csv(human_output / "human_evaluation_template.csv", template_rows)

    valid_readme = [
        "Final strict-valid evaluation package",
        "",
        f"Strict-valid source outputs: {len(strict_rows)}",
        f"Unique diagrams after content deduplication within each model-case: {len(unique_rows)}",
        "",
        "Each diagram folder contains:",
        "- diagram.puml",
        "- diagram.png",
        "- requirement.txt (structured requirement)",
        "- structured_requirement.txt",
        "- diagram_id.txt",
        "- source_run_id.txt",
        "- equivalent_sources.txt",
        "",
        "Use this unique package for the three LLM judges.",
        "all_valid_sources.csv maps every valid model/method output to its unique diagram.",
    ]
    (valid_output / "README.txt").write_text(
        "\n".join(valid_readme) + "\n", encoding="utf-8"
    )

    human_readme = [
        "Diagrams still needing human validation",
        "",
        f"Unique diagrams needing human ratings: {len(needs_human)}",
        f"Cases represented: {len(by_case_counter)}",
        "",
        "Each case folder contains the structured requirement and anonymous diagram IDs.",
        "Give requirement.txt, diagram_###.puml, and diagram_###.png to evaluators.",
        "Do not give PRIVATE_mapping.csv to evaluators because it reveals model provenance.",
    ]
    (human_output / "README.txt").write_text(
        "\n".join(human_readme) + "\n", encoding="utf-8"
    )

    print(f"Strict-valid source outputs: {len(strict_rows)}")
    print(f"Unique valid diagrams: {len(unique_rows)}")
    print(f"Already covered by two human ratings: {len(unique_rows) - len(needs_human)}")
    print(f"Need human validation: {len(needs_human)}")
    print(f"Valid package: {valid_output}")
    print(f"Human package: {human_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
