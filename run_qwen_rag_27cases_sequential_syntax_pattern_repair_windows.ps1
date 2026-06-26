param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.qwen_rag_sequential_syntax_pattern.used.json",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [int]$RepairAttempts = 8
)

$ErrorActionPreference = "Stop"

python Code\Scripts\plantuml_experiment_pipeline.py run `
    --dataset-root $DatasetRoot `
    --results-root $ResultsRoot `
    --rag-docs-dir data\empty_rag_docs `
    --rag-mode lexical `
    --use-case-rag `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__sequential_syntax_grounded_pattern_rules `
    --qwen-model $QwenModel `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_syntax_grounded_pattern_rules `
    --repair-ablation-tag sequential_syntax_grounded_pattern_rules `
    --save-prompts
