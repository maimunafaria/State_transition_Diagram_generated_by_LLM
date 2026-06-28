param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.deepseek_fewshot_sequential_example_guided.used.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$DeepSeek14Model = "deepseek-r1:14b",
    [int]$RepairAttempts = 8,
    [int]$ExamplesPerIssue = 2
)

$ErrorActionPreference = "Stop"

$EmptyRagDocs = "data\empty_rag_docs"
if (-not (Test-Path $EmptyRagDocs)) {
    New-Item -ItemType Directory -Path $EmptyRagDocs | Out-Null
}

python Code\Scripts\plantuml_experiment_pipeline.py run `
    --dataset-root $DatasetRoot `
    --results-root $ResultsRoot `
    --rag-docs-dir $EmptyRagDocs `
    --rag-mode lexical `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__sequential_example_guided `
    --deepseek14-model $DeepSeek14Model `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_example_guided `
    --repair-ablation-tag sequential_example_guided `
    --repair-example-dataset $RepairExampleDataset `
    --repair-examples-per-issue $ExamplesPerIssue `
    --save-prompts
