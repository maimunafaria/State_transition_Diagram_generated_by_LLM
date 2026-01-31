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
```

## Outputs
- PlantUML files: `results/diagrams/`
- Chain‑of‑command text: `results/text/chain_of_command/`
- RAG index: `results/rag_db/`
- Images (if generated separately): `results/images/`

## Notes
- Scripts assume a local Ollama setup with models like `llama3` and `mistral`.
- RAG sources live in `data/raw/rag_docs/`.
