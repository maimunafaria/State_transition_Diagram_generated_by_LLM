param(
  [string]$DeepSeekModel = "deepseek-r1:14b",
  [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
  [string]$OllamaHost = "http://localhost:11434",
  [int]$Timeout = 180,
  [int]$Limit = 0,
  [switch]$Fresh
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $judges = @(
    @{
      Name = "DeepSeek-R1 14B"
      Model = $DeepSeekModel
      Csv = "results\plantuml_pipeline\llm_judge\deepseek_valid_diagram_judgements.csv"
      Jsonl = "results\plantuml_pipeline\llm_judge\deepseek_valid_diagram_raw.jsonl"
    },
    @{
      Name = "Llama 3.1 8B"
      Model = $LlamaModel
      Csv = "results\plantuml_pipeline\llm_judge\llama_valid_diagram_judgements.csv"
      Jsonl = "results\plantuml_pipeline\llm_judge\llama_valid_diagram_raw.jsonl"
    }
  )

  foreach ($judge in $judges) {
    $commandArgs = @(
      "Code\Scripts\judge_valid_diagrams_deepseek.py",
      "--valid-diagrams-root", "valid_diagrams",
      "--model", $judge.Model,
      "--ollama-host", $OllamaHost,
      "--temperature", "0.0",
      "--top-p", "1.0",
      "--max-tokens", "1200",
      "--timeout", "$Timeout",
      "--seed", "20260627",
      "--output-csv", $judge.Csv,
      "--output-jsonl", $judge.Jsonl
    )

    if ($Limit -gt 0) {
      $commandArgs += @("--limit", "$Limit")
    }
    if ($Fresh) {
      $commandArgs += "--fresh"
    }

    Write-Host ""
    Write-Host "Running judge: $($judge.Name)"
    Write-Host "Model: $($judge.Model)"
    Write-Host "Temperature: 0.0 | Top-p: 1.0"
    Write-Host "Output: $($judge.Csv)"

    python @commandArgs
    if ($LASTEXITCODE -ne 0) {
      throw "$($judge.Name) judgement failed with exit code $LASTEXITCODE."
    }
  }
}
finally {
  Pop-Location
}
