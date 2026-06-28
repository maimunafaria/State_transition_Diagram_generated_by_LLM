param(
  [string]$DeepSeekModel = "deepseek-r1:14b",
  [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
  [string]$PrometheusModel = "ggozad/prometheus2",
  [string]$OllamaHost = "http://localhost:11434",
  [int]$Timeout = 300,
  [int]$Limit = 0,
  [switch]$Fresh
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $commandArgs = @(
    "Code\Scripts\judge_three_llms_reference_free.py",
    "--valid-diagrams-root", "valid_diagrams_from_untitled_raw_deduped",
    "--output-dir", "results\plantuml_pipeline\llm_judge\three_judge_reference_free_v1_valid_diagrams_from_untitled_raw_deduped",
    "--ollama-host", $OllamaHost,
    "--deepseek-model", $DeepSeekModel,
    "--llama-model", $LlamaModel,
    "--prometheus-model", $PrometheusModel,
    "--timeout", "$Timeout",
    "--shuffle-seed", "20260627"
  )

  if ($Limit -gt 0) {
    $commandArgs += @("--limit", "$Limit")
  }
  if ($Fresh) {
    $commandArgs += "--fresh"
  }

  Write-Host ""
  Write-Host "Running 3-LLM judge on valid_diagrams_from_untitled_raw_deduped"
  Write-Host "DeepSeek   : $DeepSeekModel"
  Write-Host "Llama      : $LlamaModel"
  Write-Host "Prometheus : $PrometheusModel"
  Write-Host "OllamaHost : $OllamaHost"
  Write-Host "Output dir : results\\plantuml_pipeline\\llm_judge\\three_judge_reference_free_v1_valid_diagrams_from_untitled_raw_deduped"

  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Three-LLM judgement failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
