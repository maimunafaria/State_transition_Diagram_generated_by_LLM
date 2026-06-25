param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline_qwen_train53",
    [string]$SplitInput = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [string]$RepairExampleDataset = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [string]$MistralModel = "mistral:7b-instruct",
    [int]$RepairAttempts = 8,
    [int]$ExamplesPerIssue = 2
)

$ErrorActionPreference = "Stop"

$EmptyRagDocs = "data\empty_rag_docs"
if (-not (Test-Path $EmptyRagDocs)) {
    New-Item -ItemType Directory -Path $EmptyRagDocs | Out-Null
}

$Runs = @(
    @{
        Name = "baseline"
        Tag = "repair_mistral"
        Mode = "baseline"
        Extra = @()
        Attempts = 5
    },
    @{
        Name = "syntax-grounded"
        Tag = "syntax_grounded_repair_mistral"
        Mode = "syntax_grounded"
        Extra = @()
        Attempts = 5
    },
    @{
        Name = "example-guided"
        Tag = "example_guided_repair_mistral"
        Mode = "example_guided"
        Extra = @("--repair-example-dataset", $RepairExampleDataset, "--repair-examples-per-issue", "$ExamplesPerIssue")
        Attempts = 5
    },
    @{
        Name = "sequential-example-guided"
        Tag = "sequential_example_guided_repair_mistral"
        Mode = "sequential_example_guided"
        Extra = @("--repair-example-dataset", $RepairExampleDataset, "--repair-examples-per-issue", "$ExamplesPerIssue")
        Attempts = $RepairAttempts
    }
)

foreach ($Run in $Runs) {
    $Tag = $Run.Tag
    $RunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__$Tag"
    $SplitOutput = "data\processed\experiments\qwen_train53_split_35_seed42.$Tag.used.json"

    Write-Host "Running Mistral repair method: $($Run.Name)"
    $ArgsList = @(
        "Code\Scripts\plantuml_experiment_pipeline.py", "run",
        "--dataset-root", $DatasetRoot,
        "--results-root", $ResultsRoot,
        "--rag-docs-dir", $EmptyRagDocs,
        "--rag-mode", "lexical",
        "--use-case-rag",
        "--split-input", $SplitInput,
        "--split-output", $SplitOutput,
        "--skip-gpt-baseline",
        "--only-run-id", $RunId,
        "--qwen-model", $QwenModel,
        "--runs", "1",
        "--repair-attempts", "$($Run.Attempts)",
        "--repair-mode", $Run.Mode,
        "--repair-ablation-tag", $Tag,
        "--repair-model", $MistralModel,
        "--save-prompts"
    ) + $Run.Extra

    python @ArgsList
}
