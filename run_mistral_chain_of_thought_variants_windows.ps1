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
  "--mistral-model", "mistral:7b-instruct",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commonArgs += "--skip-existing"
}

Write-Host "Running Mistral chain-of-thought..."
python @commonArgs

Write-Host "Running Mistral chain-of-thought + UML elements..."
python @($commonArgs + @("--few-shot-prompt-structure", "uml_elements"))

Write-Host "Running Mistral chain-of-thought + structural validation rules..."
python @($commonArgs + @("--few-shot-prompt-structure", "structural_validation"))

Write-Host "Running Mistral chain-of-thought + PlantUML example..."
python @($commonArgs + @("--few-shot-prompt-structure", "plantuml_example"))
