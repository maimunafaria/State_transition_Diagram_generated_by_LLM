param(
  [string]$Model = "deepseek-r1:14b",
  [string]$OllamaHost = "http://localhost:11434",
  [int]$Timeout = 180,
  [int]$Limit = 0,
  [switch]$Fresh
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $commandArgs = @(
    "Code\Scripts\judge_valid_diagrams_deepseek.py",
    "--valid-diagrams-root", "valid_diagrams",
    "--model", $Model,
    "--ollama-host", $OllamaHost,
    "--timeout", "$Timeout",
    "--output-csv", "results\plantuml_pipeline\llm_judge\deepseek_valid_diagram_judgements.csv",
    "--output-jsonl", "results\plantuml_pipeline\llm_judge\deepseek_valid_diagram_raw.jsonl"
  )

  if ($Limit -gt 0) {
    $commandArgs += @("--limit", "$Limit")
  }

  if ($Fresh) {
    $commandArgs += "--fresh"
    Write-Host "Starting a fresh DeepSeek judgement run..."
  }
  else {
    Write-Host "Resuming the DeepSeek judgement run..."
  }

  Write-Host "Judge model: $Model"
  Write-Host "Input folder: valid_diagrams"
  Write-Host "CSV output: results\plantuml_pipeline\llm_judge\deepseek_valid_diagram_judgements.csv"

  python @commandArgs

  if ($LASTEXITCODE -ne 0) {
    throw "DeepSeek judgement failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
