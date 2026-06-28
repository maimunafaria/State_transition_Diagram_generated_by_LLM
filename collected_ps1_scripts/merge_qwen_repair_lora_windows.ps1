param(
    [Parameter(Mandatory = $true)]
    [string]$LlamaFactoryDir,
    [string]$PreparedDir = "finetune\llamafactory\plantuml_repair"
)

$ErrorActionPreference = "Stop"

$PreparedConfigs = Join-Path $PreparedDir "configs"
if (-not (Test-Path $LlamaFactoryDir)) {
    throw "LLaMA-Factory folder not found: $LlamaFactoryDir"
}

$LfConfigs = Join-Path $LlamaFactoryDir "plantuml_repair_configs"
New-Item -ItemType Directory -Force -Path $LfConfigs | Out-Null
Copy-Item (Join-Path $PreparedConfigs "*.yaml") $LfConfigs -Force

Push-Location $LlamaFactoryDir
try {
    llamafactory-cli export plantuml_repair_configs\merge_qwen25_7b_plantuml_repair_lora.yaml
}
finally {
    Pop-Location
}
