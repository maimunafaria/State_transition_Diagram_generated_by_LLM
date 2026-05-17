from __future__ import annotations

import re
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = CODE_ROOT.parent
DEFAULT_DATASET_ROOT = PROJECT_ROOT / "Dataset"
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "plantuml_pipeline"
DEFAULT_RAG_DOCS_DIR = CODE_ROOT / "data" / "retreival_corpis"
DEFAULT_RAG_DB_DIR = CODE_ROOT / "results" / "rag_db"
DEFAULT_RAG_COLLECTION_NAME = "uml_docs"

STATE_ALIAS_RE = re.compile(
    r'^\s*state\s+"(?P<label>[^"]+)"\s+as\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)'
    r'(?:\s+<<(?P<stereo>[^>]+)>>)?\s*(?:\{\s*\}|\{)?\s*$'
)
STATE_ALIAS_REVERSE_RE = re.compile(
    r'^\s*state\s+(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s+as\s+"(?P<label>[^"]+)"'
    r'(?:\s+<<(?P<stereo>[^>]+)>>)?\s*(?:\{\s*\}|\{)?\s*$'
)
STATE_DECL_RE = re.compile(
    r'^\s*state\s+(?P<name>"[^"]+"|[A-Za-z_][A-Za-z0-9_\-\.]*)'
    r'(?:\s+<<(?P<stereo>[^>]+)>>)?\s*(?:\{\s*\}|\{)?\s*$'
)
TRANSITION_RE = re.compile(
    r'^\s*(?P<src>\[\*\]|\[H\]|\[H\*\]|"[^"]+"|[^\s:]+)\s*'
    r'(?P<arrow>-(?:left|right|up|down|l|r|u|d|\\[hidden\\])?->|-->)\s*'
    r'(?P<dst>\[\*\]|\[H\]|\[H\*\]|"[^"]+"|[^\s:]+)(?:\s*:\s*(?P<event>.*))?\s*$'
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")
