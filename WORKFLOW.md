# Workflow

This is the order in which the project scripts are usually used.

## 1. Prepare Requirements

Start with raw requirement files inside the dataset case folders. The
requirement preparation script extracts the functional requirements, rewrites
them into a cleaner form, and writes the structured output back into each case
folder.

```bash
PYTHONPATH=code \
python3 code/hybrid_requirement_pipeline.py \
  --dataset-root dataset \
  --output-name structured_requirement.txt
```

This step is only needed when the structured requirement files are not already
present. As we already have them, there is no need to run it again.

## 2. Create the Split

The split file records which cases are used for testing and which are reserved
for RAG examples.

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py split \
  --dataset-root dataset \
  --output data/processed/experiments/split_35_seed42.json
```
This is already present in the data folder.

## 3. Prepare RAG Material

If the RAG example documents are missing, they can be created from the non-test
dataset cases:

```bash
PYTHONPATH=code \
python3 code/create_rag_dataset_examples.py \
  --dataset-root dataset \
  --split-file data/processed/experiments/split_35_seed42.json \
  --output-dir data/rag_corpus/dataset_examples
```

The rule and theory Markdown files are already in:


data/rag_corpus/plantuml_rules/
data/rag_corpus/state_diagram_theory/


For rag analysis runs, copy selected RAG groups into separate folders:

```bash
PYTHONPATH=code \
python3 code/create_rag_analysis_corpora.py \
  --source-root data/rag_corpus \
  --output-root data/rag_analysis
```

Build the Chroma index used during RAG prompting:

```bash
PYTHONPATH=code \
python3 code/build_rag_index.py \
  --rag-docs-dir data/rag_corpus \
  --rag-db-dir results/rag_db
```

## 4. Generate Diagrams

The main runner builds prompts, calls the configured local model, validates the
PlantUML, and applies repair when the selected method requires it.

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --runs 3 \
  --save-prompts
```

For a quick check, add `--only-case-id case_01_example --runs 1`.

### Few-shot generation

Few-shot runs are included in the full generation command above. The number of
examples is controlled with `--few-shot-count`. The default is 3.

To run only the few-shot strategy for the main models:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__few_shot \
  --only-run-id open_source__mistral__few_shot \
  --only-run-id open_source__llama31_8b_instruct__few_shot \
  --only-run-id open_source__deepseek_r1_14b__few_shot \
  --few-shot-count 3 \
  --runs 3 \
  --save-prompts
```

For one-shot runs, use the same command with `--few-shot-count 1`.

### RAG generation

RAG runs are also included in the full generation command. The Chroma index must
be built first, using the command in Step 3.

To run only the RAG strategy for the main models:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__rag \
  --only-run-id open_source__mistral__rag \
  --only-run-id open_source__llama31_8b_instruct__rag \
  --only-run-id open_source__deepseek_r1_14b__rag \
  --runs 3 \
  --save-prompts
```

## 5. Repair

Repair is part of the main generation run for repair-enabled methods. The
pipeline validates a candidate diagram, builds a repair prompt from the detected
issues, and keeps the repaired version only when the validation score improves.

To run only repair-enabled strategies, select the repair run IDs. For example,
this runs RAG with validation-based repair for the main models:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair \
  --only-run-id open_source__mistral__rag_validation_generator_critic_repair \
  --only-run-id open_source__llama31_8b_instruct__rag_validation_generator_critic_repair \
  --only-run-id open_source__deepseek_r1_14b__rag_validation_generator_critic_repair \
  --repair-attempts 3 \
  --runs 3 \
  --save-prompts
```

Repair iteration summaries can be produced later:

```bash
PYTHONPATH=code \
python3 code/build_repair_iteration_artifacts.py
```

## 6. Validity Checking

PlantUML syntax validity checks whether the diagram can be parsed/rendered by
PlantUML. Structural validity checks stricter state-diagram rules, such as
having states, transitions, an initial state, and reachable paths.

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py metrics \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline
```

```bash
PYTHONPATH=code \
python3 code/report_validity_percentages.py
```

## 7. Output

Generated files are written under:

```text
results/plantuml_pipeline/
```

This includes generated `.puml` files, prompts when enabled, metadata, and
metric summaries. 
