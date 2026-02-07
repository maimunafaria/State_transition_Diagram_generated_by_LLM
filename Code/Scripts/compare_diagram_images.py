import argparse
import csv
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

MANIFEST_DEFAULT = DATA_DIR / "raw" / "manifest" / "cases.csv"
PAGES_DIR_DEFAULT = DATA_DIR / "processed" / "pages" / "dataset"
RENDERED_DIR_DEFAULT = RESULTS_DIR / "images" / "manual"


def load_manifest(path: Path):
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw.items()}
            case_id = row.get("case_id") or row.get("id")
            if not case_id:
                continue
            rows[case_id] = {
                "page_start": int(row.get("page_start", "0")),
                "page_end": int(row.get("page_end", "0")),
            }
    return rows


def pick_page_image(pages_dir: Path, page_start: int, page_end: int):
    for page in (page_end, page_start):
        candidate = pages_dir / f"page_{page:03d}.png"
        if candidate.exists():
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Open the original page image and rendered PlantUML image side-by-side."
    )
    parser.add_argument("--case-id", required=True, help="Case ID from manifest (e.g., EXAMPLE_01)")
    parser.add_argument(
        "--manifest", type=Path, default=MANIFEST_DEFAULT, help="Path to cases.csv"
    )
    parser.add_argument(
        "--pages-dir",
        type=Path,
        default=PAGES_DIR_DEFAULT,
        help="Directory containing page images",
    )
    parser.add_argument(
        "--rendered-dir",
        type=Path,
        default=RENDERED_DIR_DEFAULT,
        help="Directory containing rendered images",
    )
    parser.add_argument(
        "--format",
        choices=["png", "svg"],
        default="png",
        help="Rendered image format",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print file paths instead of opening them",
    )

    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if args.case_id not in manifest:
        raise SystemExit(f"case_id not found: {args.case_id}")

    pages = manifest[args.case_id]
    page_image = pick_page_image(args.pages_dir, pages["page_start"], pages["page_end"])
    if not page_image:
        raise SystemExit("No page image found for this case.")

    rendered = args.rendered_dir / f"{args.case_id}.{args.format}"
    if not rendered.exists():
        raise SystemExit(f"Rendered image not found: {rendered}")

    if args.print_only:
        print(page_image)
        print(rendered)
        return

    subprocess.run(["open", str(page_image)], check=False)
    subprocess.run(["open", str(rendered)], check=False)


if __name__ == "__main__":
    main()
