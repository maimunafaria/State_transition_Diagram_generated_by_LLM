param(
  [string]$StateMappingsCsv = "results\plantuml_pipeline\semantic_state_matching\semantic_state_matches.csv",
  [string]$OutputCsv = "results\plantuml_pipeline\semantic_transition_matching\topology_transition_matches.csv",
  [string]$LabelEmbeddingModel = "",
  [double]$LabelSimilarityThreshold = 0.80,
  [string]$Device = "cpu",
  [int]$SampleCount = 5
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"
  python -c "import numpy, scipy, sentence_transformers, torch"
  if ($LASTEXITCODE -ne 0) {
    throw "Missing dependencies. Run: pip install sentence-transformers scipy"
  }
  if (-not (Test-Path $StateMappingsCsv)) {
    throw "State-mapping CSV not found: $StateMappingsCsv"
  }

  $thresholdText = [string]::Format(
    [Globalization.CultureInfo]::InvariantCulture,
    "{0}",
    $LabelSimilarityThreshold
  )
  $commandArgs = @(
    "Code\Scripts\evaluate_topology_transition_matching.py",
    "--state-mappings-csv", $StateMappingsCsv,
    "--output-csv", $OutputCsv,
    "--label-similarity-threshold", $thresholdText,
    "--device", $Device,
    "--batch-size", "32",
    "--seed", "42",
    "--sample-count", "$SampleCount"
  )
  if ($LabelEmbeddingModel) {
    $commandArgs += @("--label-embedding-model", $LabelEmbeddingModel)
  }

  Write-Host "Running topology-based semantic transition matching..."
  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Topology transition matching failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
