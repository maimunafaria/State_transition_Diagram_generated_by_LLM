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
  "--repair-mode", "transition_patch",
  "--repair-ablation-tag", "transition_patch_case41",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-case-id", "case_41_video_suggestion_system",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__transition_patch_case41"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running DeepSeek transition-patch repair for case_41_video_suggestion_system..."
Write-Host "Output run id: open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__transition_patch_case41"
Write-Host "Repair attempts: $RepairAttempts"

python @commandArgs
