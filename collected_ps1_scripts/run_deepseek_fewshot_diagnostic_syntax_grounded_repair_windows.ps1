param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$commandArgs = @(
  "Code\Scripts\plantuml_experiment_pipeline.py",
  "run",
  "--dataset-root", "dataset",
  "--results-root", "results\plantuml_pipeline",
  "--rag-docs-dir", "data\rag_corpus",
  "--rag-db-dir", "results\rag_db",
  "--skip-gpt-baseline",
  "--repair-mode", "diagnostic_syntax_grounded",
  "--repair-ablation-tag", "diagnostic_syntax_grounded",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__diagnostic_syntax_grounded"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running DeepSeek few-shot diagnostic syntax-grounded repair..."
Write-Host "Output run id: open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__diagnostic_syntax_grounded"
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"

python @commandArgs
