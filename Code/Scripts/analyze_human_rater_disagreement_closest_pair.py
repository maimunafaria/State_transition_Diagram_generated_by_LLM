"""Compute closest-pair human rater disagreement statistics.

This script parses the ultimate human-evaluation workbook directly from the
XLSX XML, so it does not require pandas/openpyxl. For diagrams with exactly
two responses, those two responses are used. For diagrams with three responses,
the closest pair is selected by the smallest mean absolute difference across
the four human-evaluation criteria.
"""

from __future__ import annotations

import csv
import itertools
import math
import re
import statistics
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zipfile import ZipFile


INPUT_XLSX = Path(
    "/Users/faria/Downloads/Evaluation Form – UML State Diagram Scoring (Responses) (6).xlsx"
)
OUTPUT_CSV = (
    Path(__file__).resolve().parents[2]
    / "results"
    / "human_evaluation_likert"
    / "human_rater_disagreement_selected_table_closest_pair.csv"
)

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CRITERIA = [
    "completeness",
    "correctness",
    "understandability",
    "terminology_alignment",
]
CRITERION_LABELS = {
    "completeness": "Completeness",
    "correctness": "Correctness",
    "understandability": "Understandability",
    "terminology_alignment": "Terminological alignment",
}
KEY_COLS = ["assigned_folder", "case_number", "diagram_number", "original_diagram_name"]


def col_to_idx(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {cell_ref}")
    idx = 0
    for char in match.group(1):
        idx = idx * 26 + ord(char) - 64
    return idx - 1


def read_sheet(zip_file: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zip_file.read(sheet_path))
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", NS):
        values: dict[int, str] = {}
        max_idx = -1
        for cell in row.findall("a:c", NS):
            idx = col_to_idx(cell.attrib.get("r", "A1"))
            max_idx = max(max_idx, idx)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("a:v", NS)
            inline_node = cell.find("a:is", NS)
            value = ""
            if cell_type == "s" and value_node is not None:
                value = shared_strings[int(value_node.text or "0")]
            elif cell_type == "inlineStr" and inline_node is not None:
                value = "".join(
                    text_node.text or "" for text_node in inline_node.findall(".//a:t", NS)
                )
            elif value_node is not None:
                value = value_node.text or ""
            values[idx] = value
        if max_idx >= 0:
            rows.append([values.get(i, "") for i in range(max_idx + 1)])
    return rows


def as_float(value: str | None) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def row_scores(row: dict[str, str]) -> list[float] | None:
    scores = [as_float(row.get(criterion)) for criterion in CRITERIA]
    if any(score is None for score in scores):
        return None
    return [float(score) for score in scores]


def closest_pair(rows: list[dict[str, str]]) -> list[dict[str, str]] | None:
    valid_rows = [row for row in rows if row_scores(row) is not None]
    if len(valid_rows) < 2:
        return None

    best_pair: tuple[tuple[float, float, float], dict[str, str], dict[str, str]] | None = None
    for left, right in itertools.combinations(valid_rows, 2):
        left_scores = row_scores(left)
        right_scores = row_scores(right)
        if left_scores is None or right_scores is None:
            continue
        absolute_differences = [
            abs(left_scores[idx] - right_scores[idx]) for idx in range(len(CRITERIA))
        ]
        mean_abs_diff = sum(absolute_differences) / len(absolute_differences)
        overall_abs_diff = abs(
            (sum(left_scores) / len(left_scores)) - (sum(right_scores) / len(right_scores))
        )
        max_abs_diff = max(absolute_differences)
        selection_key = (mean_abs_diff, overall_abs_diff, max_abs_diff)
        if best_pair is None or selection_key < best_pair[0]:
            best_pair = (selection_key, left, right)

    if best_pair is None:
        return None
    return sorted(
        [best_pair[1], best_pair[2]],
        key=lambda row: as_float(row.get("excel_row")) or 0,
    )


def cohens_d_independent(second_scores: list[float], first_scores: list[float]) -> float:
    if len(second_scores) < 2 or len(first_scores) < 2:
        return float("nan")
    pooled_sd = math.sqrt(
        (
            (len(second_scores) - 1) * statistics.variance(second_scores)
            + (len(first_scores) - 1) * statistics.variance(first_scores)
        )
        / (len(second_scores) + len(first_scores) - 2)
    )
    if pooled_sd == 0:
        return 0.0
    return (statistics.mean(second_scores) - statistics.mean(first_scores)) / pooled_sd


def cohens_dz(differences: list[float]) -> float:
    if len(differences) < 2:
        return float("nan")
    sd = statistics.stdev(differences)
    if sd == 0:
        return 0.0
    return statistics.mean(differences) / sd


def report_decimal(value: float) -> str:
    """Match thesis-table rounding: four-decimal intermediate, half-up to three."""
    rounded_four = Decimal(str(round(value, 4)))
    return str(rounded_four.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def load_long_form_rows(path: Path) -> list[dict[str, str]]:
    with ZipFile(path) as zip_file:
        shared_root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(text_node.text or "" for text_node in item.findall(".//a:t", NS))
            for item in shared_root.findall("a:si", NS)
        ]
        rows = read_sheet(zip_file, "xl/worksheets/sheet4.xml", shared_strings)

    headers = rows[0]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        records.append(dict(zip(headers, padded, strict=False)))
    return records


def selected_pairs(records: list[dict[str, str]]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in records:
        key = tuple(row.get(column, "") for column in KEY_COLS)
        groups.setdefault(key, []).append(row)

    pairs: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for key, rows in groups.items():
        if len(rows) == 2:
            pairs[key] = sorted(rows, key=lambda row: as_float(row.get("excel_row")) or 0)
        else:
            pair = closest_pair(rows)
            if pair is not None:
                pairs[key] = pair
    return pairs


def table_rows(pairs: dict[tuple[str, ...], list[dict[str, str]]]) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []

    for criterion in CRITERIA:
        first_scores: list[float] = []
        second_scores: list[float] = []
        differences: list[float] = []
        count_ge_2 = 0

        for pair in pairs.values():
            first = as_float(pair[0].get(criterion))
            second = as_float(pair[1].get(criterion))
            if first is None or second is None:
                continue
            first_scores.append(first)
            second_scores.append(second)
            difference = second - first
            differences.append(difference)
            if abs(difference) >= 2:
                count_ge_2 += 1

        n = len(differences)
        output_rows.append(
            {
                "Criterion": CRITERION_LABELS[criterion],
                "Cohen's d": report_decimal(
                    cohens_d_independent(second_scores, first_scores)
                ),
                "Paired Cohen's dz": report_decimal(cohens_dz(differences)),
                ">=2-point difference": f"{count_ge_2} / {n} = {count_ge_2 / n * 100:.1f}%",
            }
        )

    first_averages: list[float] = []
    second_averages: list[float] = []
    average_differences: list[float] = []
    count_average_ge_2 = 0

    for pair in pairs.values():
        first_scores = row_scores(pair[0])
        second_scores = row_scores(pair[1])
        if first_scores is None or second_scores is None:
            continue
        first_average = sum(first_scores) / len(first_scores)
        second_average = sum(second_scores) / len(second_scores)
        first_averages.append(first_average)
        second_averages.append(second_average)
        difference = second_average - first_average
        average_differences.append(difference)
        if abs(difference) >= 2:
            count_average_ge_2 += 1

    n = len(average_differences)
    output_rows.append(
        {
            "Criterion": "Overall average score",
            "Cohen's d": report_decimal(
                cohens_d_independent(second_averages, first_averages)
            ),
            "Paired Cohen's dz": report_decimal(cohens_dz(average_differences)),
            ">=2-point difference": f"{count_average_ge_2} / {n} = {count_average_ge_2 / n * 100:.1f}%",
        }
    )

    return output_rows


def main() -> None:
    records = load_long_form_rows(INPUT_XLSX)
    pairs = selected_pairs(records)
    rows = table_rows(pairs)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
