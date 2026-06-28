param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.deepseek_fewshot_sequential_syntax_pattern.used.json",
    [string]$DeepSeek14Model = "deepseek-r1:14b",
    [int]$RepairAttempts = 8
)

$ErrorActionPreference = "Stop"

python Code\Scripts\plantuml_experiment_pipeline.py run `
    --dataset-root $DatasetRoot `
    --results-root $ResultsRoot `
    --rag-docs-dir data\empty_rag_docs `
    --rag-mode lexical `
    --split-input $SplitInput `
    --split-output $SplitOutput `
    --skip-gpt-baseline `
    --only-run-id open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__sequential_syntax_grounded_pattern_rules `
    --deepseek14-model $DeepSeek14Model `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_syntax_grounded_pattern_rules `
    --repair-ablation-tag sequential_syntax_grounded_pattern_rules `
    --save-prompts
