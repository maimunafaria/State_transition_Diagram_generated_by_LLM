param(
  [int]$Runs = 1,
  [int]$TopK = 3,
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
  "--rag-mode", "vector",
  "--skip-gpt-baseline",
  "--rag-profile", "behavior_aware",
  "--rag-ablation-tag", "behavior_aware",
  "--top-k-rag", "$TopK",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__rag__behavior_aware",
  "--only-run-id", "open_source__mistral__rag__behavior_aware",
  "--only-run-id", "open_source__llama31_8b_instruct__rag__behavior_aware",
  "--only-run-id", "open_source__deepseek_r1_14b__rag__behavior_aware",
  "--only-run-id", "open_source__gemma3_12b__rag__behavior_aware"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running behavior-aware RAG for selected open-source models..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Top-K RAG docs: $TopK"
if ($SkipExisting) {
  Write-Host "Skipping existing generated files."
}

python @commandArgs
