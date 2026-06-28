param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$Resume
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceRunsRoot = "Code\untitled folder\results\plantuml_pipeline\runs"
$ResultsRoot = "final_results"
$OutputRunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_no_rules_original_rag"
$OutputRunDir = Join-Path $ResultsRoot "runs\$OutputRunId"

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $SourceRunDir = Join-Path $SourceRunsRoot "open_source__qwen25_7b_instruct__rag"
  if (-not (Test-Path $SourceRunDir)) {
    throw "Frozen original Qwen Basic RAG folder not found: $SourceRunDir"
  }

  if ((Test-Path $OutputRunDir) -and (-not $Resume)) {
    throw "Output already exists: $OutputRunDir. Use -Resume to skip completed cases."
  }

  $CommandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py",
    "run",
    "--dataset-root", "dataset",
    "--results-root", $ResultsRoot,
    "--repair-source-runs-root", $SourceRunsRoot,
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--qwen-model", "qwen2.5:7b-instruct",
    "--requirement-source", "structured",
    "--repair-mode", "syntax_grounded_no_rules",
    "--repair-ablation-tag", "syntax_grounded_no_rules_original_rag",
    "--repair-attempts", "$RepairAttempts",
    "--runs", "$Runs",
    "--seed", "42",
    "--save-prompts",
    "--only-run-id", $OutputRunId
  )

  if ($Resume) {
    $CommandArgs += "--skip-existing"
  }

  Write-Host "Running Qwen syntax-guided repair without Structural Validation Rules..."
  Write-Host "Frozen source: $SourceRunDir"
  Write-Host "Output: $OutputRunDir"
  Write-Host "Repair attempts per case: $RepairAttempts"

  python @CommandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Qwen repair run failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
