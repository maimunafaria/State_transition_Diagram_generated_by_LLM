#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "data" / "rag_corpus"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "rag_analysis"

ANALYSIS_GROUPS = {
    "examples_only": ["dataset_examples"],
    "rules_only": ["plantuml_rules"],
    "theory_only": ["state_diagram_theory"],
}


def recreate_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_markdown_tree(src_dir: Path, dst_dir: Path) -> int:
    count = 0
    for src in sorted(src_dir.rglob("*.md")):
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    return count


def build_analysis_corpora(source_root: Path, output_root: Path) -> list[dict[str, str | int]]:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, str | int]] = []

    for analysis_name, source_groups in ANALYSIS_GROUPS.items():
        analysis_dir = output_root / analysis_name
        recreate_dir(analysis_dir)
        copied = 0
        for group in source_groups:
            src_group_dir = source_root / group
            if not src_group_dir.exists():
                raise FileNotFoundError(f"Missing source RAG folder: {src_group_dir}")
            copied += copy_markdown_tree(src_group_dir, analysis_dir / group)
        manifest_rows.append(
            {
                "analysis_group": analysis_name,
                "source_groups": ",".join(source_groups),
                "documents_copied": copied,
                "output_dir": str(analysis_dir),
            }
        )

    manifest_path = output_root / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["analysis_group", "source_groups", "documents_copied", "output_dir"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    return manifest_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create analysis-specific RAG corpora from the main rag_corpus folder."
    )
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()

    rows = build_analysis_corpora(args.source_root.resolve(), args.output_root.resolve())
    for row in rows:
        print(
            f"{row['analysis_group']}: {row['documents_copied']} docs -> {row['output_dir']}"
        )
    print(f"Manifest: {args.output_root.resolve() / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
