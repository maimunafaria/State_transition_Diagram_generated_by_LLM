# UML State Diagram Generation Pipeline

This folder contains the code used to prepare requirement files, generate
PlantUML state diagrams, run validation-based repair, and report syntax and
structural validity.

The code folder is expected to be named `code` in the repository. The examples
below use that name.

## Folder Layout

The repository should contain these folders:

```text
code/
dataset/
data/
results/
```

Each dataset case should contain:

```text
dataset/
  case_01_example/
    raw_requirement.txt
    structured_requirement.txt
    diagram.puml
```

The generation prompts use `structured_requirement.txt`. The reference diagram
is read from `diagram.puml`.

The optional RAG data should be placed under:

```text
data/
  rag_corpus/
    dataset_examples/
    plantuml_rules/
    state_diagram_theory/
  processed/
    experiments/
      split_35_seed42.json
```

## Main Scripts

`hybrid_requirement_pipeline.py` prepares structured functional requirements
from raw requirement text. It is only needed when `structured_requirement.txt`
files have not already been prepared.

`plantuml_experiment_pipeline.py` is the main command-line entry point for
creating splits, running diagram generation, applying repair, and recomputing
metrics.

`build_rag_index.py` builds the Chroma vector index from Markdown files in
`data/rag_corpus/`.

`create_rag_dataset_examples.py` creates RAG example Markdown files from the
training part of the dataset.

`create_rag_analysis_corpora.py` copies existing RAG documents into smaller
analysis corpora, such as examples-only, rules-only, or theory-only.

`build_repair_iteration_artifacts.py` summarizes repair attempts and prepares
repair-iteration review files.

`report_validity_percentages.py` reports PlantUML syntax validity and stricter
state-diagram structural validity.

## Pipeline Package

`plantuml_pipeline/cli.py` defines the command-line arguments.

`plantuml_pipeline/commands.py` implements the split, run, metrics, and table
commands.

`plantuml_pipeline/constants.py` stores default paths and regular expressions
used while parsing PlantUML.

`plantuml_pipeline/dataset.py` loads dataset cases and reads
`structured_requirement.txt`.

`plantuml_pipeline/generation.py` runs diagram-generation attempts, validation,
and repair.

`plantuml_pipeline/io_utils.py` contains small helpers for reading and writing
text, JSON, and JSONL files.

`plantuml_pipeline/metrics.py` compares generated diagrams with reference
diagrams and computes graph, syntax, and structural-validity metrics.

`plantuml_pipeline/model_client.py` sends prompts to local models through
Ollama.

`plantuml_pipeline/models.py` defines the dataclasses shared across the
pipeline.

`plantuml_pipeline/parser.py` normalizes PlantUML text, extracts states and
transitions, and checks PlantUML/state-diagram validity.

`plantuml_pipeline/prompting.py` builds zero-shot, few-shot, RAG, and repair
prompts.

## Requirements

Start Ollama before running generation:

```bash
ollama serve
```

Install Chroma if vector RAG is used:

```bash
pip install chromadb
```

For PlantUML render checking, the `plantuml` command should also be available
on the system path.

## Workflow

Prepare structured requirement files only if they are missing:

```bash
PYTHONPATH=code \
python3 code/hybrid_requirement_pipeline.py \
  --dataset-root dataset \
  --output-name structured_requirement.txt
```

Create the train/test split:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py split \
  --dataset-root dataset \
  --output data/processed/experiments/split_35_seed42.json
```

Create RAG example documents if they are missing:

```bash
PYTHONPATH=code \
python3 code/create_rag_dataset_examples.py \
  --dataset-root dataset \
  --split-file data/processed/experiments/split_35_seed42.json \
  --output-dir data/rag_corpus/dataset_examples
```

Build the vector RAG index:

```bash
PYTHONPATH=code \
python3 code/build_rag_index.py \
  --rag-docs-dir data/rag_corpus \
  --rag-db-dir results/rag_db
```

Run all configured generation strategies for all test-split cases:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --runs 3 \
  --save-prompts
```

This includes zero-shot, few-shot, RAG, validation, and repair-enabled
strategies.

## Validation Flow

The validation flow is separate from prompting, but it is used by both the
generation and repair stages.

First, the generated PlantUML is normalized and parsed. Then the parser checks
basic PlantUML syntax and state-diagram structure, including states,
transitions, initial states, final states, and unreachable states. The detected
errors and warnings are saved with the run metadata.

For repair-enabled strategies, the same validation issues are passed into the
repair prompt. The repaired diagram is validated again, and the pipeline keeps
the repaired version only when the validation score improves.

To validate one PlantUML file directly:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py validate \
  --puml results/plantuml_pipeline/example_diagram.puml \
  --json
```

To recompute validation and metric outputs for generated diagrams:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py metrics \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline
```

To report syntax-valid and structurally-valid percentages:

```bash
PYTHONPATH=code \
python3 code/report_validity_percentages.py
```

Run a quick check on one case:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --only-case-id case_01_example \
  --runs 1 \
  --save-prompts
```

Run only one strategy by selecting its run IDs. For example, zero-shot:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__zero_shot \
  --only-run-id open_source__mistral__zero_shot \
  --only-run-id open_source__llama31_8b_instruct__zero_shot \
  --only-run-id open_source__deepseek_r1_14b__zero_shot \
  --runs 3 \
  --save-prompts
```

For few-shot, replace `zero_shot` with `few_shot` and set
`--few-shot-count` if needed. For RAG, replace `zero_shot` with `rag`.

Run only the RAG repair strategy:

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

Repair iteration summaries can be produced with:

```bash
PYTHONPATH=code \
python3 code/build_repair_iteration_artifacts.py
```

Generated diagrams, prompts, metadata, and metric summaries are written under
`results/plantuml_pipeline/`.
