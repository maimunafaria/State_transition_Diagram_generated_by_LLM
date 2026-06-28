param(
  [string]$MetaModel = "deepseek-r1:14b",
  [string]$DeepSeekJudge = "deepseek-r1:14b",
  [string]$LlamaJudge = "llama3.1:8b-instruct-q4_K_M",
  [string]$PrometheusJudge = "ggozad/prometheus2",
  [string]$OllamaHost = "http://localhost:11434",
  [string]$PlantUmlJar = "",
  [int]$Timeout = 300,
  [int]$MaxTokens = 300,
  [int]$Seed = 42,
  [int]$ValidationWorkers = 4,
  [switch]$PreflightOnly,
  [switch]$Fresh
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $ProjectRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $CandidateRoot = "final_results\valid_diagrams"
  $JudgeCsv = "final_results\llm_judge\three_judge_reference_free_final_valid97\judge_scores_long.csv"
  $OutputDir = "final_results\meta_ensemble"

  if ([string]::IsNullOrWhiteSpace($PlantUmlJar)) {
    $ProjectJar = "tools\plantuml.jar"
    $HomeJar = Join-Path $HOME "tools\plantuml.jar"
    if (Test-Path $ProjectJar) {
      $PlantUmlJar = $ProjectJar
    }
    elseif (Test-Path $HomeJar) {
      $PlantUmlJar = $HomeJar
    }
    else {
      throw "PlantUML JAR not found in .\tools or $HOME\tools."
    }
  }

  if (-not (Test-Path $CandidateRoot)) {
    throw "Candidate package not found: $CandidateRoot"
  }
  if (-not (Test-Path $JudgeCsv)) {
    throw "Three-judge score CSV not found: $JudgeCsv"
  }
  if (-not (Test-Path $PlantUmlJar)) {
    throw "PlantUML JAR not found: $PlantUmlJar"
  }

  python -c "import numpy, scipy, sentence_transformers"
  if ($LASTEXITCODE -ne 0) {
    throw "Missing Python dependencies. Run: pip install -r requirements.txt"
  }

  $CommandArgs = @(
    "Code\Scripts\run_validation_filtered_meta_ensemble.py",
    "--candidate-root", $CandidateRoot,
    "--dataset-root", "dataset",
    "--split-file", "data\processed\experiments\split_35_seed42.json",
    "--judge-scores-csv", $JudgeCsv,
    "--output-dir", $OutputDir,
    "--meta-model", $MetaModel,
    "--ollama-host", $OllamaHost,
    "--deepseek-judge", $DeepSeekJudge,
    "--llama-judge", $LlamaJudge,
    "--prometheus-judge", $PrometheusJudge,
    "--plantuml-jar", $PlantUmlJar,
    "--timeout", "$Timeout",
    "--max-tokens", "$MaxTokens",
    "--seed", "$Seed",
    "--validation-workers", "$ValidationWorkers",
    "--embedding-model", "sentence-transformers/all-MiniLM-L6-v2",
    "--state-threshold", "0.80",
    "--state-relaxed-threshold", "0.48",
    "--embedding-device", "cpu"
  )

  if ($PreflightOnly) {
    $CommandArgs += "--preflight-only"
  }
  if ($Fresh) {
    $CommandArgs += "--fresh"
  }

  Write-Host "Running validation-filtered, selection-only meta-LLM ensemble..."
  Write-Host "Candidates : $CandidateRoot"
  Write-Host "Judge CSV  : $JudgeCsv"
  Write-Host "Meta-LLM   : $MetaModel"
  Write-Host "Output     : $OutputDir"
  Write-Host "Ground truth and State F1 are used only after selection."

  python @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Meta-LLM ensemble failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
