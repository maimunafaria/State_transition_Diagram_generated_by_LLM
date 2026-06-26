param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.gemma_rag_sequential_baseline.used.json",
    [string]$Gemma3Model = "gemma3:12b",
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
    --only-run-id open_source__gemma3_12b__rag_validation_generator_critic_repair__sequential_baseline `
    --gemma3-model $Gemma3Model `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_baseline `
    --repair-ablation-tag sequential_baseline `
    --save-prompts
