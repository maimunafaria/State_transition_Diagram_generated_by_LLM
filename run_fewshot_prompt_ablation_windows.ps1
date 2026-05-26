$ErrorActionPreference = "Stop"

$env:PYTHONPATH = "Code\Scripts"

$structures = @(
  "structural_validation",
  "uml_elements",
  "uml_elements_structural_validation"
)

foreach ($structure in $structures) {
  Write-Host "Running few-shot prompt structure: $structure"

  python Code\Scripts\plantuml_experiment_pipeline.py run `
    --dataset-root dataset `
    --results-root results\plantuml_pipeline `
    --skip-gpt-baseline `
    --only-run-id open_source__llama31_8b_instruct__few_shot `
    --only-run-id open_source__deepseek_r1_8b__few_shot `
    --few-shot-count 3 `
    --few-shot-prompt-structure $structure `
    --runs 3 `
    --save-prompts `
    --skip-existing
}
