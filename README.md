# State Transition Diagram Generation by LLM

This project explores how well local LLMs can turn structured natural-language requirements into UML state transition diagrams. The generated diagrams are written in PlantUML, and the pipeline supports zero-shot, one-shot, few-shot, RAG, RAG with validation and repair, and stacked ensemble experiments.

## Project Layout

Code/Scripts/plantuml_experiment_pipeline.py   # main CLI entrypoint
Code/Scripts/plantuml_pipeline/                # active pipeline package
Code/Scripts/build_rag_index.py                # builds vector RAG index
Code/Scripts/create_rag_dataset_examples.py    # converts train cases into RAG docs
Code/Scripts/report_validity_percentages.py    # validity summary CSV/table generator
Code/Scripts/render_puml_batch.py              # optional PlantUML renderer

dataset/                                      # case folders with requirements and gold diagrams
data/rag_corpus/                              # RAG markdown corpus
data/processed/experiments/split_35_seed42.json
results/rag_db/                               # persisted vector RAG index
results/plantuml_pipeline/runs/               # generated diagrams
results/plantuml_pipeline/metrics/            # generated metrics and validity CSVs


## Models Used

The current open-source setup uses these Ollama models:

Llama 3.1 8B:     llama3.1:8b-instruct-q4_K_M
Qwen 2.5 7B:      qwen2.5:7b-instruct
DeepSeek R1 14B:  deepseek-r1:14b


If you do not already have them locally, pull them with Ollama:


ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct
ollama pull deepseek-r1:14b


## Data Split

For reproducibility, the experiments use the same fixed split:


35% test cases
65% train/RAG cases
seed = 42
split file = data/processed/experiments/split_35_seed42.json


By default, the prompt is built from `structured_requirement.txt`.

## RAG Setup

The RAG corpus lives here:


data/rag_corpus/


Build or rebuild the vector index with:


python3 Code/Scripts/build_rag_index.py


The generated vector database is saved here:


results/rag_db/


## Run Experiments

### Zero-Shot


python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --only-run-id open_source__llama31_8b_instruct__zero_shot \
  --only-run-id open_source__qwen25_7b_instruct__zero_shot \
  --only-run-id open_source__deepseek_r1_14b__zero_shot \
  --llama-model llama3.1:8b-instruct-q4_K_M \
  --qwen-model qwen2.5:7b-instruct \
  --deepseek14-model deepseek-r1:14b \
  --runs 1 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --save-prompts


### One-Shot

One-shot uses the same few-shot code path, but with only one example:


python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__one_shot \
  --only-run-id open_source__qwen25_7b_instruct__one_shot \
  --only-run-id open_source__deepseek_r1_14b__one_shot \
  --llama-model llama3.1:8b-instruct-q4_K_M \
  --qwen-model qwen2.5:7b-instruct \
  --deepseek14-model deepseek-r1:14b \
  --runs 1 \
  --few-shot-count 1 \
  --few-shot-seed 42 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --save-prompts


### Few-Shot

Few-shot uses three examples by default:


python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__few_shot \
  --only-run-id open_source__qwen25_7b_instruct__few_shot \
  --only-run-id open_source__deepseek_r1_14b__few_shot \
  --llama-model llama3.1:8b-instruct-q4_K_M \
  --qwen-model qwen2.5:7b-instruct \
  --deepseek14-model deepseek-r1:14b \
  --runs 1 \
  --few-shot-count 3 \
  --few-shot-seed 42 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --save-prompts


### RAG


python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__rag \
  --only-run-id open_source__qwen25_7b_instruct__rag \
  --only-run-id open_source__deepseek_r1_14b__rag \
  --llama-model llama3.1:8b-instruct-q4_K_M \
  --qwen-model qwen2.5:7b-instruct \
  --deepseek14-model deepseek-r1:14b \
  --runs 1 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --rag-mode vector \
  --top-k-rag 3 \
  --rag-max-chars-per-doc 1200 \
  --save-prompts


### RAG + Validation Repair

This mode first generates a diagram, validates it, and then asks the model to repair it using the reported validation issues and targeted guidance. The final `run_XX.puml` keeps the best accepted version, while each repair attempt is saved separately so it can be inspected later.


python3 Code/Scripts/plantuml_experiment_pipeline.py run \
  --skip-gpt-baseline \
  --only-run-id open_source__llama31_8b_instruct__rag_validation_generator_critic_repair \
  --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair \
  --only-run-id open_source__deepseek_r1_14b__rag_validation_generator_critic_repair \
  --llama-model llama3.1:8b-instruct-q4_K_M \
  --qwen-model qwen2.5:7b-instruct \
  --deepseek14-model deepseek-r1:14b \
  --runs 1 \
  --repair-attempts 5 \
  --test-size 0.35 \
  --seed 42 \
  --split-output data/processed/experiments/split_35_seed42.json \
  --rag-mode vector \
  --top-k-rag 3 \
  --rag-max-chars-per-doc 1200 \
  --save-prompts


A repair run saves files in this shape:


run_01.prompt.txt
run_01.initial.puml
run_01.repair_01.prompt.txt
run_01.repair_01.puml
...
run_01.repair_05.prompt.txt
run_01.repair_05.puml
run_01.puml
run_01.meta.json


## Windows Command Example

On Windows, use `python` instead of `python3`:


python Code/Scripts/plantuml_experiment_pipeline.py run --skip-gpt-baseline --only-run-id open_source__llama31_8b_instruct__rag_validation_generator_critic_repair --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair --only-run-id open_source__deepseek_r1_14b__rag_validation_generator_critic_repair --llama-model llama3.1:8b-instruct-q4_K_M --qwen-model qwen2.5:7b-instruct --deepseek14-model deepseek-r1:14b --runs 1 --repair-attempts 5 --test-size 0.35 --seed 42 --split-output data/processed/experiments/split_35_seed42.json --rag-mode vector --top-k-rag 3 --rag-max-chars-per-doc 1200 --save-prompts

## Render PNG Diagrams

To render the final diagrams for all one-shot and RAG + repair outputs:


find results/plantuml_pipeline/runs -type f \( -path '*__one_shot/*' -o -path '*__rag_validation_generator_critic_repair/*' \) -name 'run_[0-9][0-9].puml' -exec plantuml -tpng {} \;


To render every `.puml`, including intermediate repair attempts:


find results/plantuml_pipeline/runs -type f \( -path '*__one_shot/*' -o -path '*__rag_validation_generator_critic_repair/*' \) -name '*.puml' -exec plantuml -tpng {} \;


## Validity Tables

Generate the PlantUML syntax validity table and the stricter UML state-rule validity table with:


python3 Code/Scripts/report_validity_percentages.py


CSV outputs:


results/plantuml_pipeline/metrics/validity_by_model_method.csv
results/plantuml_pipeline/metrics/state_rules_validity_by_model_method.csv
results/plantuml_pipeline/metrics/plantuml_validity_cases.csv
results/plantuml_pipeline/metrics/state_rules_validity_cases.csv
results/plantuml_pipeline/metrics/invalid_validity_cases.csv
results/plantuml_pipeline/metrics/invalid_state_rules_cases.csv


The two validity checks mean:


PlantUML render/syntax validity: PlantUML can parse and render the diagram.
Strict UML state-rule validity: PlantUML is valid, and no parser warnings or state-rule violations remain.


## Stacked Ensemble

The stacked ensemble combines candidate diagrams from Qwen, LLaMA, and DeepSeek. It selects candidates using gold-free scores, then asks a stack model to produce one final PlantUML diagram.

Run the stacked ensemble for all five methods:


python3 Code/Scripts/plantuml_experiment_pipeline.py ensemble \
  --ensemble-method stacked_llm \
  --stack-model llama3.1:8b-instruct-q4_K_M \
  --stack-use-rag \
  --stack-rag-mode vector \
  --stack-top-k-rag 3 \
  --stack-rag-max-chars-per-doc 1200 \
  --stack-max-candidates 6 \
  --stack-fallback-majority


Output:


results/plantuml_pipeline/ensemble_stacked_llm/runs/<ensemble_run_id>/<case_id>/ensemble.puml
results/plantuml_pipeline/ensemble_stacked_llm/runs/<ensemble_run_id>/<case_id>/ensemble.meta.json
results/plantuml_pipeline/ensemble_stacked_llm/metrics/


A majority-vote ensemble is also available:


python3 Code/Scripts/plantuml_experiment_pipeline.py ensemble \
  --ensemble-method majority_vote


## Useful Notes

- Few-shot examples come from the train/RAG split, not from test cases.
- `--few-shot-count 1` produces one-shot outputs and uses `__one_shot` run IDs.
- `--runs N` means N independent generations per case.
- `--repair-attempts N` means up to N repair attempts inside each repair-enabled run.
- `--save-prompts` writes generation and repair prompts beside the `.puml` outputs.
- The `.puml` normalizer removes markdown code fences from model output.
