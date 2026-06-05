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
  "--few-shot-prompt-structure", "structural_validation",
  "--only-run-id", "open_source__qwen25_7b_instruct__chain_of_thought",
  "--only-run-id", "open_source__mistral__chain_of_thought",
  "--only-run-id", "open_source__llama31_8b_instruct__chain_of_thought",
  "--only-run-id", "open_source__deepseek_r1_14b__chain_of_thought",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running chain-of-thought + structural validation rules strategies for all test cases..."
Write-Host "Runs per case/config: $Runs"
if ($SkipExisting) {
  Write-Host "Skipping existing generated files."
}

python @commandArgs
