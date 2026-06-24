param(
    [string]$InputPath = "data\sft\all_llm_violation_repair_sft.cleaned.jsonl",
    [string]$OutputDir = "finetune\llamafactory\plantuml_repair",
    [double]$EvalRatio = 0.1,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"

python Code\Scripts\prepare_llamafactory_repair_sft.py `
    --input $InputPath `
    --output-dir $OutputDir `
    --eval-ratio $EvalRatio `
    --seed $Seed
