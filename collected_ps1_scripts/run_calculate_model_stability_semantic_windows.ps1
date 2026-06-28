param(
    [string]$Run1Csv = "results\plantuml_pipeline\semantic_state_matching\semantic_state_matches_324.csv",
    [string]$Run2Csv = "results\plantuml_pipeline_run2\semantic_state_matching\semantic_state_matches_324.csv",
    [string]$Run3Csv = "results\plantuml_pipeline_run3\semantic_state_matching\semantic_state_matches_324.csv",
    [string]$OutputCsv = "results\plantuml_pipeline\semantic_state_matching\model_stability_summary_semantic.csv",
    [int]$ExpectedRunCount = 3,
    [ValidateSet("llm", "llm_method")]
    [string]$GroupBy = "llm"
)

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "Code\Scripts"

python Code\Scripts\calculate_model_stability_semantic.py `
    --input-set "run1=$Run1Csv" `
    --input-set "run2=$Run2Csv" `
    --input-set "run3=$Run3Csv" `
    --output-csv $OutputCsv `
    --expected-run-count $ExpectedRunCount `
    --group-by $GroupBy
