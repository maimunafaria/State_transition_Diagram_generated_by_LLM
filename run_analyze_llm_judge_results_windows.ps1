param(
  [Parameter(Mandatory = $true)]
  [string]$InputCsv,

  [string]$OutputDir = "results\plantuml_pipeline\llm_judge\analysis",

  [switch]$Fresh
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  if ($Fresh -and (Test-Path $OutputDir)) {
    Remove-Item -Recurse -Force $OutputDir
  }

  $commandArgs = @(
    "Code\Scripts\analyze_llm_judge_results.py",
    "--input-csv", $InputCsv,
    "--output-dir", $OutputDir
  )

  Write-Host ""
  Write-Host "Running LLM-as-a-Judge analysis"
  Write-Host "Input : $InputCsv"
  Write-Host "Output: $OutputDir"

  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "LLM-as-a-Judge analysis failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
