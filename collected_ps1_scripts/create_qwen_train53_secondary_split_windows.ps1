param(
    [string]$DatasetRoot = "dataset",
    [string]$BaseSplit = "data\processed\experiments\split_35_seed42.json",
    [string]$Output = "data\processed\experiments\qwen_train53_split_35_seed42.json",
    [double]$TestSize = 0.35,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"

python Code\Scripts\create_secondary_split_from_rag_cases.py `
    --dataset-root $DatasetRoot `
    --base-split $BaseSplit `
    --output $Output `
    --test-size $TestSize `
    --seed $Seed
