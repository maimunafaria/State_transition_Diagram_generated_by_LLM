param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [string]$RepairModel = "qwen2.5:7b-instruct",
  [string]$PlantUmlJar = "tools\plantuml.jar",
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"
  $sourceRunsRoot = "final_results\runs"
  $resultsRoot = "final_results\validator_guided_graph_repair_qwen27"
  $splitInput = "data\processed\experiments\split_35_seed42.json"
  $outputRunId = "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__validator_guided_graph_edit_original_rag"

  if (-not (Get-Command plantuml -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $PlantUmlJar)) {
      throw "PlantUML was not found. Download plantuml.jar to '$PlantUmlJar'."
    }
    if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
      throw "Java is required and must be available in PATH."
    }
    $env:PLANTUML_JAR = (Resolve-Path $PlantUmlJar).Path
  }

  $commandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py",
    "run",
    "--dataset-root", "dataset",
    "--results-root", $resultsRoot,
    "--repair-source-runs-root", $sourceRunsRoot,
    "--split-input", $splitInput,
    "--split-output", "$resultsRoot\split_used.json",
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-mode", "validator_guided_graph_edit",
    "--repair-ablation-tag", "validator_guided_graph_edit_original_rag",
    "--repair-model", $RepairModel,
    "--repair-attempts", "$RepairAttempts",
    "--temperature", "0.0",
    "--top-p", "1.0",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId
  )

  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running validator-guided graph repair on the original 27 Qwen RAG cases..."
  Write-Host "Frozen source: $sourceRunsRoot\open_source__qwen25_7b_instruct__rag"
  Write-Host "Repair model: $RepairModel"
  Write-Host "Output: $resultsRoot\runs\$outputRunId"
  python @commandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Validator-guided graph repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
