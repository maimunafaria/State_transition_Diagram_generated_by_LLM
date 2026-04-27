# State_transition_Diagram_generated_by_LLM

Generate UML state machine diagrams in PlantUML from structured natural-language requirements using zero-shot, few-shot, and RAG-based LLM prompts.

## Active Project Layout

```text
Code/Scripts/plantuml_experiment_pipeline.py   # main CLI entrypoint
Code/Scripts/plantuml_pipeline/                # active pipeline package
Code/Scripts/build_rag_index.py                # optional vector RAG index builder
Code/Scripts/render_puml_batch.py              # optional PlantUML image renderer
dataset/                                      # case folders used by experiments
data/raw/rag_docs/                            # RAG reference documents
data/processed/experiments/split_35_seed42.json
data/processed/dataset/diagram_requirements_catalog.csv
results/plantuml_pipeline/                    # current generated outputs and metrics
results/rag_db/                               # optional persisted vector RAG index
```

## Main Commands

Show CLI help:

```bash
python3 Code/Scripts/plantuml_experiment_pipeline.py --help
```

Run zero-shot:

```bash
python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__zero_shot \
  --only-run-id open_source__qwen25_7b_instruct__zero_shot \
  --only-run-id open_source__deepseek_r1_14b__zero_shot \
  --runs 1 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --save-prompts
```

Run few-shot:

```bash
python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__few_shot \
  --only-run-id open_source__qwen25_7b_instruct__few_shot \
  --only-run-id open_source__deepseek_r1_14b__few_shot \
  --runs 1 \
  --test-size 0.35 \
  --seed 42 \
  --few-shot-seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --save-prompts
```

Render generated `.puml` files to PNG:

```bash
find results/plantuml_pipeline/runs \( -path "*zero_shot*" -o -path "*few_shot*" \) -name "*.puml" -exec plantuml -tpng {} \;
```

Recompute metrics:

```bash
python3 Code/Scripts/plantuml_experiment_pipeline.py metrics \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline
```

Run a gold-free stacked ensemble from an explicit candidate pool:

```bash
python3 Code/Scripts/plantuml_experiment_pipeline.py ensemble \
  --ensemble-method stacked_llm \
  --ensemble-root ensemble_gold_free_stacked \
  --stack-max-candidates 3 \
  --stack-fallback-majority \
  --candidate-run-id open_source__llama31_8b_instruct__zero_shot \
  --candidate-run-id open_source__llama31_8b_instruct__few_shot \
  --candidate-run-id open_source__llama31_8b_instruct__rag \
  --candidate-run-id open_source__llama31_8b_instruct__rag_validation_generator_critic_repair \
  --candidate-run-id open_source__qwen25_7b_instruct__zero_shot \
  --candidate-run-id open_source__qwen25_7b_instruct__few_shot \
  --candidate-run-id open_source__qwen25_7b_instruct__rag \
  --candidate-run-id open_source__deepseek_r1_14b__zero_shot \
  --candidate-run-id open_source__deepseek_r1_14b__few_shot \
  --candidate-run-id open_source__deepseek_r1_14b__rag
```

## Notes

- Requirements are loaded from each case's `structured_requirement.txt`.
- Few-shot examples are selected from the train/RAG split, not from test cases.
- Generated prompts are saved as `run_XX.prompt.txt` when `--save-prompts` is used.
- Generated PlantUML is saved as `run_XX.puml`.
- Stacked ensemble candidate selection is gold-free by default: it ranks candidates using
  structural validity, requirement coverage, candidate consensus, and diagram quality.
