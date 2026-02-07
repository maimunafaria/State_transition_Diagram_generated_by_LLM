import argparse
import base64
import csv
import json
import sys
from pathlib import Path
from urllib import request, error


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

MANIFEST_DEFAULT = DATA_DIR / "raw" / "manifest" / "cases.csv"
PAGES_DIR_DEFAULT = DATA_DIR / "processed" / "pages" / "dataset"
OUTPUT_DIR_DEFAULT = DATA_DIR / "processed" / "diagrams_txt"


def load_manifest(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw.items()}
            case_id = row.get("case_id") or row.get("id")
            if not case_id:
                raise ValueError("Manifest row missing case_id.")
            rows.append(
                {
                    "case_id": case_id,
                    "book": row.get("book", ""),
                    "page_start": int(row.get("page_start", "0")),
                    "page_end": int(row.get("page_end", "0")),
                }
            )
    return rows


def page_paths(pages_dir: Path, start: int, end: int):
    paths = []
    for page in range(start, end + 1):
        candidate = pages_dir / f"page_{page:03d}.png"
        if candidate.exists():
            paths.append(candidate)
    return paths


def encode_images(paths):
    images = []
    for path in paths:
        images.append(base64.b64encode(path.read_bytes()).decode("utf-8"))
    return images


def build_prompt(case_id: str):
    return (
        "You are given image(s) of a UML state machine diagram. "
        "Convert the diagram to PlantUML.\n\n"
        "Rules:\n"
        "- Output ONLY PlantUML code.\n"
        "- Start with @startuml and end with @enduml.\n"
        "- Use [*] for the initial state.\n"
        "- Use --> for transitions.\n"
        "- Include transition labels if present.\n"
        "- Do not include explanations.\n\n"
        f"Case ID: {case_id}"
    )


def call_ollama(host: str, model: str, prompt: str, images):
    payload = {
        "model": model,
        "prompt": prompt,
        "images": images,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=f"{host.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except error.HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error: {exc.code} {exc.reason}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Cannot reach Ollama at {host}") from exc


def extract_plantuml(text: str):
    if not text:
        return text
    start = text.find("@startuml")
    end = text.rfind("@enduml")
    if start == -1 or end == -1:
        return text.strip()
    return text[start : end + len("@enduml")].strip() + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Generate PlantUML from case page images using Ollama vision."
    )
    parser.add_argument("--model", default="llama3.2-vision", help="Ollama vision model")
    parser.add_argument(
        "--host", default="http://127.0.0.1:11434", help="Ollama API host"
    )
    parser.add_argument(
        "--manifest", type=Path, default=MANIFEST_DEFAULT, help="Path to cases.csv"
    )
    parser.add_argument(
        "--pages-dir", type=Path, default=PAGES_DIR_DEFAULT, help="Directory of page images"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR_DEFAULT,
        help="Directory for .puml outputs",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="Process a specific case_id (can be repeated)",
    )
    parser.add_argument(
        "--last-page-only",
        action="store_true",
        help="Only send the last page image per case",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Limit number of images per case (0 = no limit)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cases that already have .puml output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which images would be processed without calling Ollama",
    )

    args = parser.parse_args()
    cases = load_manifest(args.manifest)

    if args.case_id:
        wanted = {cid.strip() for cid in args.case_id}
        cases = [case for case in cases if case["case_id"] in wanted]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for case in cases:
        case_id = case["case_id"]
        output_path = args.output_dir / f"{case_id}.puml"
        if args.skip_existing and output_path.exists():
            print(f"Skip {case_id} (exists)")
            continue

        pages = page_paths(args.pages_dir, case["page_start"], case["page_end"])
        if not pages:
            print(f"Skip {case_id} (no images found)")
            continue

        if args.last_page_only:
            pages = [pages[-1]]
        if args.max_pages and len(pages) > args.max_pages:
            pages = pages[: args.max_pages]

        if args.dry_run:
            print(f"{case_id}: {len(pages)} image(s)")
            continue

        images = encode_images(pages)
        prompt = build_prompt(case_id)
        response = call_ollama(args.host, args.model, prompt, images)
        plantuml = extract_plantuml(response)
        if not plantuml:
            print(f"{case_id}: empty response")
            continue

        output_path.write_text(plantuml, encoding="utf-8")
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
