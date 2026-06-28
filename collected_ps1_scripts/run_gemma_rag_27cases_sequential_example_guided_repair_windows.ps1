param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.gemma_rag_sequential_example_guided.used.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$Gemma3Model = "gemma3:12b",
    [int]$RepairAttempts = 8,
    [int]$ExamplesPerIssue = 2
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
    --only-run-id open_source__gemma3_12b__rag_validation_generator_critic_repair__sequential_example_guided `
    --gemma3-model $Gemma3Model `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_example_guided `
    --repair-ablation-tag sequential_example_guided `
    --repair-example-dataset $RepairExampleDataset `
    --repair-examples-per-issue $ExamplesPerIssue `
    --save-prompts
