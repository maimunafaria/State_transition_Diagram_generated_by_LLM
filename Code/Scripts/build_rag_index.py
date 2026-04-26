import argparse
from pathlib import Path

import chromadb

from plantuml_pipeline.prompting import _rag_doc_source_type

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

RAG_DOCS_DIR = DATA_DIR / "rag_corpus"
DB_DIR = RESULTS_DIR / "rag_db"
COLLECTION_NAME = "uml_docs"


def build_index(rag_docs_dir: Path, db_dir: Path, collection_name: str, reset: bool = True) -> None:
    if not rag_docs_dir.exists():
        raise FileNotFoundError(f"RAG docs directory not found: {rag_docs_dir}")

    db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(db_dir))

    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass
    collection = client.get_or_create_collection(collection_name)

    docs = []
    ids = []
    metadatas = []

    for path in sorted(rag_docs_dir.rglob("*.md")):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        doc_id = str(path.relative_to(rag_docs_dir))
        docs.append(content)
        ids.append(doc_id)
        metadatas.append(
            {
                "source_type": _rag_doc_source_type(doc_id, content),
                "path": doc_id,
            }
        )

    if not ids:
        print(f"No Markdown RAG documents found in {rag_docs_dir}")
        return

    collection.add(documents=docs, ids=ids, metadatas=metadatas)
    print(f"Indexed {len(docs)} documents into collection '{collection_name}'")
    print(f"Vector DB: {db_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Chroma vector index for RAG.")
    parser.add_argument("--rag-docs-dir", type=Path, default=RAG_DOCS_DIR)
    parser.add_argument("--rag-db-dir", type=Path, default=DB_DIR)
    parser.add_argument("--collection-name", default=COLLECTION_NAME)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing collection instead of recreating it.",
    )
    args = parser.parse_args()
    build_index(
        rag_docs_dir=args.rag_docs_dir,
        db_dir=args.rag_db_dir,
        collection_name=args.collection_name,
        reset=not args.append,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
