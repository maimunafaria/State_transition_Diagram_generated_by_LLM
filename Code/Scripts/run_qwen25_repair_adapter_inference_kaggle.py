from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)


SYSTEM_PROMPT = (
    "You are a PlantUML state-diagram repair assistant. "
    "Repair the candidate diagram according to the validation errors. "
    "Do not add unsupported behavior. Return only valid PlantUML code."
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not all(row.get(key) for key in ("case_id", "instruction", "input")):
                raise ValueError(f"Invalid test row {line_number}")
            rows.append(row)
    return rows


def extract_puml(response: str) -> str:
    match = re.search(r"@startuml\b.*?@enduml", response, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return response.replace("```plantuml", "").replace("```", "").strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Qwen repair adapter on the frozen 18-case test set."
    )
    parser.add_argument("--test-data", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/kaggle/working/qwen25_repair_external18"),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-input-tokens", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=1536)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU not found.")
    if not args.adapter_path.is_dir():
        raise FileNotFoundError(f"Adapter not found: {args.adapter_path}")

    rows = read_jsonl(args.test_data)
    if len(rows) != 18:
        raise ValueError(f"Expected 18 test cases, found {len(rows)}")

    use_bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.adapter_path, use_fast=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=quantization,
        device_map={"": 0},
        dtype=dtype,
    )
    model = PeftModel.from_pretrained(base_model, args.adapter_path)
    model.eval()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{str(row['instruction']).strip()}\n\n"
                    f"{str(row['input']).strip()}"
                ),
            },
        ]
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=args.max_input_tokens,
        ).to("cuda")

        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        response = tokenizer.decode(
            generated[0, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        ).strip()
        repaired_puml = extract_puml(response)
        has_wrapper = (
            "@startuml" in repaired_puml.lower()
            and "@enduml" in repaired_puml.lower()
        )

        case_dir = args.output_dir / str(row["case_id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "invalid.puml").write_text(
            str(row.get("invalid_puml", "")).strip() + "\n",
            encoding="utf-8",
        )
        (case_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (case_dir / "raw_response.txt").write_text(
            response + "\n",
            encoding="utf-8",
        )
        (case_dir / "repaired.puml").write_text(
            repaired_puml + "\n",
            encoding="utf-8",
        )

        prediction = {
            **row,
            "response": response,
            "repaired_puml": repaired_puml,
            "has_plantuml_wrapper": has_wrapper,
            "input_token_count": int(inputs["input_ids"].shape[1]),
        }
        prediction_rows.append(prediction)
        csv_rows.append(
            {
                "case_id": str(row["case_id"]),
                "violation_types": "|".join(row.get("violation_types", [])),
                "has_plantuml_wrapper": str(has_wrapper).lower(),
                "input_token_count": str(inputs["input_ids"].shape[1]),
                "repaired_file": str(case_dir / "repaired.puml"),
            }
        )
        print(
            f"[{index:02d}/18] {row['case_id']} "
            f"wrapper={has_wrapper} input_tokens={inputs['input_ids'].shape[1]}"
        )

    predictions_path = args.output_dir / "predictions.jsonl"
    with predictions_path.open("w", encoding="utf-8") as handle:
        for row in prediction_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (args.output_dir / "predictions.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "violation_types",
                "has_plantuml_wrapper",
                "input_token_count",
                "repaired_file",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    summary = {
        "model": args.model,
        "adapter_path": str(args.adapter_path),
        "test_data": str(args.test_data),
        "case_count": len(rows),
        "wrapper_success_count": sum(
            bool(row["has_plantuml_wrapper"]) for row in prediction_rows
        ),
        "deterministic_decoding": True,
        "ground_truth_used_during_inference": False,
    }
    (args.output_dir / "inference_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
