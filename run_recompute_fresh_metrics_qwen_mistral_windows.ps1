param(
    [string]$DatasetRoot = "dataset",
    [string[]]$ResultsRoots = @(
        "results\plantuml_pipeline_run2",
        "results\plantuml_pipeline_run3"
    ),
    [string]$OutputDir = "results\plantuml_pipeline\fresh_recomputed_metrics_qwen_mistral"
)

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\run_recompute_fresh_metrics_windows.ps1" `
    -DatasetRoot $DatasetRoot `
    -ResultsRoots $ResultsRoots `
    -RunFolders @(
        "open_source__qwen25_7b_instruct__rag",
        "open_source__mistral__rag"
    ) `
    -OutputDir $OutputDir
