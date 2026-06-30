param(
  [string]$OutputPath = "final_results\environment\windows_environment.txt",
  [string]$PlantUmlJar = "$HOME\tools\plantuml.jar"
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Models = @(
  "qwen2.5:7b-instruct",
  "mistral:7b-instruct",
  "deepseek-r1:14b",
  "llama3.1:8b-instruct-q4_K_M",
  "ggozad/prometheus2"
)

Push-Location $ProjectRoot
try {
  $OutputFile = Join-Path $ProjectRoot $OutputPath
  New-Item -ItemType Directory -Force (Split-Path -Parent $OutputFile) | Out-Null

  & {
    Write-Output "EXPERIMENT ENVIRONMENT REPORT"
    Write-Output "Generated: $(Get-Date -Format o)"

    Write-Output "`n=== OPERATING SYSTEM ==="
    Get-CimInstance Win32_OperatingSystem |
      Select-Object Caption, Version, BuildNumber, OSArchitecture |
      Format-List

    Write-Output "`n=== CPU ==="
    Get-CimInstance Win32_Processor |
      Select-Object Name, NumberOfCores, NumberOfLogicalProcessors |
      Format-List

    Write-Output "`n=== RAM ==="
    $Computer = Get-CimInstance Win32_ComputerSystem
    [pscustomobject]@{
      TotalPhysicalMemoryBytes = [int64]$Computer.TotalPhysicalMemory
      TotalPhysicalMemoryGiB = [math]::Round(
        [double]$Computer.TotalPhysicalMemory / 1GB,
        2
      )
    } | Format-List

    Write-Output "`n=== GPU (WINDOWS) ==="
    Get-CimInstance Win32_VideoController |
      Select-Object Name, DriverVersion, AdapterRAM |
      Format-List

    Write-Output "`n=== NVIDIA GPU / VRAM (IF AVAILABLE) ==="
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
      nvidia-smi --query-gpu=name,memory.total,driver_version `
        --format=csv,noheader
    }
    else {
      Write-Output "nvidia-smi not found."
    }

    Write-Output "`n=== PYTHON ==="
    python --version 2>&1

    Write-Output "`n=== JAVA ==="
    java -version 2>&1

    Write-Output "`n=== PLANTUML ==="
    if (Test-Path $PlantUmlJar) {
      Write-Output "JAR: $PlantUmlJar"
      java -jar $PlantUmlJar -version 2>&1
    }
    elseif (Get-Command plantuml -ErrorAction SilentlyContinue) {
      plantuml -version 2>&1
    }
    else {
      Write-Output "PlantUML executable/JAR not found."
    }

    Write-Output "`n=== OLLAMA ==="
    ollama --version 2>&1
    ollama list 2>&1

    Write-Output "`n=== OLLAMA MODEL DETAILS ==="
    foreach ($Model in $Models) {
      Write-Output "`n--- $Model ---"
      ollama show $Model 2>&1
    }

    Write-Output "`n=== OLLAMA FULL TAG DIGESTS ==="
    try {
      $Tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags"
      $Tags.models |
        Where-Object { $_.name -in $Models } |
        Select-Object name, digest, size, modified_at, details |
        ConvertTo-Json -Depth 6
    }
    catch {
      Write-Output "Could not query Ollama tags API: $($_.Exception.Message)"
    }

    Write-Output "`n=== EMBEDDING SOFTWARE ==="
    python -c "import sentence_transformers, transformers, torch, scipy, sklearn; print('sentence-transformers', sentence_transformers.__version__); print('transformers', transformers.__version__); print('torch', torch.__version__); print('scipy', scipy.__version__); print('scikit-learn', sklearn.__version__)" 2>&1
  } 2>&1 | Out-File -FilePath $OutputFile -Encoding utf8

  Write-Host "Environment report saved to: $OutputFile"
}
finally {
  Pop-Location
}
