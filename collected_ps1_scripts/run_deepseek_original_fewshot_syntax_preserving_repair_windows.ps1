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

  $outputRunId = "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_preserving"
  $commandArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py", "run",
    "--dataset-root", "dataset",
    "--results-root", "results\plantuml_pipeline",
    "--repair-source-runs-root", "Code\untitled folder\results\plantuml_pipeline\runs",
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-mode", "syntax_preserving",
    "--repair-ablation-tag", "syntax_preserving",
    "--repair-attempts", "$RepairAttempts",
    "--temperature", "0",
    "--max-tokens", "8192",
    "--timeout", "600",
    "--runs", "$Runs",
    "--save-prompts",
    "--only-run-id", $outputRunId,
    "--only-case-id", "case_32_e_visa_processing_and_follow_up_system",
    "--only-case-id", "case_65_plane",
    "--only-case-id", "case_67_atm_many_scenarios_1"
  )
  if ($SkipExisting) {
    $commandArgs += "--skip-existing"
  }

  Write-Host "Running syntax-preserving repair for 3 DeepSeek Few-shot cases..."
  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "DeepSeek syntax-preserving repair failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
