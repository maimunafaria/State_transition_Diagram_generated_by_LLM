#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

export PYTHONPATH="Code/Scripts"

python3 -c "import numpy, scipy, sentence_transformers, torch" >/dev/null

RUNS_ROOT="final_results/runs"
OUTPUT_DIR="final_results/semantic_state_matching"
DETAIL_CSV="$OUTPUT_DIR/semantic_state_matches_324.csv"
SUMMARY_CSV="$OUTPUT_DIR/semantic_state_summary.csv"

mkdir -p "$OUTPUT_DIR"

python3 Code/Scripts/evaluate_semantic_state_matching.py \
  --dataset-root dataset \
  --output-csv "$DETAIL_CSV" \
  --embedding-model sentence-transformers/all-MiniLM-L6-v2 \
  --threshold 0.80 \
  --relaxed-threshold 0.48 \
  --device cpu \
  --batch-size 32 \
  --seed 42 \
  --sample-count 5 \
  --allow-non-strict \
  --candidate-run "Qwen_2.5_7B|rag|$RUNS_ROOT/open_source__qwen25_7b_instruct__rag" \
  --candidate-run "Qwen_2.5_7B|baseline_repair|$RUNS_ROOT/open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair" \
  --candidate-run "Qwen_2.5_7B|syntax_grounded_repair|$RUNS_ROOT/open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair__syntax_grounded_no_rules_original_rag" \
  --candidate-run "Mistral|rag|$RUNS_ROOT/open_source__mistral__rag" \
  --candidate-run "Mistral|baseline_repair|$RUNS_ROOT/open_source__mistral__rag_validation_generator_critic_repair" \
  --candidate-run "Mistral|syntax_grounded_repair|$RUNS_ROOT/open_source__mistral__rag_validation_generator_critic_repair__syntax_grounded" \
  --candidate-run "DeepSeek_R1_14B|few_shot|$RUNS_ROOT/open_source__deepseek_r1_14b__few_shot" \
  --candidate-run "DeepSeek_R1_14B|baseline_repair|$RUNS_ROOT/open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair" \
  --candidate-run "DeepSeek_R1_14B|syntax_grounded_repair|$RUNS_ROOT/open_source__deepseek_r1_14b__few_shot_validation_generator_critic_repair__syntax_grounded_no_rules" \
  --candidate-run "Llama_3.1_8B|few_shot|$RUNS_ROOT/open_source__llama31_8b_instruct__few_shot" \
  --candidate-run "Llama_3.1_8B|baseline_repair|$RUNS_ROOT/open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair" \
  --candidate-run "Llama_3.1_8B|syntax_grounded_repair|$RUNS_ROOT/open_source__llama31_8b_instruct__few_shot_validation_generator_critic_repair__syntax_grounded"

python3 Code/Scripts/summarize_semantic_state_f1.py \
  --input-csv "$DETAIL_CSV" \
  --output-csv "$SUMMARY_CSV"
