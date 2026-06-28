param(
  [int]$Runs = 1,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$commandArgs = @(
  "Code\Scripts\plantuml_experiment_pipeline.py",
  "run",
  "--dataset-root", "dataset",
  "--results-root", "results\plantuml_pipeline",
  "--skip-gpt-baseline",
  "--few-shot-count", "3",
  "--few-shot-prompt-structure", "structural_validation_patterns",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__few_shot",
  "--only-run-id", "open_source__mistral__few_shot",
  "--only-run-id", "open_source__llama31_8b_instruct__few_shot",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot",
  "--only-run-id", "open_source__gemma3_12b__few_shot"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running few-shot generation with PlantUML structural-validation patterns..."
Write-Host "Runs per case/config: $Runs"
if ($SkipExisting) {
  Write-Host "Skipping existing few-shot structural-pattern files."
}

python @commandArgs
