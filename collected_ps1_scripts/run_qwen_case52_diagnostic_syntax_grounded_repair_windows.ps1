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
  "--repair-ablation-tag", "diagnostic_syntax_grounded_case52",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-case-id", "case_52_microwave_oven",
  "--only-run-id", "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__diagnostic_syntax_grounded_case52"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running Qwen RAG diagnostic syntax-grounded repair for case_52_microwave_oven..."
Write-Host "Output run id: open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__diagnostic_syntax_grounded_case52"
Write-Host "Repair attempts: $RepairAttempts"

python @commandArgs
