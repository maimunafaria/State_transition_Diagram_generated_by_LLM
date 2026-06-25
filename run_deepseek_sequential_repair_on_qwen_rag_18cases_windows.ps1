param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline_qwen_train53",
    [string]$SplitInput = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [string]$DeepSeekModel = "deepseek-r1:14b",
    [int]$RepairAttempts = 8,
    [int]$ExamplesPerIssue = 2
)

$ErrorActionPreference = "Stop"

$EmptyRagDocs = "data\empty_rag_docs"
if (-not (Test-Path $EmptyRagDocs)) {
    New-Item -ItemType Directory -Path $EmptyRagDocs | Out-Null
}

$Tag = "sequential_example_guided_repair_deepseek"
$RunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__$Tag"

python Code\Scripts\plantuml_experiment_pipeline.py run `
    --dataset-root $DatasetRoot `
    --results-root $ResultsRoot `
    --rag-docs-dir $EmptyRagDocs `
    --rag-mode lexical `
    --use-case-rag `
    --split-input $SplitInput `
    --split-output "data\processed\experiments\qwen_train53_split_35_seed42.$Tag.used.json" `
    --skip-gpt-baseline `
    --only-run-id $RunId `
    --qwen-model $QwenModel `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_example_guided `
    --repair-ablation-tag $Tag `
    --repair-model $DeepSeekModel `
    --repair-example-dataset $RepairExampleDataset `
    --repair-examples-per-issue $ExamplesPerIssue `
    --save-prompts
