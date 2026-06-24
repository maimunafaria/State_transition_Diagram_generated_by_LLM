param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$Output = "data\sft\all_llm_violation_repair_sft.jsonl",
    [ValidateSet("jsonl", "json")]
    [string]$Format = "jsonl",
    [ValidateSet("solved_violation", "full_case")]
    [string]$Granularity = "solved_violation"
)

$ErrorActionPreference = "Stop"

python Code\Scripts\build_repair_sft_dataset.py `
    --dataset-root $DatasetRoot `
    --results-root $ResultsRoot `
    --all-repair-runs `
    --output $Output `
    --format $Format `
    --granularity $Granularity
