import argparse
import csv
import re
import sys
from pathlib import Path


def require_pymupdf():
    try:
        import fitz  # PyMuPDF
    except Exception:  # pragma: no cover - import guard
        print("Missing dependency: PyMuPDF")
        print("Install with: pip install pymupdf")
        sys.exit(1)
    return fitz


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_PDFS_DIR = DATA_DIR / "raw" / "source_pdfs"
MANIFEST_DEFAULT = DATA_DIR / "raw" / "manifest" / "cases.csv"


EXAMPLE_RE = re.compile(r"example\s*(\d+)", re.IGNORECASE)


def extract_case_starts(pdf_path: Path):
    fitz = require_pymupdf()
    starts = []
    with fitz.open(pdf_path) as doc:
        for index in range(doc.page_count):
            page = doc.load_page(index)
            text = (page.get_text("text") or "").strip()
            if not text:
                continue

            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if not lines:
                continue

            match = None
            for line in lines:
                match = EXAMPLE_RE.search(line)
                if match:
                    break
            if not match:
                continue
            example_num = match.group(1).zfill(2)
            case_id = f"EXAMPLE_{example_num}"

            book_line = next((ln for ln in lines if ln.lower().startswith("book:")), "")
            book = book_line.split(":", 1)[1].strip() if book_line else ""

            starts.append(
                {
                    "case_id": case_id,
                    "book": book,
                    "page_start": index + 1,
                }
            )

    return starts


def build_manifest(starts, page_count):
    rows = []
    for idx, start in enumerate(starts):
        end_page = page_count if idx == len(starts) - 1 else starts[idx + 1]["page_start"] - 1
        rows.append(
            {
                "case_id": start["case_id"],
                "book": start["book"],
                "page_start": start["page_start"],
                "page_end": end_page,
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Auto-build cases.csv by detecting 'Example NN' page headings."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=RAW_PDFS_DIR / "dataset.pdf",
        help="Path to source PDF",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MANIFEST_DEFAULT,
        help="Output manifest CSV",
    )

    args = parser.parse_args()
    pdf_path = args.pdf
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    fitz = require_pymupdf()
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count

    starts = extract_case_starts(pdf_path)
    if not starts:
        raise RuntimeError("No 'Example NN' headings found. Manifest not generated.")

    rows = build_manifest(starts, page_count)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case_id", "book", "page_start", "page_end"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
