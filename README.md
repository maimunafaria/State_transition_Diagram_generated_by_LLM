# State_transition_Diagram_generated_by_LLM

Generate UML state machine diagrams (PlantUML) from natural‑language requirements using LLM prompts.

## Project layout
```
Code/
  Scripts/                 # Python scripts
data/
  raw/rag_docs/            # RAG reference docs
results/
  diagrams/                # .puml outputs (few‑shot)
  text/chain_of_command/   # chain‑of‑command text outputs
  text/                    # other text outputs (e.g., zero‑shot)
  images/fewshot/           # rendered images from few‑shot outputs
  images/chain_of_command/  # rendered images from chain‑of‑command outputs
  rag_db/                  # Chroma index output
```

## Scripts
Run from the project root:
```
python Code/Scripts/Few_shot_text.py
python Code/Scripts/Chain_Of_Command.py
python Code/Scripts/chain_of_command_mistral.py
python Code/Scripts/build_rag_index.py
python Code/Scripts/build_experiment_manifest.py
```

### Build Section 3.4 experiment design artifacts
```
python Code/Scripts/build_experiment_manifest.py \
  --dataset data/processed/dataset/dataset_2026-02-24.jsonl
```
Creates:
- `data/processed/dataset/subsets/gpt4o_balanced_30.jsonl`
- `data/processed/experiments/run_manifest_3_4.jsonl`
- `data/processed/experiments/experimental_design_3_4.json`

## Outputs
- PlantUML files: `results/diagrams/`
- Chain‑of‑command text: `results/text/chain_of_command/`
- RAG index: `results/rag_db/`
- Images (if generated separately): `results/images/`

## Notes
- Scripts assume a local Ollama setup with models like `llama3` and `mistral`.
- RAG sources live in `data/raw/rag_docs/`.

## Research-Oriented Pipeline
Use the modular pipeline entrypoint:
```
python Code/Scripts/plantuml_experiment_pipeline.py --help
```

### 1) Run generation with domain-aware RAG
```
python Code/Scripts/plantuml_experiment_pipeline.py run \
  --only-run-id open_source__qwen25_7b_instruct__rag \
  --rag-docs-dir data/raw/rag_docs \
  --top-k-rag 3 \
  --rag-max-chars-per-doc 1200 \
  --rag-domain-hint inventory \
  --runs 3
```

### 2) Run stacked-LLM ensemble (with optional RAG)
```
python Code/Scripts/plantuml_experiment_pipeline.py ensemble \
  --ensemble-method stacked_llm \
  --stack-model llama3.1:8b-instruct \
  --stack-use-rag \
  --stack-rag-docs-dir data/raw/rag_docs \
  --stack-top-k-rag 3 \
  --stack-rag-domain-hint inventory \
  --stack-fallback-majority
```

### 3) Recompute and inspect metrics
```
python Code/Scripts/plantuml_experiment_pipeline.py metrics
python Code/Scripts/plantuml_experiment_pipeline.py table --source summary
```

Research traceability artifacts:
- `results/.../manifest.json`: full run configuration and RAG settings.
- `results/.../runs/*/*.meta.json`: per-case metadata including retrieval traces.
- `results/.../metrics/*`: aggregate and per-run metrics.
