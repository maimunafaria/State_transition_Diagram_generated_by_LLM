param(
    [string]$InputPath = "data\sft\all_llm_violation_repair_sft.jsonl",
    [string]$OutputPath = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$ReportPath = "data\sft\all_llm_violation_repair_sft.cleaned.report.json",
    [int]$MinOutputChars = 150
)

$ErrorActionPreference = "Stop"

python Code\Scripts\clean_repair_sft_dataset.py `
    --input $InputPath `
    --output $OutputPath `
    --report $ReportPath `
    --min-output-chars $MinOutputChars
