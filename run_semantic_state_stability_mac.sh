#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="Code/Scripts"

python3 -c "import numpy, scipy, sentence_transformers, torch" >/dev/null

OUTPUT_DIR="results/semantic_state_stability"
mkdir -p "$OUTPUT_DIR"

run_semantic_set() {
  local run_label="$1"
  local runs_root="$2"
  local output_csv="$OUTPUT_DIR/${run_label}_semantic_state_matches.csv"

  python3 Code/Scripts/evaluate_semantic_state_matching.py \
    --dataset-root dataset \
    --output-csv "$output_csv" \
    --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
    --threshold 0.80 \
    --relaxed-threshold 0.48 \
    --device cpu \
    --batch-size 32 \
    --seed 42 \
    --sample-count 0 \
    --allow-non-strict \
    --candidate-run "Qwen_2.5_7B|rag|$runs_root/open_source__qwen25_7b_instruct__rag" \
    --candidate-run "Qwen_2.5_7B|baseline_repair|$runs_root/open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair" \
    --candidate-run "Mistral|rag|$runs_root/open_source__mistral__rag" \
    --candidate-run "Mistral|baseline_repair|$runs_root/open_source__mistral__rag_validation_generator_critic_repair" \
    --candidate-run "DeepSeek_R1_14B|few_shot|$runs_root/open_source__deepseek_r1_14b__few_shot" \
    --candidate-run "DeepSeek_R1_14B|baseline_repair|$runs_root/open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair" \
    --candidate-run "Llama_3.1_8B|few_shot|$runs_root/open_source__llama31_8b_instruct__few_shot" \
    --candidate-run "Llama_3.1_8B|baseline_repair|$runs_root/open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair"

  python3 Code/Scripts/summarize_semantic_state_f1.py \
    --input-csv "$output_csv" \
    --output-csv "$OUTPUT_DIR/${run_label}_semantic_state_summary.csv"
}

run_semantic_set "run1" "final_results/runs"
run_semantic_set "run2" "results/plantuml_pipeline_run2/runs"
run_semantic_set "run3" "results/plantuml_pipeline_run3/runs"

python3 Code/Scripts/calculate_model_stability_semantic.py \
  --input-set "run1=$OUTPUT_DIR/run1_semantic_state_matches.csv" \
  --input-set "run2=$OUTPUT_DIR/run2_semantic_state_matches.csv" \
  --input-set "run3=$OUTPUT_DIR/run3_semantic_state_matches.csv" \
  --output-csv "$OUTPUT_DIR/model_stability_summary.csv" \
  --expected-run-count 3 \
  --group-by llm_method
