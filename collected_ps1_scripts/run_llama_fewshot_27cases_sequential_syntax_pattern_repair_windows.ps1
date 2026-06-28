param(
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "data\processed\experiments\split_35_seed42.llama_fewshot_sequential_syntax_pattern.used.json",
    [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
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
    --only-run-id open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__sequential_syntax_grounded_pattern_rules `
    --llama-model $LlamaModel `
    --runs 1 `
    --repair-attempts $RepairAttempts `
    --repair-mode sequential_syntax_grounded_pattern_rules `
    --repair-ablation-tag sequential_syntax_grounded_pattern_rules `
    --save-prompts
