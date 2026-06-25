param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.selected_5llm_sequential_example_guided.used.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [string]$Gemma3Model = "gemma3:12b",
    [string]$MistralModel = "mistral:7b-instruct",
    [string]$DeepSeek14Model = "deepseek-r1:14b",
    [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
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
    --use-case-rag `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__sequential_example_guided `
    --only-run-id open_source__gemma3_12b__rag_validation_generator_critic_repair__sequential_example_guided `
    --only-run-id open_source__mistral__rag_validation_generator_critic_repair__sequential_example_guided `
    --only-run-id open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__sequential_example_guided `
    --only-run-id open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__sequential_example_guided `
    --qwen-model $QwenModel `
    --gemma3-model $Gemma3Model `
    --mistral-model $MistralModel `
    --deepseek14-model $DeepSeek14Model `
    --llama-model $LlamaModel `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_example_guided `
    --repair-ablation-tag sequential_example_guided `
    --repair-example-dataset $RepairExampleDataset `
    --repair-examples-per-issue $ExamplesPerIssue `
    --save-prompts
