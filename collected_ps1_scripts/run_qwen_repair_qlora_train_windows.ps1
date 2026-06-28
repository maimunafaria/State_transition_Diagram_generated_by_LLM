param(
    [Parameter(Mandatory = $true)]
    [string]$LlamaFactoryDir,
    [string]$PreparedDir = "finetune\llamafactory\plantuml_repair"
)

$ErrorActionPreference = "Stop"

$PreparedData = Join-Path $PreparedDir "data"
$PreparedConfigs = Join-Path $PreparedDir "configs"

if (-not (Test-Path $LlamaFactoryDir)) {
    throw "LLaMA-Factory folder not found: $LlamaFactoryDir"
}
if (-not (Test-Path $PreparedData)) {
    throw "Prepared data folder not found. Run .\prepare_llamafactory_repair_sft_windows.ps1 first."
}

$LfData = Join-Path $LlamaFactoryDir "data"
$LfConfigs = Join-Path $LlamaFactoryDir "plantuml_repair_configs"
New-Item -ItemType Directory -Force -Path $LfData | Out-Null
New-Item -ItemType Directory -Force -Path $LfConfigs | Out-Null

Copy-Item (Join-Path $PreparedData "plantuml_repair_train.json") $LfData -Force
Copy-Item (Join-Path $PreparedData "plantuml_repair_eval.json") $LfData -Force
Copy-Item (Join-Path $PreparedData "dataset_info.json") $LfData -Force
Copy-Item (Join-Path $PreparedConfigs "*.yaml") $LfConfigs -Force

Push-Location $LlamaFactoryDir
try {
    llamafactory-cli train plantuml_repair_configs\qwen25_7b_plantuml_repair_qlora_sft.yaml
}
finally {
    Pop-Location
}
