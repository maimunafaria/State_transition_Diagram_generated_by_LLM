param(
    [string]$DatasetRoot = "dataset",
    [string[]]$ResultsRoots = @(
        "results\plantuml_pipeline"
    ),
    [string[]]$RunFolders = @(),
    [string]$OutputDir = "results\plantuml_pipeline\fresh_recomputed_metrics"
)

$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$argsList = @(
    "Code\Scripts\recompute_run_metrics_fresh.py",
    "--dataset-root", $DatasetRoot,
    "--output-dir", $OutputDir
)

foreach ($resultsRoot in $ResultsRoots) {
    $argsList += @("--results-root", $resultsRoot)
}

foreach ($runFolder in $RunFolders) {
    $argsList += @("--run-folder", $runFolder)
}

python @argsList

