param(
  [string]$EmbeddingModel = "sentence-transformers/all-MiniLM-L6-v2",
  [double]$Threshold = 0.80,
  [double]$RelaxedThreshold = 0.48,
  [string]$Device = "cpu",
  [int]$SampleCount = 5
)

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\run_semantic_state_matching_324_windows.ps1" `
  -EmbeddingModel $EmbeddingModel `
  -Threshold $Threshold `
  -RelaxedThreshold $RelaxedThreshold `
  -Device $Device `
  -SampleCount $SampleCount

& "$PSScriptRoot\run_semantic_state_matching_run2_windows.ps1" `
  -EmbeddingModel $EmbeddingModel `
  -Threshold $Threshold `
  -RelaxedThreshold $RelaxedThreshold `
  -Device $Device `
  -SampleCount $SampleCount

& "$PSScriptRoot\run_semantic_state_matching_run3_windows.ps1" `
  -EmbeddingModel $EmbeddingModel `
  -Threshold $Threshold `
  -RelaxedThreshold $RelaxedThreshold `
  -Device $Device `
  -SampleCount $SampleCount
