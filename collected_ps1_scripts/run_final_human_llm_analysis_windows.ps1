param(
  [string]$NewHumanCsv = "$HOME\Downloads\new human ev - Sheet1.csv"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputDir = "final_results\llm_judge\final_human_comparison"

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  if (-not (Test-Path $NewHumanCsv)) {
    throw "New human evaluation CSV not found: $NewHumanCsv"
  }

  python Code\Scripts\build_final_human_llm_comparison.py `
    --new-human-csv $NewHumanCsv `
    --output-dir $OutputDir
  if ($LASTEXITCODE -ne 0) {
    throw "Human/LLM comparison input build failed."
  }

  python Code\Scripts\analyze_llm_judge_results.py `
    --input-csv "$OutputDir\human_llm_final97_analysis_input.csv" `
    --output-dir "$OutputDir\analysis"
  if ($LASTEXITCODE -ne 0) {
    throw "LLM-as-a-Judge analysis failed."
  }

  Write-Host "Final human + LLM analysis complete."
  Write-Host "Output: $OutputDir"
}
finally {
  Pop-Location
}
