param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline_qwen_train53",
    [string]$SplitInput = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\qwen_train53_split_35_seed42.used.json",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [int]$Runs = 1
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
    --use-case-rag `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__qwen25_7b_instruct__rag `
    --qwen-model $QwenModel `
    --runs $Runs `
    --save-prompts
