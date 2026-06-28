param(
    [string]$InputCsv = "results\plantuml_pipeline\fresh_recomputed_metrics\per_case_fresh_metrics.csv",
    [string]$OutputCsv = "results\plantuml_pipeline\fresh_recomputed_metrics\model_stability_summary.csv",
    [ValidateSet("state_f1_exact", "state_f1_relaxed")]
    [string]$StateF1Column = "state_f1_relaxed",
    [int]$ExpectedRunCount = 3
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "Code\Scripts"

python Code\Scripts\calculate_model_stability.py `
    --input-csv $InputCsv `
    --output-csv $OutputCsv `
    --state-f1-column $StateF1Column `
    --expected-run-count $ExpectedRunCount
