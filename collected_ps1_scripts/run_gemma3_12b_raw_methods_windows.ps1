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
  "--rag-db-dir", "results\rag_db",
  "--skip-gpt-baseline",
  "--gemma3-model", "gemma3:12b",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commonArgs += "--skip-existing"
}

Write-Host "Running Gemma 3 12B raw methods for all test cases..."
Write-Host "Runs per case/config: $Runs"
if ($SkipExisting) {
  Write-Host "Skipping existing generated files."
}

Write-Host "1/5 Zero-shot"
python @commonArgs --only-run-id open_source__gemma3_12b__zero_shot

Write-Host "2/5 Few-shot"
python @commonArgs --only-run-id open_source__gemma3_12b__few_shot --few-shot-count 3

Write-Host "3/5 One-shot"
python @commonArgs --only-run-id open_source__gemma3_12b__few_shot --few-shot-count 1

Write-Host "4/5 Chain-of-thought"
python @commonArgs --only-run-id open_source__gemma3_12b__chain_of_thought

Write-Host "5/5 RAG"
python @commonArgs --only-run-id open_source__gemma3_12b__rag
