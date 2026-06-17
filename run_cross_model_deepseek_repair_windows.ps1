param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 3,
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
  "--repair-mode", "targeted",
  "--repair-ablation-tag", "deepseek_repair",
  "--repair-model", "deepseek-r1:14b",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__few_shot_validation_generator_critic_repair__deepseek_repair",
  "--only-run-id", "open_source__mistral__rag_validation_generator_critic_repair__deepseek_repair",
  "--only-run-id", "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__deepseek_repair",
  "--only-run-id", "open_source__gemma3_12b__rag_validation_generator_critic_repair__deepseek_repair"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running targeted cross-model repair with DeepSeek R1 14B..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"
if ($SkipExisting) {
  Write-Host "Skipping existing repaired files."
}

python @commandArgs
