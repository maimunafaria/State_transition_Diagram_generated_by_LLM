from __future__ import annotations

import argparse

from .commands import (
    command_ensemble,
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
            "All-in-one PlantUML validator/parser + metrics + 11-config batch runner + "
            "cross-model ensemble (stacked LLM or majority vote)"
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

    p_run = sub.add_parser("run", help="Run full 11-configuration experiment batch")
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
        "--repair-source-runs-root",
        default="",
        help=(
            "Optional runs directory containing frozen raw outputs to reuse as "
            "repair inputs. Repair results are still written under --results-root."
        ),
    )
    p_run.add_argument(
        "--rag-docs-dir",
        default=str(DEFAULT_RAG_DOCS_DIR),
        help="RAG documents directory",
    )
    p_run.add_argument(
        "--rag-mode",
        choices=["lexical", "vector", "graph"],
        default="lexical",
        help="RAG retrieval mode",
    )
    p_run.add_argument(
        "--rag-profile",
        choices=["standard", "behavior_aware"],
        default="standard",
        help="RAG selection/prompting profile",
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
        "--repair-mode",
        choices=[
            "baseline",
            "targeted",
            "syntax_grounded",
            "syntax_grounded_no_rules",
            "diagnostic_syntax_grounded",
            "compiler_guided_syntax",
            "compiler_guided_issue_routed",
            "syntax_preserving",
            "compiler_constrained_patch",
            "constrained_validator",
            "transition_patch",
            "hybrid_issue_guided",
            "syntax_grounded_pattern_rules",
            "full_patterns",
            "example_guided",
            "sequential_baseline",
            "sequential_example_guided",
            "sequential_syntax_grounded_pattern_rules",
        ],
        default="baseline",
        help="Repair prompt/acceptance mode for repair-enabled configs",
    )
    p_run.add_argument(
        "--repair-model",
        default="",
        help="Optional model id used only for repair calls; default repairs with the generator model",
    )
    p_run.add_argument(
        "--repair-example-dataset",
        default="data/sft/all_llm_violation_repair_sft.cleaned.jsonl",
        help="JSONL repair dataset used by --repair-mode example_guided.",
    )
    p_run.add_argument(
        "--repair-examples-per-issue",
        type=int,
        default=2,
        help="Historical repair examples retrieved per validation issue for example_guided repair.",
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
        "--split-input",
        default="",
        help=(
            "Optional existing split JSON to use instead of creating a new split. "
            "The file must contain test_case_ids and rag_case_ids."
        ),
    )
    p_run.add_argument(
        "--use-case-rag",
        action="store_true",
        help="Use non-test dataset cases as RAG documents in addition to --rag-docs-dir docs",
    )
    p_run.add_argument(
        "--baseline-subset-size",
        type=int,
        default=30,
        help="Target balanced subset size for GPT-4o baseline",
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
    p_run.add_argument(
        "--repair-ablation-tag",
        default="",
        help=(
            "Optional tag added to repair-family run_ids so repair ablation runs do not "
            "overwrite baseline repair outputs, e.g. targeted or deepseek_repair."
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
    p_run.add_argument(
        "--few-shot-prompt-structure",
        choices=[
            "original",
            "structural_validation",
            "uml_elements",
            "uml_elements_structural_validation",
            "plantuml_example",
            "structural_validation_patterns",
        ],
        default="original",
        help=(
            "Prompt structure for few-shot and chain-of-thought ablations. Non-original "
            "structures add a prompt_* suffix to affected run IDs."
        ),
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
    p_run.add_argument("--gpt-model", default="gpt-4o", help="GPT baseline model id")
    p_run.add_argument("--qwen-model", default="qwen2.5:7b-instruct", help="Qwen model id")
    p_run.add_argument("--qwen14-model", default="qwen2.5:14b-instruct", help="Qwen 14B model id")
    p_run.add_argument("--mistral-model", default="mistral:7b-instruct", help="Mistral model id")
    p_run.add_argument("--llama-model", default="llama3.1:8b-instruct-q4_K_M", help="Llama model id")
    p_run.add_argument("--llama70-model", default="llama3.1:70b", help="Llama 70B model id")
    p_run.add_argument("--deepseek-model", default="deepseek-r1:8b", help="DeepSeek model id")
    p_run.add_argument("--deepseek14-model", default="deepseek-r1:14b", help="DeepSeek 14B model id")
    p_run.add_argument("--gemma3-model", default="gemma3:12b", help="Gemma 3 12B model id")
    p_run.add_argument(
        "--skip-gpt-baseline",
        action="store_true",
        help="Skip proprietary GPT-4o baseline and run open-source configs only",
    )
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

    p_ensemble = sub.add_parser(
        "ensemble",
        help="Build cross-model ensemble (stacked LLM or majority vote) from existing Qwen/LLaMA runs",
    )
    p_ensemble.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Dataset root containing case_* folders",
    )
    p_ensemble.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Results root containing runs/ from prior experiments",
    )
    p_ensemble.add_argument(
        "--ensemble-root",
        default="ensemble_stacked_llm",
        help="Output folder under results-root for ensemble artifacts",
    )
    p_ensemble.add_argument(
        "--ensemble-method",
        choices=["stacked_llm", "majority_vote"],
        default="stacked_llm",
        help="Ensembling method (default: stacked_llm)",
    )
    p_ensemble.add_argument(
        "--strategy",
        action="append",
        help=(
            "Strategy to ensemble separately (repeatable). "
            "Default: one pooled ensemble from all five methods across Qwen, LLaMA, and DeepSeek."
        ),
    )
    p_ensemble.add_argument(
        "--candidate-run-id",
        action="append",
        help=(
            "Explicit source run_id to include in one cross-run candidate pool "
            "(repeatable). When set, --strategy and model-prefix defaults are ignored."
        ),
    )
    p_ensemble.add_argument(
        "--qwen-run-prefix",
        default="open_source__qwen25_7b_instruct",
        help="Run-id prefix for Qwen configurations",
    )
    p_ensemble.add_argument(
        "--llama-run-prefix",
        default="open_source__llama31_8b_instruct",
        help="Run-id prefix for LLaMA configurations",
    )
    p_ensemble.add_argument(
        "--deepseek-run-prefix",
        default="open_source__deepseek_r1_14b",
        help="Run-id prefix for DeepSeek configurations",
    )
    p_ensemble.add_argument(
        "--min-candidates",
        type=int,
        default=2,
        help="Minimum candidate outputs required per case before voting",
    )
    p_ensemble.add_argument(
        "--min-votes",
        type=int,
        default=0,
        help="Votes required to keep a state/transition (0 = strict majority)",
    )
    p_ensemble.add_argument(
        "--require-both-models",
        action="store_true",
        help="Require both Qwen and LLaMA candidates per case",
    )
    p_ensemble.add_argument(
        "--stack-model",
        default="llama3.1:8b-instruct",
        help="Meta-model used for stacked_llm ensembling",
    )
    p_ensemble.add_argument(
        "--stack-use-rag",
        action="store_true",
        help="Use domain/reference RAG context in stacked_llm meta-generation",
    )
    p_ensemble.add_argument(
        "--stack-rag-docs-dir",
        default=str(DEFAULT_RAG_DOCS_DIR),
        help="RAG documents directory for stacked_llm",
    )
    p_ensemble.add_argument(
        "--stack-rag-mode",
        choices=["lexical", "vector"],
        default="lexical",
        help="RAG retrieval mode for stacked_llm",
    )
    p_ensemble.add_argument(
        "--stack-rag-db-dir",
        default=str(DEFAULT_RAG_DB_DIR),
        help="Persisted vector database directory for stacked_llm vector RAG",
    )
    p_ensemble.add_argument(
        "--stack-rag-collection-name",
        default=DEFAULT_RAG_COLLECTION_NAME,
        help="Vector collection name for stacked_llm RAG",
    )
    p_ensemble.add_argument(
        "--stack-top-k-rag",
        type=int,
        default=3,
        help="Top-k RAG docs for stacked_llm",
    )
    p_ensemble.add_argument(
        "--stack-rag-max-chars-per-doc",
        type=int,
        default=1200,
        help="Maximum characters per stacked_llm RAG document",
    )
    p_ensemble.add_argument(
        "--stack-rag-domain-hint",
        action="append",
        help="Optional domain hint for stacked_llm RAG retrieval (repeatable)",
    )
    p_ensemble.add_argument(
        "--stack-requirement-source",
        choices=["raw", "structured"],
        default="structured",
        help="Requirement text source used by the stack model",
    )
    p_ensemble.add_argument(
        "--stack-max-candidates",
        type=int,
        default=6,
        help="Maximum distinct candidates passed to the stack model",
    )
    p_ensemble.add_argument("--stack-temperature", type=float, default=0.1)
    p_ensemble.add_argument("--stack-top-p", type=float, default=0.9)
    p_ensemble.add_argument("--stack-max-tokens", type=int, default=1536)
    p_ensemble.add_argument(
        "--stack-timeout",
        type=int,
        default=300,
        help="Stack model call timeout (seconds)",
    )
    p_ensemble.add_argument(
        "--stack-ollama-host",
        default="http://127.0.0.1:11434",
        help="Ollama host for local stack model calls",
    )
    p_ensemble.add_argument(
        "--stack-fallback-majority",
        action="store_true",
        help="Fallback to majority vote when stacked_llm generation fails",
    )
    p_ensemble.set_defaults(func=command_ensemble)

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
        choices=["all", "qwen", "llama", "ensemble", "gpt"],
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
