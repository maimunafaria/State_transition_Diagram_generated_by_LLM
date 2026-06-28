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
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ValidRoot = "final_results\valid_diagrams"
$OutputDir = "final_results\llm_judge\three_judge_reference_free_final_valid97"

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  if (-not (Test-Path $ValidRoot)) {
    throw "Valid-diagram package not found: $ValidRoot"
  }

  $DiagramCount = (
    Get-ChildItem -Path $ValidRoot -Filter "diagram.puml" -File -Recurse
  ).Count
  if ($DiagramCount -ne 97) {
    throw "Expected 97 unique valid diagrams, but found $DiagramCount in $ValidRoot"
  }

  python -c "import ollama"
  if ($LASTEXITCODE -ne 0) {
    throw "Python Ollama client is missing. Run: pip install ollama"
  }

  $CommandArgs = @(
    "Code\Scripts\judge_three_llms_reference_free.py",
    "--valid-diagrams-root", $ValidRoot,
    "--output-dir", $OutputDir,
    "--ollama-host", $OllamaHost,
    "--deepseek-model", $DeepSeekModel,
    "--llama-model", $LlamaModel,
    "--prometheus-model", $PrometheusModel,
    "--timeout", "$Timeout",
    "--shuffle-seed", "20260628"
  )

  if ($Limit -gt 0) {
    $CommandArgs += @("--limit", "$Limit")
  }
  if ($Fresh) {
    $CommandArgs += "--fresh"
  }
  if ($RetryFailed) {
    $CommandArgs += "--retry-failed"
  }

  Write-Host "Running three blind LLM judges on $DiagramCount unique valid diagrams..."
  Write-Host "Requirements: structured requirement.txt files"
  Write-Host "DeepSeek   : $DeepSeekModel"
  Write-Host "Llama      : $LlamaModel"
  Write-Host "Prometheus : $PrometheusModel"
  Write-Host "Output     : $OutputDir"

  python @CommandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "Three-LLM judgment failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
