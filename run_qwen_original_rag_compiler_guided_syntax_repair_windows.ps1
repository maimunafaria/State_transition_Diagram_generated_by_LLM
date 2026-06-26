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
  $outputRunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__compiler_guided_syntax_original_rag"

  if (-not (Get-Command plantuml -ErrorAction SilentlyContinue)) {
    throw "PlantUML CLI is required. Install it and ensure 'plantuml' is available in PATH."
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
    "--repair-mode", "compiler_guided_syntax",
    "--repair-ablation-tag", "compiler_guided_syntax_original_rag",
    "--repair-attempts", "$RepairAttempts",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId
  )

  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running compiler-guided Qwen repair on frozen original RAG diagrams..."
  Write-Host "Output: results\plantuml_pipeline\runs\$outputRunId"
  python @commandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Compiler-guided Qwen repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
