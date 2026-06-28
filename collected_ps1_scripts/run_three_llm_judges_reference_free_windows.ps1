param(
  [string]$DeepSeekModel = "deepseek-r1:14b",
  [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
  [string]$PrometheusModel = "ggozad/prometheus2",
  [string]$OllamaHost = "http://localhost:11434",
  [int]$Timeout = 300,
  [int]$Limit = 0,
  [switch]$Fresh,
  [switch]$RetryFailed
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  python -c "import ollama"
  if ($LASTEXITCODE -ne 0) {
    throw "Python Ollama client is missing. Run: pip install -r requirements.txt"
  }

  $commandArgs = @(
    "Code\Scripts\judge_three_llms_reference_free.py",
    "--valid-diagrams-root", "valid_diagrams",
    "--output-dir", "results\plantuml_pipeline\llm_judge\three_judge_reference_free_v1",
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
  if ($RetryFailed) {
    $commandArgs += "--retry-failed"
  }

  Write-Host "Starting the reference-free three-judge experiment..."
  Write-Host "DeepSeek: $DeepSeekModel"
  Write-Host "Llama: $LlamaModel"
  Write-Host "Prometheus: $PrometheusModel"
  Write-Host "Temperature: 0.0 | Top-p: 1.0 | Num-predict: 1200"

  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Three-judge experiment failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
