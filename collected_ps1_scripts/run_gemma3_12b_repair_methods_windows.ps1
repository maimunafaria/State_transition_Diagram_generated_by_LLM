param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$commonArgs = @(
  "Code\Scripts\plantuml_experiment_pipeline.py",
  "run",
  "--dataset-root", "dataset",
  "--results-root", "results\plantuml_pipeline",
  "--rag-docs-dir", "data\rag_corpus",
  "--rag-db-dir", "results\rag_db",
  "--rag-mode", "vector",
  "--skip-gpt-baseline",
  "--gemma3-model", "gemma3:12b",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commonArgs += "--skip-existing"
}

Write-Host "Running Gemma 3 12B repair methods for all test cases..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Repair attempts per case: $RepairAttempts"
if ($SkipExisting) {
  Write-Host "Skipping existing repaired files."
}

Write-Host "1/3 Few-shot + Repair"
python @commonArgs --only-run-id open_source__gemma3_12b__few_shot_validation_generator_critic_repair --few-shot-count 3

Write-Host "2/3 RAG + Repair"
python @commonArgs --only-run-id open_source__gemma3_12b__rag_validation_generator_critic_repair

Write-Host "3/3 Chain-of-thought + Repair"
python @commonArgs --only-run-id open_source__gemma3_12b__chain_of_thought_validation_generator_critic_repair
