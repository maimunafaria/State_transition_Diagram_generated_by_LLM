# How to Run This Project

This folder contains the code and RAG artifacts needed to generate UML state-machine diagrams from bidirectionally aligned software requirements.

The pipeline does four main things:

1. Reads dataset cases from `dataset/`
2. Builds prompts using zero-shot, few-shot, RAG, or repair settings
3. Calls a local LLM through Ollama
4. Saves generated PlantUML diagrams and computes automated validity metrics

## 1. Install Requirements

From the project root, run:

```bash
pip3 install -r code/requirements.txt
```

The only Python package dependency is `chromadb`, which is needed for vector RAG.

## 2. Start Ollama

The generation code uses local models through Ollama.

Start Ollama:

```bash
ollama serve
```

In another terminal, pull at least one model. For example:

```bash
ollama pull qwen2.5:7b-instruct
```

The default examples below use Qwen 2.5 7B.

## 3. Run a Small Test First

Before running the full experiment, test one case. This confirms that the dataset path, Chroma vector DB, RAG files, and model call are working.

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/retreival_corpis \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db \
  --qwen-model qwen2.5:7b-instruct \
  --only-case-id case_01_healthcare_portal \
  --runs 1 \
  --save-prompts
```

What this does:

- loads one dataset case
- builds prompts from the bidirectionally aligned requirement
- retrieves RAG context from the Chroma vector DB at `code/results/rag_db`
- asks the local model to generate PlantUML
- saves the `.puml`, prompt, and metadata files

Outputs are saved under:

```text
results/plantuml_pipeline/runs/
```

## 4. Generate Diagrams with RAG

Use this when you want normal RAG-based diagram generation.

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/retreival_corpis \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__rag \
  --qwen-model qwen2.5:7b-instruct \
  --runs 1 \
  --save-prompts
```

What this does:

- runs only the Qwen RAG configuration
- uses the full RAG corpus:
  - dataset examples
  - PlantUML rules
  - UML state-diagram theory
- writes generated diagrams into `results/plantuml_pipeline/runs/`

## 5. Generate Diagrams with RAG + Repair

Use this when you want the model to repair invalid diagrams after generation.

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/retreival_corpis \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db \
  --only-run-id open_source__qwen25_7b_instruct__rag_validation_generator_critic_repair \
  --qwen-model qwen2.5:7b-instruct \
  --runs 1 \
  --repair-attempts 3 \
  --save-prompts
```

What this does:

- generates a first PlantUML diagram
- validates it automatically
- if issues are found, builds a repair prompt
- gives the model targeted repair hints
- accepts the repaired diagram only if the validation score improves

Repair hints are defined in:

```text
code/Code/Scripts/plantuml_pipeline/prompting.py
```

The repair loop is defined in:

```text
code/Code/Scripts/plantuml_pipeline/generation.py
```

## 6. Run All Local Model Configurations

This runs all configured local-model methods. It can take a long time.

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/retreival_corpis \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db \
  --runs 1 \
  --save-prompts
```

Use `--skip-existing` if you want to continue a previous run without overwriting finished outputs:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/retreival_corpis \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db \
  --runs 1 \
  --save-prompts \
  --skip-existing
```

## 7. Run RAG Ablation

RAG ablation means testing only one type of RAG knowledge at a time.

Examples-only RAG:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/rag_ablation/examples_only \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db_examples_only \
  --rag-ablation-tag examples_only \
  --only-run-id open_source__qwen25_7b_instruct__rag__examples_only \
  --qwen-model qwen2.5:7b-instruct \
  --runs 1 \
  --save-prompts
```

Rules-only RAG:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/rag_ablation/rules_only \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db_rules_only \
  --rag-ablation-tag rules_only \
  --only-run-id open_source__qwen25_7b_instruct__rag__rules_only \
  --qwen-model qwen2.5:7b-instruct \
  --runs 1 \
  --save-prompts
```

Theory-only RAG:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py run \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline \
  --rag-docs-dir code/data/rag_ablation/theory_only \
  --rag-mode vector \
  --rag-db-dir code/results/rag_db_theory_only \
  --rag-ablation-tag theory_only \
  --only-run-id open_source__qwen25_7b_instruct__rag__theory_only \
  --qwen-model qwen2.5:7b-instruct \
  --runs 1 \
  --save-prompts
```

## 8. Compute Metrics

After generation, compute automated metrics:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/plantuml_experiment_pipeline.py metrics \
  --dataset-root Dataset \
  --results-root results/plantuml_pipeline
```

This computes:

- PlantUML validity
- structural validity
- graph similarity metrics
- state/transition matching metrics

Metrics are saved under:

```text
results/plantuml_pipeline/metrics/
```

## 9. Structural Validity Analysis

After metrics are available, run:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/analyze_structural_validity_rq.py
```

This creates automated structural validity summaries from the metrics CSV files.

## 10. Repair Effectiveness Analysis

After repair runs are available, run:

```bash
PYTHONPATH=code/Code/Scripts \
python3 code/Code/Scripts/analyze_repair_effectiveness.py
```

This compares the initial generated diagrams with the final repaired diagrams.

## Important Files

- Dataset structuring code: `code/Code/Scripts/hybrid_requirement_pipeline.py`
- Main experiment runner: `code/Code/Scripts/plantuml_experiment_pipeline.py`
- Prompt and RAG logic: `code/Code/Scripts/plantuml_pipeline/prompting.py`
- Generation and repair loop: `code/Code/Scripts/plantuml_pipeline/generation.py`
- Validation and DFS logic: `code/Code/Scripts/plantuml_pipeline/parser.py`
- Metrics logic: `code/Code/Scripts/plantuml_pipeline/metrics.py`
- Main RAG corpus: `code/data/retreival_corpis/`
- RAG ablation corpus: `code/data/rag_ablation/`

## Notes

- Use vector RAG for these experiments. The copied Chroma DB folders are already included under `code/results/rag_db*`.
- The code assumes the dataset folder is named `Dataset/` and contains `case_*` folders.
- If PlantUML CLI is installed, the validator can also run official PlantUML syntax checks.
