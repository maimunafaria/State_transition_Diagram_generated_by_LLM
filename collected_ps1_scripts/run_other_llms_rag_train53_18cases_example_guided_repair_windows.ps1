param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline_qwen_train53",
    [string]$SplitInput = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\qwen_train53_split_35_seed42.other_llms_example_guided_repair.used.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$MistralModel = "mistral:7b-instruct",
    [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
    [string]$DeepSeek14Model = "deepseek-r1:14b",
    [string]$Gemma3Model = "gemma3:12b",
    [int]$RepairAttempts = 5,
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
    --use-case-rag `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__mistral__rag_validation_generator_critic_repair__example_guided `
    --only-run-id open_source__llama31_8b_instruct__rag_validation_generator_critic_repair__example_guided `
    --only-run-id open_source__deepseek_r1_14b__rag_validation_generator_critic_repair__example_guided `
    --only-run-id open_source__gemma3_12b__rag_validation_generator_critic_repair__example_guided `
    --mistral-model $MistralModel `
    --llama-model $LlamaModel `
    --deepseek14-model $DeepSeek14Model `
    --gemma3-model $Gemma3Model `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode example_guided `
    --repair-ablation-tag example_guided `
    --repair-example-dataset $RepairExampleDataset `
    --repair-examples-per-issue $ExamplesPerIssue `
    --save-prompts
