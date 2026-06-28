param(
    [ValidateSet("qwen_rag", "mistral_rag", "deepseek_fewshot", "llama_fewshot")]
    [string]$Profile,
    [string]$DatasetRoot = "dataset",
    [string]$ResultsRoot = "results\plantuml_pipeline",
    [string]$SplitInput = "data\processed\experiments\split_35_seed42.json",
    [string]$SplitOutput = "",
    [string]$QwenModel = "qwen2.5:7b-instruct",
    [string]$MistralModel = "mistral:7b-instruct",
    [string]$DeepSeek14Model = "deepseek-r1:14b",
    [string]$LlamaModel = "llama3.1:8b-instruct-q4_K_M",
    [int]$Seed = 42,
    [int]$FewShotSeed = 42,
    [int]$Runs = 1
)

$ErrorActionPreference = "Stop"

$config = @{
    qwen_rag = @{
        RunId = "open_source__qwen25_7b_instruct__rag"
        SplitSuffix = "qwen_rag"
        Args = @("--skip-gpt-baseline", "--use-case-rag", "--rag-mode", "lexical", "--only-run-id", "open_source__qwen25_7b_instruct__rag")
        ModelArgs = @("--qwen-model", $QwenModel)
        NeedsFewShotSeed = $false
    }
    mistral_rag = @{
        RunId = "open_source__mistral__rag"
        SplitSuffix = "mistral_rag"
        Args = @("--skip-gpt-baseline", "--use-case-rag", "--rag-mode", "lexical", "--only-run-id", "open_source__mistral__rag")
        ModelArgs = @("--mistral-model", $MistralModel)
        NeedsFewShotSeed = $false
    }
    deepseek_fewshot = @{
        RunId = "open_source__deepseek_r1_14b__few_shot"
        SplitSuffix = "deepseek_fewshot"
        Args = @("--skip-gpt-baseline", "--only-run-id", "open_source__deepseek_r1_14b__few_shot")
        ModelArgs = @("--deepseek14-model", $DeepSeek14Model)
        NeedsFewShotSeed = $true
    }
    llama_fewshot = @{
        RunId = "open_source__llama31_8b_instruct__few_shot"
        SplitSuffix = "llama_fewshot"
        Args = @("--skip-gpt-baseline", "--only-run-id", "open_source__llama31_8b_instruct__few_shot")
        ModelArgs = @("--llama-model", $LlamaModel)
        NeedsFewShotSeed = $true
    }
}

if (-not $config.ContainsKey($Profile)) {
    throw "Unknown profile: $Profile"
}

$selected = $config[$Profile]
if (-not $SplitOutput) {
    $SplitOutput = "data\processed\experiments\split_35_seed42.$($selected.SplitSuffix).run$Seed.used.json"
}

$cmdArgs = @(
    "Code\Scripts\plantuml_experiment_pipeline.py",
    "run",
    "--dataset-root", $DatasetRoot,
    "--results-root", $ResultsRoot,
    "--rag-docs-dir", "data\empty_rag_docs",
    "--split-input", $SplitInput,
    "--split-output", $SplitOutput,
    "--seed", $Seed,
    "--runs", $Runs,
    "--save-prompts"
)

$cmdArgs += $selected.Args
$cmdArgs += $selected.ModelArgs
if ($selected.NeedsFewShotSeed) {
    $cmdArgs += @("--few-shot-seed", $FewShotSeed)
}

& python @cmdArgs
