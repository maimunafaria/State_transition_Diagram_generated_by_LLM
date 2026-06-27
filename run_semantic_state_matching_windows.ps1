param(
  [string]$EmbeddingModel = "sentence-transformers/all-MiniLM-L6-v2",
  [double]$Threshold = 0.80,
  [string]$Device = "cpu",
  [int]$SampleCount = 5,
  [string]$OutputCsv = "results\plantuml_pipeline\semantic_state_matching\semantic_state_matches.csv"
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"
  python -c "import numpy, scipy, sentence_transformers, torch"
  if ($LASTEXITCODE -ne 0) {
    throw "Missing dependencies. Run: pip install sentence-transformers scipy"
  }

  $commandArgs = @(
    "Code\Scripts\evaluate_semantic_state_matching.py",
    "--dataset-root", "dataset",
    "--valid-diagrams-root", "valid_diagrams",
    "--output-csv", $OutputCsv,
    "--embedding-model", $EmbeddingModel,
    "--threshold", "$Threshold",
    "--device", $Device,
    "--batch-size", "32",
    "--seed", "42",
    "--sample-count", "$SampleCount"
  )

  Write-Host "Running semantic state matching..."
  Write-Host "Embedding model: $EmbeddingModel"
  Write-Host "Similarity threshold: $Threshold"
  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Semantic state matching failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
