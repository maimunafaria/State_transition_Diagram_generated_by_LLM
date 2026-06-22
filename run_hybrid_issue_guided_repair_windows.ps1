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
  "--repair-mode", "hybrid_issue_guided",
  "--repair-ablation-tag", "hybrid_issue_guided",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__gemma3_12b__chain_of_thought_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__gemma3_12b__rag_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__mistral__rag_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__hybrid_issue_guided",
  "--only-run-id", "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__hybrid_issue_guided"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running hybrid issue-guided repair for the seven selected model/method pairs..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"

python @commandArgs
