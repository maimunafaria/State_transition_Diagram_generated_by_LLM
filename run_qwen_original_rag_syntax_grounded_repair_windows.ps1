param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $sourceRunsRoot = "Code\untitled folder\results\plantuml_pipeline\runs"
  $outputRunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag"

  if (-not (Test-Path $sourceRunsRoot)) {
    throw "Original runs folder not found: $sourceRunsRoot"
  }

  $commandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py",
    "run",
    "--dataset-root", "dataset",
    "--results-root", "results\plantuml_pipeline",
    "--repair-source-runs-root", $sourceRunsRoot,
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-mode", "syntax_grounded",
    "--repair-ablation-tag", "syntax_grounded_original_rag",
    "--repair-attempts", "$RepairAttempts",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId
  )

  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running Qwen Syntax-Grounded Repair on the frozen ORIGINAL RAG diagrams..."
  Write-Host "Source: $sourceRunsRoot\open_source__qwen25_7b_instruct__rag"
  Write-Host "Output: results\plantuml_pipeline\runs\$outputRunId"

  python @commandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Qwen original-RAG Syntax-Grounded Repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
