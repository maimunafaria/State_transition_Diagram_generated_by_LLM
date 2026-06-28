param(
  [string]$RunsRoot = "final_results\runs",
  [string]$OutputDir = "final_results\recalculated_repair_analysis",
  [string]$PlantUmlJar = "$HOME\tools\plantuml.jar",
  [int]$Workers = 4
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  python Code\Scripts\compare_baseline_syntax_repair_fresh.py `
    --runs-root $RunsRoot `
    --output-dir $OutputDir `
    --plantuml-jar $PlantUmlJar `
    --workers $Workers

  if ($LASTEXITCODE -ne 0) {
    throw "Fresh repair analysis failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
