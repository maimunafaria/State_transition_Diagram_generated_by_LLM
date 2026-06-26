param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 10,
  [string]$PlantUmlJar = "tools\plantuml.jar",
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"
  if (-not (Get-Command plantuml -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $PlantUmlJar)) {
      throw "PlantUML was not found. Download plantuml.jar to '$PlantUmlJar'."
    }
    if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
      throw "Java is required to run $PlantUmlJar. Install Java and ensure 'java' is available in PATH."
    }
    $env:PLANTUML_JAR = (Resolve-Path $PlantUmlJar).Path
    Write-Host "Using PlantUML JAR: $env:PLANTUML_JAR"
  }

  $sourceRunsRoot = "Code\untitled folder\results\plantuml_pipeline\runs"
  $outputRunId = "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__compiler_guided_issue_routed_original_fewshot"
  $commandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py", "run",
    "--dataset-root", "dataset",
    "--results-root", "results\plantuml_pipeline",
    "--repair-source-runs-root", $sourceRunsRoot,
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-mode", "compiler_guided_issue_routed",
    "--repair-ablation-tag", "compiler_guided_issue_routed_original_fewshot",
    "--repair-attempts", "$RepairAttempts",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId
  )

  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running compiler-guided issue-routed DeepSeek repair..."
  Write-Host "Frozen source: $sourceRunsRoot\open_source__deepseek_r1_14b__few_shot"
  Write-Host "Output: results\plantuml_pipeline\runs\$outputRunId"
  python @commandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Compiler-guided issue-routed DeepSeek repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
