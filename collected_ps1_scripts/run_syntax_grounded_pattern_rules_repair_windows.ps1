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
  "--repair-mode", "syntax_grounded_pattern_rules",
  "--repair-ablation-tag", "syntax_grounded_pattern_rules",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__gemma3_12b__rag_validation_generator_critic_repair__syntax_grounded_pattern_rules"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running syntax-grounded repair with PlantUML structural-rule patterns..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"
if ($SkipExisting) {
  Write-Host "Skipping existing syntax-grounded-pattern-rules repair files."
}

python @commandArgs
