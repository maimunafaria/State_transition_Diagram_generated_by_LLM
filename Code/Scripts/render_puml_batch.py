import argparse
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed" / "diagrams_txt"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "images" / "manual"


def find_puml_files(input_dir: Path):
    return sorted(input_dir.rglob("*.puml"))


def render_file(puml_file: Path, output_dir: Path, fmt: str):
    rel_output = os.path.relpath(output_dir, start=puml_file.parent)
    cmd = ["plantuml", f"-t{fmt}", "-o", rel_output, str(puml_file)]
    subprocess.run(cmd, cwd=puml_file.parent, check=True)


def main():
    parser = argparse.ArgumentParser(description="Render PlantUML files to images.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing .puml files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for rendered images",
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=["png", "svg"],
        help="Image output format",
    )

    args = parser.parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    if shutil.which("plantuml") is None:
        raise RuntimeError(
            "plantuml command not found. Install PlantUML and ensure it is on PATH."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    files = find_puml_files(input_dir)
    if not files:
        print(f"No .puml files found in {input_dir}")
        return

    for puml_file in files:
        render_file(puml_file, output_dir, args.format)
        print(f"Rendered {puml_file.name}")

    print(f"Images written to {output_dir}")


if __name__ == "__main__":
    main()
