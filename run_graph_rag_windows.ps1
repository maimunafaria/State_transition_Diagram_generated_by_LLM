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
  "--rag-mode", "graph",
  "--rag-profile", "standard",
  "--rag-ablation-tag", "graph",
  "--top-k-rag", "$TopK",
  "--skip-gpt-baseline",
  "--runs", "$Runs",
  "--save-prompts",
  "--only-run-id", "open_source__qwen25_7b_instruct__rag__graph",
  "--only-run-id", "open_source__mistral__rag__graph",
  "--only-run-id", "open_source__llama31_8b_instruct__rag__graph",
  "--only-run-id", "open_source__deepseek_r1_14b__rag__graph",
  "--only-run-id", "open_source__gemma3_12b__rag__graph"
)

if ($SkipExisting) {
  $commandArgs += "--skip-existing"
}

Write-Host "Running graph-based RAG for selected open-source models..."
Write-Host "Runs per case/config: $Runs"
Write-Host "Top-K graph-matched examples: $TopK"
if ($SkipExisting) {
  Write-Host "Skipping existing generated files."
}

python @commandArgs
