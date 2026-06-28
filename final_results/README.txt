This folder contains the selected final run folders copied from:
results/plantuml_pipeline/runs

Included models:
- DeepSeek R1 14B
- Llama 3.1 8B Instruct
- Qwen 2.5 7B Instruct
- Mistral

Included methods per model:
- zero_shot
- one_shot
- few_shot
- rag
- baseline_repair
- syntax_guided_no_rules

Notes:
- For DeepSeek, syntax-guided without structural validation rules comes from:
  open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded_no_rules
- For Qwen, Llama, and Mistral, the copied syntax-guided folder is the variant whose prompt contains
  Valid PlantUML repair patterns but does not contain the Structural Validation Rules section.
- Original run folder names are preserved inside final_results/runs.
