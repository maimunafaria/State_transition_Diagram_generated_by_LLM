import argparse
import csv
import json
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

PROCESSED_DIR = DATA_DIR / "processed"
PAGES_DIR = PROCESSED_DIR / "pages"
DATASET_DIR = PROCESSED_DIR / "dataset"


def parse_manifest(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Manifest has no header row.")

        for raw in reader:
            row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw.items()}
            case_id = row.get("case_id") or row.get("id")
            page_start = row.get("page_start")
            page_end = row.get("page_end")

            if not case_id or not page_start or not page_end:
                raise ValueError(
                    "Manifest rows must include case_id (or id), page_start, page_end."
                )

            rows.append(
                {
                    "case_id": case_id,
                    "book": row.get("book", ""),
                    "page_start": int(page_start),
                    "page_end": int(page_end),
                }
            )

    return rows


def relpath(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return path.as_posix()


def extract_pages(pdf_path: Path, image_zoom: float, write_images: bool, write_text: bool):
    fitz = require_pymupdf()
    doc = fitz.open(pdf_path)

    pdf_stem = pdf_path.stem.replace(" ", "_")
    out_dir = PAGES_DIR / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    page_text = {}
    page_images = {}

    matrix = fitz.Matrix(image_zoom, image_zoom)

    for index in range(len(doc)):
        page_number = index + 1
        page = doc.load_page(index)

        if write_text:
            text = page.get_text("text") or ""
            txt_path = out_dir / f"page_{page_number:03d}.txt"
            txt_path.write_text(text, encoding="utf-8")
            page_text[page_number] = txt_path

        if write_images:
            pix = page.get_pixmap(matrix=matrix)
            img_path = out_dir / f"page_{page_number:03d}.png"
            pix.save(str(img_path))
            page_images[page_number] = img_path

    return page_text, page_images, len(doc)


def build_dataset_rows(cases, pdf_path: Path, page_text, page_images, page_count):
    rows = []
    for case in cases:
        start = case["page_start"]
        end = case["page_end"]
        if start < 1 or end < 1 or start > end:
            raise ValueError(f"Invalid page range for {case['case_id']}: {start}-{end}")
        if end > page_count:
            raise ValueError(
                f"Page range out of bounds for {case['case_id']}: {start}-{end} > {page_count}"
            )

        text_parts = []
        image_paths = []
        text_paths = []

        for page_number in range(start, end + 1):
            if page_number in page_text:
                text_parts.append(Path(page_text[page_number]).read_text(encoding="utf-8"))
                text_paths.append(relpath(page_text[page_number]))
            if page_number in page_images:
                image_paths.append(relpath(page_images[page_number]))

        user_story = "\n".join(p for p in text_parts if p).strip()

        rows.append(
            {
                "case_id": case["case_id"],
                "book": case["book"],
                "page_start": start,
                "page_end": end,
                "source_pdf": relpath(pdf_path),
                "page_images": image_paths,
                "page_text_files": text_paths,
                "user_story": user_story,
                "diagram_text": "",
            }
        )

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Build dataset.jsonl from a PDF and a cases.csv manifest."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=RAW_PDFS_DIR / "dataset.pdf",
        help="Path to source PDF",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=MANIFEST_DEFAULT,
        help="Path to cases.csv manifest",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATASET_DIR / "dataset.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--image-zoom",
        type=float,
        default=2.0,
        help="Scale factor for rendered page images",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip rendering images (text only)",
    )
    parser.add_argument(
        "--skip-text",
        action="store_true",
        help="Skip extracting page text",
    )

    args = parser.parse_args()

    pdf_path = args.pdf
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    cases = parse_manifest(args.manifest)
    page_text, page_images, page_count = extract_pages(
        pdf_path,
        image_zoom=args.image_zoom,
        write_images=not args.skip_images,
        write_text=not args.skip_text,
    )

    rows = build_dataset_rows(cases, pdf_path, page_text, page_images, page_count)

    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
