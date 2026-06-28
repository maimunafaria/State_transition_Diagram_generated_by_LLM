param(
  [string]$EmbeddingModel = "sentence-transformers/all-MiniLM-L6-v2",
  [double]$Threshold = 0.80,
  [double]$RelaxedThreshold = 0.50,
  [string]$Device = "cpu",
  [int]$SampleCount = 5,
  [string]$SourceRunsRoot = "Code\untitled folder\results\plantuml_pipeline\runs",
  [string]$OutputCsv = "results\plantuml_pipeline\semantic_state_matching\semantic_state_matches_324.csv"
)

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
  $env:PYTHONPATH = "Code\Scripts"
  python -c "import numpy, scipy, sentence_transformers, torch"
  if ($LASTEXITCODE -ne 0) {
    throw "Missing dependencies. Run: pip install sentence-transformers scipy"
  }

  $thresholdText = [string]::Format(
    [Globalization.CultureInfo]::InvariantCulture,
    "{0}",
    $Threshold
  )
  $relaxedThresholdText = [string]::Format(
    [Globalization.CultureInfo]::InvariantCulture,
    "{0}",
    $RelaxedThreshold
  )
  $commandArgs = @(
    "Code\Scripts\evaluate_semantic_state_matching.py",
    "--dataset-root", "dataset",
    "--output-csv", $OutputCsv,
    "--embedding-model", $EmbeddingModel,
    "--threshold", $thresholdText,
    "--relaxed-threshold", $relaxedThresholdText,
    "--device", $Device,
    "--batch-size", "32",
    "--seed", "42",
    "--sample-count", "$SampleCount",
    "--allow-non-strict",

    "--candidate-run", "Qwen_2.5_7B|rag|$SourceRunsRoot\open_source__qwen25_7b_instruct__rag",
    "--candidate-run", "Qwen_2.5_7B|baseline_repair|$SourceRunsRoot\open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
    "--candidate-run", "Qwen_2.5_7B|syntax_grounded_repair|$SourceRunsRoot\open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_original_rag",

    "--candidate-run", "Mistral|rag|$SourceRunsRoot\open_source__mistral__rag",
    "--candidate-run", "Mistral|baseline_repair|$SourceRunsRoot\open_source__mistral__rag_validation_generator_critic_repair",
    "--candidate-run", "Mistral|syntax_grounded_repair|$SourceRunsRoot\open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded",

    "--candidate-run", "DeepSeek_R1_14B|few_shot|$SourceRunsRoot\open_source__deepseek_r1_14b__few_shot",
    "--candidate-run", "DeepSeek_R1_14B|baseline_repair|$SourceRunsRoot\open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair",
    "--candidate-run", "DeepSeek_R1_14B|syntax_grounded_repair|$SourceRunsRoot\open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded",

    "--candidate-run", "Llama_3.1_8B|few_shot|$SourceRunsRoot\open_source__llama31_8b_instruct__few_shot",
    "--candidate-run", "Llama_3.1_8B|baseline_repair|$SourceRunsRoot\open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair",
    "--candidate-run", "Llama_3.1_8B|syntax_grounded_repair|$SourceRunsRoot\open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded"
  )

  Write-Host "Running semantic state matching for 27 cases x 4 LLMs x 3 methods..."
  Write-Host "Methods: raw selected method, baseline repair, syntax-grounded repair"
  Write-Host "Embedding model: $EmbeddingModel"
  Write-Host "Similarity threshold: $Threshold"
  Write-Host "Relaxed threshold: $RelaxedThreshold"
  python @commandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Semantic state matching failed with exit code $LASTEXITCODE."
  }
}
finally {
  Pop-Location
}
