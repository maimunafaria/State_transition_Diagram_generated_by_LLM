param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [string]$PlantUmlJar = "$env:USERPROFILE\tools\plantuml.jar",
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  if (Test-Path $PlantUmlJar) {
    if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
      throw "Java is required to run '$PlantUmlJar'."
    }
    $env:PLANTUML_JAR = (Resolve-Path $PlantUmlJar).Path
    java -jar $env:PLANTUML_JAR -version
    if ($LASTEXITCODE -ne 0) {
      throw "PlantUML JAR self-check failed."
    }
  }
  elseif (Get-Command plantuml -ErrorAction SilentlyContinue) {
    Remove-Item Env:PLANTUML_JAR -ErrorAction SilentlyContinue
    plantuml -version
    if ($LASTEXITCODE -ne 0) {
      throw "PlantUML command self-check failed."
    }
  }
  else {
    throw "PlantUML was not found. Expected JAR: '$PlantUmlJar'."
  }

  $outputRunId = "open_source__mistral__rag_validation_generator_critic_repair__compiler_constrained_patch"
  $commandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py", "run",
    "--dataset-root", "dataset",
    "--results-root", "results\plantuml_pipeline",
    "--repair-source-runs-root", "Code\untitled folder\results\plantuml_pipeline\runs",
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-mode", "compiler_constrained_patch",
    "--repair-ablation-tag", "compiler_constrained_patch",
    "--repair-attempts", "$RepairAttempts",
    "--temperature", "0",
    "--max-tokens", "4096",
    "--timeout", "600",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId,
    "--only-case-id", "case_02_inventory",
    "--only-case-id", "case_16_weather_monitoring_system",
    "--only-case-id", "case_28_ott_based_system_mini_reel",
    "--only-case-id", "case_34_green_rides",
    "--only-case-id", "case_46_digital_watch",
    "--only-case-id", "case_59_atm_1",
    "--only-case-id", "case_78_class_campaign_version_2"
  )
  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running compiler-constrained patch repair for 7 Mistral RAG cases..."
  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Mistral compiler-constrained patch repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
