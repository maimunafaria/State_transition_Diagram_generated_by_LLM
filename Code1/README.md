# UML State Diagram Generation Pipeline

This folder contains the scripts used for preparing requirements, generating
PlantUML state diagrams, applying validation-based repair, and checking syntax
and structural validity.


## Main Files

`hybrid_requirement_pipeline.py` prepares structured functional requirements from raw
requirement text. It is only needed when `structured_requirement.txt` files have
not already been prepared

`plantuml_experiment_pipeline.py` is the main command-line entry point. It calls
the pipeline package for dataset splitting, diagram generation, repair, and
metric calculation.

`build_rag_index.py` builds the Chroma vector index from the Markdown files in
`data/rag_corpus/`. The generation run uses this index for RAG.

`create_rag_dataset_examples.py` creates RAG example Markdown files from the
training portion of the dataset.

`create_rag_analysis_corpora.py` copies existing RAG documents into smaller
analysis corpora, such as examples-only, rules-only, or theory-only.

`build_repair_iteration_artifacts.py` summarizes repair attempts and prepares
repair-iteration review folders and tables.

`report_validity_percentages.py` reports PlantUML syntax validity and stricter
state-diagram structural validity.

## Pipeline Package Files

`plantuml_pipeline/__init__.py` exposes the package entry point.

`plantuml_pipeline/cli.py` defines the command-line arguments for validation,
splitting, generation, metrics, and table display.

`plantuml_pipeline/commands.py` contains the implementation behind the command
line: split creation, run execution, metric recomputation, and table output.

`plantuml_pipeline/constants.py` stores default paths and regular expressions
used while parsing PlantUML state diagrams.

`plantuml_pipeline/dataset.py` loads dataset cases. For prompting it reads
`structured_requirement.txt`.

`plantuml_pipeline/generation.py` runs one diagram-generation attempt, records
validation results, and applies repair when the selected method requires it.

`plantuml_pipeline/io_utils.py` contains small helpers for reading and writing
text, JSON, and JSONL files.

`plantuml_pipeline/metrics.py` compares generated diagrams with reference
diagrams and computes graph, syntax, and structural-validity metrics.

`plantuml_pipeline/model_client.py` sends prompts to local models through
Ollama.

`plantuml_pipeline/models.py` defines the dataclasses shared across the
pipeline, such as cases, experiment configurations, diagram graphs, and
validation results.

`plantuml_pipeline/parser.py` normalizes PlantUML text, extracts states and
transitions, and checks PlantUML/state-diagram validity.

`plantuml_pipeline/prompting.py` builds zero-shot, few-shot, RAG, and repair
prompts.

## Expected Folders

The code expects these folders at the repository root:

```text
code/
dataset/
data/
results/
```

The dataset cases should look like this:

```text
dataset/
  case_01_example/
    raw_requirement.txt
    structured_requirement.txt
    diagram.puml
```

The generation prompts use `structured_requirement.txt`.

The RAG files should look like this:

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

## Requirements

The generation scripts call local models through Ollama. Start Ollama before
running generation:

```bash
ollama serve
```

If vector RAG is used, install Chroma:

```bash
pip install chromadb
```

For PlantUML render checking, the `plantuml` command should be available on the
system path.

## Basic Usage

Create a train/test split:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py split \
  --dataset-root dataset \
  --output data/processed/experiments/split_35_seed42.json
```

Build the vector RAG index:

```bash
PYTHONPATH=code \
python3 code/build_rag_index.py \
  --rag-docs-dir data/rag_corpus \
  --rag-db-dir results/rag_db
```

Run a small generation test:

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

Run the full generation set for all test-split cases and all configured
strategies:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py run \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline \
  --rag-db-dir results/rag_db \
  --runs 3 \
  --save-prompts
```

By default, this runs the configured zero-shot, few-shot, RAG, validation, and
repair strategies for every case in the test split.

Run one strategy for all test-split cases by selecting the run IDs for that
strategy. For example, this runs zero-shot for the four main models:

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

For a RAG-only run, replace `zero_shot` with `rag` in the selected run IDs.

Recompute metrics from generated diagrams:

```bash
PYTHONPATH=code \
python3 code/plantuml_experiment_pipeline.py metrics \
  --dataset-root dataset \
  --results-root results/plantuml_pipeline
```

Report syntax and structural validity:

```bash
PYTHONPATH=code \
python3 code/report_validity_percentages.py
```

## Notes

The upload folder contains code only. It does not include generated diagrams,
evaluation spreadsheets, result tables, vector databases, or raw source PDFs.

The `results/` folder is created when the pipeline is run.
