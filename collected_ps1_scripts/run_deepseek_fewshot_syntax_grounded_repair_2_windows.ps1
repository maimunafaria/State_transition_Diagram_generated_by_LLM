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
  "--repair-mode", "syntax_grounded",
  "--repair-ablation-tag", "syntax_grounded_2",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded_2"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running DeepSeek few-shot syntax-grounded repair rerun 2..."
Write-Host "Output run id: open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded_2"
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"

python @commandArgs
