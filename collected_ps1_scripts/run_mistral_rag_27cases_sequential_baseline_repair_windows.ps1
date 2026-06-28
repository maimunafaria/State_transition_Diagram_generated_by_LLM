param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.mistral_rag_sequential_baseline.used.json",
    [string]$MistralModel = "mistral:7b-instruct",
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
    --only-run-id open_source__mistral__rag_validation_generator_critic_repair__sequential_baseline `
    --mistral-model $MistralModel `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_baseline `
    --repair-ablation-tag sequential_baseline `
    --save-prompts
