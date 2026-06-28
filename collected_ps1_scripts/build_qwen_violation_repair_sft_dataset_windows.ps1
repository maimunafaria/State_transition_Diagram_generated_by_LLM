param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$Output = "data\sft\qwen_violation_repair_sft.jsonl",
    [ValidateSet("jsonl", "json")]
    [string]$Format = "jsonl",
    [ValidateSet("solved_violation", "full_case")]
    [string]$Granularity = "solved_violation"
)

$ErrorActionPreference = "Stop"

$RunIds = @(
    "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair",
    "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__syntax_grounded",
    "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__syntax_grounded_pattern_rules",
    "open_source__qwen25_7b_instruct__chain_of_thought_validation_generator_critic_repair__hybrid_issue_guided",
    "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair",
    "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded",
    "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_pattern_rules",
    "open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__hybrid_issue_guided"
)

$ArgsList = @(
    "Code\Scripts\build_repair_sft_dataset.py",
    "--dataset-root", $DatasetRoot,
    "--results-root", $ResultsRoot,
    "--output", $Output,
    "--format", $Format,
    "--granularity", $Granularity
)

foreach ($RunId in $RunIds) {
    $RunPath = Join-Path $ResultsRoot "runs\$RunId"
    if (Test-Path $RunPath) {
        $ArgsList += @("--run-id", $RunId)
    } else {
        Write-Host "Skipping missing run: $RunId"
    }
}

python @ArgsList
