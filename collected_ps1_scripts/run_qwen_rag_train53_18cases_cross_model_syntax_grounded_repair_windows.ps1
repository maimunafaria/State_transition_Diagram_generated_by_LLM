param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline_qwen_train53",
    [string]$SplitInput = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [string]$MistralModel = "mistral:7b-instruct",
    [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
    [string]$DeepSeekModel = "deepseek-r1:14b",
    [string]$GemmaModel = "gemma3:12b",
    [int]$RepairAttempts = 5
)

$ErrorActionPreference = "Stop"

$EmptyRagDocs = "data\empty_rag_docs"
if (-not (Test-Path $EmptyRagDocs)) {
    New-Item -ItemType Directory -Path $EmptyRagDocs | Out-Null
}

$RepairModels = @(
    @{ Tag = "syntax_grounded_repair_mistral"; Model = $MistralModel },
    @{ Tag = "syntax_grounded_repair_llama"; Model = $LlamaModel },
    @{ Tag = "syntax_grounded_repair_deepseek"; Model = $DeepSeekModel },
    @{ Tag = "syntax_grounded_repair_gemma"; Model = $GemmaModel }
)

foreach ($Repair in $RepairModels) {
    $Tag = $Repair.Tag
    $Model = $Repair.Model
    $RunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__$Tag"
    $SplitOutput = "data\processed\experiments\qwen_train53_split_35_seed42.$Tag.used.json"

    Write-Host "Running syntax-grounded cross-model repair: $Tag using $Model"
    python Code\Scripts\plantuml_experiment_pipeline.py run `
        --dataset-root $DatasetRoot `
        --results-root $ResultsRoot `
        --rag-docs-dir $EmptyRagDocs `
        --rag-mode lexical `
        --use-case-rag `
        --split-input $SplitInput `
        --split-output $SplitOutput `
        --skip-gpt-baseline `
        --only-run-id $RunId `
        --qwen-model $QwenModel `
        --runs 1 `
        --repair-attempts $RepairAttempts `
        --repair-mode syntax_grounded `
        --repair-ablation-tag $Tag `
        --repair-model $Model `
        --save-prompts
}
