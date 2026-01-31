from pathlib import Path
import chromadb
from chromadb.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

RAG_DOCS_DIR = DATA_DIR / "raw" / "rag_docs"
DB_DIR = RESULTS_DIR / "rag_db"
COLLECTION_NAME = "uml_docs"

def build_index():
    if not RAG_DOCS_DIR.exists():
        raise FileNotFoundError(f"RAG docs directory not found: {RAG_DOCS_DIR}")

    DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.Client(
        Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(DB_DIR),
        )
    )

    collection = client.get_or_create_collection(COLLECTION_NAME)

    docs = []
    ids = []

    for path in sorted(RAG_DOCS_DIR.iterdir()):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        docs.append(content)
        ids.append(path.name)


    if ids:
        try:
            collection.delete(ids=collection.get(ids=ids)["ids"])
        except Exception:
            pass

    collection.add(documents=docs, ids=ids)
    print(f"Indexed {len(docs)} documents into collection '{COLLECTION_NAME}'")

if __name__ == "__main__":
    build_index()
