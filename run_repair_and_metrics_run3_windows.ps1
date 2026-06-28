param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$SkipExisting,
  [string]$EmbeddingModel = "sentence-transformers/all-MiniLM-L6-v2",
  [double]$Threshold = 0.80,
  [double]$RelaxedThreshold = 0.48,
  [string]$Device = "cpu",
  [int]$SampleCount = 5
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"

  $resultsRoot = "results\plantuml_pipeline_run3"
  $sourceRunsRoot = "$resultsRoot\runs"

  if (-not (Test-Path $sourceRunsRoot)) {
    throw "Source runs folder not found: $sourceRunsRoot"
  }

  $repairArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py",
    "run",
    "--dataset-root", "dataset",
    "--results-root", $resultsRoot,
    "--repair-source-runs-root", $sourceRunsRoot,
    "--rag-docs-dir", "data\rag_corpus",
    "--rag-db-dir", "results\rag_db",
    "--skip-gpt-baseline",
    "--repair-attempts", "$RepairAttempts",
    "--runs", "$Runs",
    "--save-prompts",

    "--only-run-id", "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
    "--only-run-id", "open_source__mistral__rag_validation_generator_critic_repair",
    "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
    "--only-run-id", "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",

    "--only-run-id", "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag",
    "--only-run-id", "open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded",
    "--only-run-id", "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded",
    "--only-run-id", "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded"
  )

  if ($SkipExisting) {
    $repairArgs += "--skip-existing"
  }

  Write-Host "Running baseline repair on run3..."
  $baselineArgs = $repairArgs + @("--repair-mode", "baseline")
  python @baselineArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Run3 baseline repair failed with exit code $LASTEXITCODE."
  }

  Write-Host "Running syntax-grounded repair on run3..."
  $syntaxArgs = $repairArgs + @("--repair-mode", "syntax_grounded")
  python @syntaxArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Run3 syntax-grounded repair failed with exit code $LASTEXITCODE."
  }

  Write-Host "Recomputing fresh exact/relaxed metrics for run3 repairs..."
  & "$PSScriptRoot\run_recompute_fresh_metrics_windows.ps1" `
    -DatasetRoot "dataset" `
    -ResultsRoots @($resultsRoot) `
    -RunFolders @(
      "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
      "open_source__mistral__rag_validation_generator_critic_repair",
      "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
      "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",
      "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag",
      "open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded",
      "open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded",
      "open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded"
    ) `
    -OutputDir "results\plantuml_pipeline_run3\fresh_recomputed_metrics_repairs"

  $thresholdText = [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $Threshold)
  $relaxedThresholdText = [string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $RelaxedThreshold)
  $semanticOut = "results\plantuml_pipeline_run3\semantic_state_matching\semantic_state_matches_repairs.csv"
  $semanticOutDir = Split-Path -Parent $semanticOut
  if ($semanticOutDir -and -not (Test-Path $semanticOutDir)) {
    New-Item -ItemType Directory -Path $semanticOutDir -Force | Out-Null
  }

  Write-Host "Computing semantic state matching for run3 repairs..."
  $semanticArgs = @(
    "Code\Scripts\evaluate_semantic_state_matching.py",
    "--dataset-root", "dataset",
    "--output-csv", $semanticOut,
    "--embedding-model", $EmbeddingModel,
    "--threshold", $thresholdText,
    "--relaxed-threshold", $relaxedThresholdText,
    "--device", $Device,
    "--batch-size", "32",
    "--seed", "42",
    "--sample-count", "$SampleCount",
    "--allow-non-strict",
    "--candidate-run", "Qwen_2.5_7B|baseline_repair|$sourceRunsRoot\open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
    "--candidate-run", "Mistral|baseline_repair|$sourceRunsRoot\open_source__mistral__rag_validation_generator_critic_repair",
    "--candidate-run", "DeepSeek_R1_14B|baseline_repair|$sourceRunsRoot\open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
    "--candidate-run", "Llama_3.1_8B|baseline_repair|$sourceRunsRoot\open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",
    "--candidate-run", "Qwen_2.5_7B|syntax_grounded_repair|$sourceRunsRoot\open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag",
    "--candidate-run", "Mistral|syntax_grounded_repair|$sourceRunsRoot\open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded",
    "--candidate-run", "DeepSeek_R1_14B|syntax_grounded_repair|$sourceRunsRoot\open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded",
    "--candidate-run", "Llama_3.1_8B|syntax_grounded_repair|$sourceRunsRoot\open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded"
  )
  python @semanticArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Run3 semantic state matching for repairs failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
