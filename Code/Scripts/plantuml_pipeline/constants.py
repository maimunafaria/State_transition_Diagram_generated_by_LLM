from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "dataset"
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "plantuml_pipeline"
DEFAULT_RAG_DOCS_DIR = PROJECT_ROOT / "data" / "raw" / "rag_docs"

STATE_ALIAS_RE = re.compile(
    r'^\s*state\s+"(?P<label>[^"]+)"\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*$'
)
STATE_DECL_RE = re.compile(
    r'^\s*state\s+(?P<name>"[^"]+"|[A-Za-z_][A-Za-z0-9_\-\.]*)\s*$'
)
TRANSITION_RE = re.compile(
    r'^\s*(?P<src>\[\*\]|"[^"]+"|[^\s:]+)\s*-[^>]*->\s*(?P<dst>\[\*\]|"[^"]+"|[^\s:]+)(?:\s*:\s*(?P<event>.*))?\s*$'
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")
