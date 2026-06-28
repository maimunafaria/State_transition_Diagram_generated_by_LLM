param(
  [int]$Runs = 1,
  [int]$RepairAttempts = 5,
  [switch]$SkipExisting
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "Code\Scripts"

$commonArgs = @(
  "Code\Scripts\plantuml_experiment_pipeline.py",
  "run",
  "--dataset-root", "dataset",
  "--results-root", "results\plantuml_pipeline",
  "--rag-docs-dir", "data\rag_corpus",
  "--rag-db-dir", "results\rag_db",
  "--skip-gpt-baseline",
  "--repair-attempts", "$RepairAttempts",
  "--runs", "$Runs",
  "--save-prompts"
)

if ($SkipExisting) {
  $commonArgs += "--skip-existing"
}

Write-Host "Running Qwen and Gemma CoT Syntax-Grounded repair..."
$syntaxGroundedArgs = $commonArgs + @(
  "--repair-mode", "syntax_grounded",
  "--repair-ablation-tag", "syntax_grounded",
  "--only-run-id", "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__syntax_grounded",
  "--only-run-id", "open_source__gemma3_12b__chain_of_thought_validation_generator_critic_repair__syntax_grounded"
)
python @syntaxGroundedArgs

Write-Host "Running Qwen and Gemma CoT Syntax-Grounded + Pattern Rules repair..."
$patternRulesArgs = $commonArgs + @(
  "--repair-mode", "syntax_grounded_pattern_rules",
  "--repair-ablation-tag", "syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__syntax_grounded_pattern_rules",
  "--only-run-id", "open_source__gemma3_12b__chain_of_thought_validation_generator_critic_repair__syntax_grounded_pattern_rules"
)
python @patternRulesArgs

Write-Host "Completed both CoT repair variants for Qwen and Gemma."
