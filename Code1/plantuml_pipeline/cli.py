from __future__ import annotations

import argparse

from .commands import (
    command_metrics,
    command_run,
    command_split,
    command_table,
    command_validate,
)
from .constants import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_RAG_COLLECTION_NAME,
    DEFAULT_RAG_DB_DIR,
    DEFAULT_RAG_DOCS_DIR,
    DEFAULT_RESULTS_ROOT,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PlantUML validator/parser, metrics, and UML state-diagram batch runner"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate and parse a PlantUML file")
    p_validate.add_argument("--puml", required=True, help="Path to .puml file")
    p_validate.add_argument("--json", action="store_true", help="Print JSON output")
    p_validate.set_defaults(func=command_validate)

    p_split = sub.add_parser("split", help="Create a reproducible stratified test/RAG split")
    p_split.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_split.add_argument(
        "--test-size",
        type=float,
        default=0.35,
        help="Fraction of cases used for testing/evaluation",
    )
    p_split.add_argument("--seed", type=int, default=42, help="Random seed")
    p_split.add_argument(
        "--output",
        default="data/processed/experiments/split_35_seed42.json",
        help="Path where split metadata is saved",
    )
    p_split.set_defaults(func=command_split)

    p_run = sub.add_parser("run", help="Run the UML state-diagram experiment batch")
    p_run.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_run.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Output root for run artifacts and metrics",
    )
    p_run.add_argument(
        "--rag-docs-dir",
        default=str(DEFAULT_RAG_DOCS_DIR),
        help="RAG documents directory",
    )
    p_run.add_argument(
        "--rag-mode",
        choices=["lexical", "vector"],
        default="lexical",
        help="RAG retrieval mode",
    )
    p_run.add_argument(
        "--rag-db-dir",
        default=str(DEFAULT_RAG_DB_DIR),
        help="Persisted vector database directory for --rag-mode vector",
    )
    p_run.add_argument(
        "--rag-collection-name",
        default=DEFAULT_RAG_COLLECTION_NAME,
        help="Vector collection name for --rag-mode vector",
    )
    p_run.add_argument("--runs", type=int, default=3, help="Runs per case/config")
    p_run.add_argument(
        "--repair-attempts",
        type=int,
        default=3,
        help="Maximum repair attempts per generated diagram for repair-enabled configs",
    )
    p_run.add_argument(
        "--test-size",
        type=float,
        default=0.35,
        help=(
            "Fraction of cases used for testing/evaluation. Use 0.35 to test on "
            "about 35%% and reserve the rest for few-shot/RAG examples."
        ),
    )
    p_run.add_argument(
        "--split-output",
        default="data/processed/experiments/split_35_seed42.json",
        help="Path where the generated train/test split metadata is saved",
    )
    p_run.add_argument(
        "--use-case-rag",
        action="store_true",
        help="Use non-test dataset cases as RAG documents in addition to --rag-docs-dir docs",
    )
    p_run.add_argument(
        "--requirement-source",
        choices=["raw", "structured"],
        default="structured",
        help="Requirement text source used in prompts",
    )
    p_run.add_argument("--top-k-rag", type=int, default=3, help="Top-k RAG docs")
    p_run.add_argument(
        "--rag-max-chars-per-doc",
        type=int,
        default=1200,
        help="Maximum characters per retrieved RAG document",
    )
    p_run.add_argument(
        "--rag-domain-hint",
        action="append",
        help="Optional domain hint to bias RAG retrieval (repeatable)",
    )
    p_run.add_argument(
        "--rag-ablation-tag",
        default="",
        help=(
            "Optional tag added to RAG-family run_ids so ablation runs do not overwrite "
            "default RAG outputs, e.g. examples_only or rules_only."
        ),
    )
    p_run.add_argument("--seed", type=int, default=42, help="Random seed")
    p_run.add_argument(
        "--few-shot-seed",
        type=int,
        default=42,
        help="Seed for randomized few-shot example selection",
    )
    p_run.add_argument(
        "--few-shot-count",
        type=int,
        default=3,
        help="Number of few-shot examples to include",
    )
    p_run.add_argument("--temperature", type=float, default=0.2)
    p_run.add_argument("--top-p", type=float, default=0.9)
    p_run.add_argument("--max-tokens", type=int, default=1024)
    p_run.add_argument("--timeout", type=int, default=300, help="Model call timeout (seconds)")
    p_run.add_argument(
        "--ollama-host",
        default="http://127.0.0.1:11434",
        help="Ollama host for open-source model calls",
    )
    p_run.add_argument("--qwen-model", default="qwen2.5:7b-instruct", help="Qwen model id")
    p_run.add_argument("--qwen14-model", default="qwen2.5:14b-instruct", help="Qwen 14B model id")
    p_run.add_argument("--mistral-model", default="mistral", help="Mistral model id")
    p_run.add_argument("--llama-model", default="llama3.1:8b-instruct-q4_K_M", help="Llama model id")
    p_run.add_argument("--llama70-model", default="llama3.1:70b", help="Llama 70B model id")
    p_run.add_argument("--deepseek-model", default="deepseek-r1:8b", help="DeepSeek model id")
    p_run.add_argument("--deepseek14-model", default="deepseek-r1:14b", help="DeepSeek 14B model id")
    p_run.add_argument(
        "--only-run-id",
        action="append",
        help="Run only selected run_id (repeatable)",
    )
    p_run.add_argument(
        "--only-case-id",
        action="append",
        help="Run only selected case_id from the test split (repeatable)",
    )
    p_run.add_argument("--skip-existing", action="store_true", help="Skip existing run files")
    p_run.add_argument("--save-prompts", action="store_true", help="Store prompts in .meta.json")
    p_run.set_defaults(func=command_run)

    p_metrics = sub.add_parser(
        "metrics", help="Recompute metrics from generated run files under results"
    )
    p_metrics.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_metrics.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Results root containing runs/",
    )
    p_metrics.set_defaults(func=command_metrics)

    p_table = sub.add_parser("table", help="Show metrics as a terminal table")
    p_table.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Results root containing metrics/",
    )
    p_table.add_argument(
        "--source",
        choices=["summary", "complexity", "per-run"],
        default="summary",
        help="Which metrics source to render as a table",
    )
    p_table.add_argument(
        "--model-family",
        choices=["all", "qwen", "llama"],
        default="all",
        help="Filter rows by model family based on run_id",
    )
    p_table.add_argument(
        "--columns",
        default="",
        help="Comma-separated columns to display (default depends on source)",
    )
    p_table.add_argument(
        "--sort-by",
        default="",
        help="Column to sort by (default depends on source)",
    )
    p_table.add_argument(
        "--asc",
        action="store_true",
        help="Sort ascending (default is descending)",
    )
    p_table.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit rows (0 = all rows)",
    )
    p_table.add_argument(
        "--run-id",
        action="append",
        help="Filter by run_id (repeatable)",
    )
    p_table.add_argument(
        "--structural-only",
        action="store_true",
        help="Show only structural validity percentage columns",
    )
    p_table.set_defaults(func=command_table)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))
