param(
  [int]$Runs = 1,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$commonArgs = @(
  "Code\Scripts\plantuml_experiment_pipeline.py",
  "run",
  "--dataset-root", "dataset",
  "--results-root", "results\plantuml_pipeline",
  "--skip-gpt-baseline",
  "--only-run-id", "open_source__mistral__chain_of_thought",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commonArgs += "--skip-existing"
}

Write-Host "Running CoT + PlantUML example for Mistral..."
python @($commonArgs + @("--few-shot-prompt-structure", "plantuml_example"))

Write-Host "Running CoT + structural validation rules for Mistral..."
python @($commonArgs + @("--few-shot-prompt-structure", "structural_validation"))
