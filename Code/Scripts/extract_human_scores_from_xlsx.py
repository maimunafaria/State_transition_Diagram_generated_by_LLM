from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def col_to_num(col: str) -> int:
    value = 0
    for ch in col:
        if ch.isalpha():
            value = value * 26 + ord(ch.upper()) - 64
    return value


def cell_ref_to_pos(ref: str) -> tuple[int, int]:
    col = "".join(ch for ch in ref if ch.isalpha())
    row = "".join(ch for ch in ref if ch.isdigit())
    return int(row), col_to_num(col)


def load_first_sheet_rows(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{MAIN_NS}si"):
                shared_strings.append("".join(t.text or "" for t in si.iter(f"{MAIN_NS}t")))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = workbook.find(f"{MAIN_NS}sheets")
        if sheets is None or len(sheets) == 0:
            return []
        first_sheet = sheets[0]
        rel_id = first_sheet.attrib[f"{REL_NS}id"]

        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        target = "xl/" + rel_map[rel_id]

        sheet_root = ET.fromstring(archive.read(target))
        rows: list[list[str]] = []
        for row in sheet_root.iter(f"{MAIN_NS}row"):
            values: dict[int, str] = {}
            for cell in row.findall(f"{MAIN_NS}c"):
                ref = cell.attrib.get("r", "")
                _, col_idx = cell_ref_to_pos(ref)
                cell_type = cell.attrib.get("t")
                value_node = cell.find(f"{MAIN_NS}v")
                value = ""
                if cell_type == "s" and value_node is not None and value_node.text is not None:
                    value = shared_strings[int(value_node.text)]
                elif cell_type == "inlineStr":
                    inline_node = cell.find(f"{MAIN_NS}is")
                    if inline_node is not None:
                        value = "".join(t.text or "" for t in inline_node.iter(f"{MAIN_NS}t"))
                elif value_node is not None and value_node.text is not None:
                    value = value_node.text
                values[col_idx] = value
            if values:
                max_col = max(values)
                rows.append([values.get(i, "") for i in range(1, max_col + 1)])
        return rows


def normalize_method(method: str) -> str:
    low = method.strip().lower()
    if low == "repair":
        return "baseline_repair"
    if low == "few-shot":
        return "few_shot"
    if low == "rag":
        return "rag"
    if low == "syntax-grounded":
        return "syntax_grounded_repair"
    return method.strip()


def normalize_llm(llm: str) -> str:
    return (
        llm.strip()
        .replace(" Instruct", "")
        .replace("  ", " ")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract clean human-score CSV from a simple XLSX sheet.")
    parser.add_argument("--input-xlsx", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    input_xlsx = Path(args.input_xlsx)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_first_sheet_rows(input_xlsx)
    if not rows:
        raise SystemExit("No sheet rows found.")

    header = rows[0]
    records = [
        dict(zip(header, row + [""] * (len(header) - len(row))))
        for row in rows[1:]
        if any(str(cell).strip() for cell in row)
    ]
    records = [r for r in records if str(r.get("original_diagram_name", "")).strip()]

    clean_rows: list[dict[str, str]] = []
    per_diagram: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)

    for r in records:
        clean = {
            "assigned_folder": r.get("assigned_folder", "").strip(),
            "case_id": f"case_{int(float(r['case_number'])):02d}" if r.get("case_number", "").strip() else "",
            "diagram_variant": r.get("diagram_number", "").strip(),
            "evaluator_id": r.get("evaluator_id", "").strip(),
            "generation_model": normalize_llm(r.get("llm_used", "")),
            "generation_method": normalize_method(r.get("method", "")),
            "original_diagram_name": r.get("original_diagram_name", "").strip(),
            "completeness_score": r.get("completeness", "").strip(),
            "correctness_score": r.get("correctness", "").strip(),
            "understandability_score": r.get("understandability", "").strip(),
            "terminology_alignment_score": r.get("terminology_alignment", "").strip(),
            "completeness_justification": r.get("completeness_justification", "").strip(),
            "correctness_justification": r.get("correctness_justification", "").strip(),
            "understandability_justification": r.get("understandability_justification", "").strip(),
            "terminology_alignment_justification": r.get("terminology_alignment_justification", "").strip(),
            "combined_justifications": r.get("Combined justifications (N/A skipped)", "").strip(),
            "combined_meaning": r.get("What the combined justification means", "").strip(),
        }
        clean_rows.append(clean)
        key = (
            clean["case_id"],
            clean["diagram_variant"],
            clean["generation_model"],
            clean["generation_method"],
            clean["original_diagram_name"],
        )
        per_diagram[key].append(clean)

    clean_csv = output_dir / "human_scores_clean.csv"
    with clean_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(clean_rows[0].keys()))
        writer.writeheader()
        writer.writerows(clean_rows)

    coverage_rows: list[dict[str, str]] = []
    for key, entries in sorted(per_diagram.items()):
        evaluator_ids = sorted({entry["evaluator_id"] for entry in entries})
        coverage_rows.append(
            {
                "case_id": key[0],
                "diagram_variant": key[1],
                "generation_model": key[2],
                "generation_method": key[3],
                "original_diagram_name": key[4],
                "rating_count": str(len(entries)),
                "unique_evaluator_count": str(len(evaluator_ids)),
                "evaluator_ids": "|".join(evaluator_ids),
                "has_exactly_two_humans": "True" if len(evaluator_ids) == 2 else "False",
            }
        )

    coverage_csv = output_dir / "human_scores_coverage.csv"
    with coverage_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0].keys()))
        writer.writeheader()
        writer.writerows(coverage_rows)

    summary_txt = output_dir / "human_scores_summary.txt"
    unique_diagrams = len(per_diagram)
    rating_dist = Counter(len(v) for v in per_diagram.values())
    unique_eval_dist = Counter(len({e['evaluator_id'] for e in v}) for v in per_diagram.values())
    exact_two = sum(1 for v in per_diagram.values() if len({e["evaluator_id"] for e in v}) == 2)
    with summary_txt.open("w", encoding="utf-8") as handle:
        handle.write(f"Total score rows: {len(clean_rows)}\n")
        handle.write(f"Unique diagrams: {unique_diagrams}\n")
        handle.write(f"Diagrams with exactly two unique human evaluators: {exact_two}\n")
        handle.write(f"Rating count distribution: {dict(rating_dist)}\n")
        handle.write(f"Unique evaluator count distribution: {dict(unique_eval_dist)}\n")

    print(f"Wrote clean CSV: {clean_csv}")
    print(f"Wrote coverage CSV: {coverage_csv}")
    print(f"Wrote summary: {summary_txt}")
    print(f"Unique diagrams: {unique_diagrams}")
    print(f"Exactly two unique human evaluators: {exact_two}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
