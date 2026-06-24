from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = (
    "You are a PlantUML state-diagram repair assistant. "
    "Repair the candidate diagram according to the validation error. "
    "Return only valid PlantUML code."
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
    return rows


def to_alpaca(row: dict[str, Any]) -> dict[str, str]:
    return {
        "instruction": str(row.get("instruction", "")).strip(),
        "input": str(row.get("input", "")).strip(),
        "output": str(row.get("output", "")).strip(),
        "system": SYSTEM_PROMPT,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare cleaned PlantUML repair SFT data for LLaMA-Factory."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/sft/all_llm_violation_repair_sft.cleaned.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("finetune/llamafactory/plantuml_repair"),
    )
    parser.add_argument("--eval-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    examples = [to_alpaca(row) for row in rows]
    rng = random.Random(args.seed)
    rng.shuffle(examples)

    eval_count = max(1, round(len(examples) * args.eval_ratio)) if examples else 0
    eval_rows = examples[:eval_count]
    train_rows = examples[eval_count:]

    data_dir = args.output_dir / "data"
    config_dir = args.output_dir / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    write_json(data_dir / "plantuml_repair_train.json", train_rows)
    write_json(data_dir / "plantuml_repair_eval.json", eval_rows)

    dataset_info = {
        "plantuml_repair_train": {
            "file_name": "plantuml_repair_train.json",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
        "plantuml_repair_eval": {
            "file_name": "plantuml_repair_eval.json",
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
                "system": "system",
            },
        },
    }
    write_json(data_dir / "dataset_info.json", dataset_info)

    train_yaml = """\
### model
model_name_or_path: Qwen/Qwen2.5-7B-Instruct
trust_remote_code: true

### method
stage: sft
do_train: true
finetuning_type: lora
lora_target: all
quantization_bit: 4

### dataset
dataset_dir: data
dataset: plantuml_repair_train
eval_dataset: plantuml_repair_eval
template: qwen
cutoff_len: 4096
overwrite_cache: true
preprocessing_num_workers: 4

### output
output_dir: saves/qwen2_5_7b_lora/plantuml_repair
logging_steps: 5
save_steps: 50
plot_loss: true
overwrite_output_dir: true

### train
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 2.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
weight_decay: 0.01
max_grad_norm: 1.0
fp16: true

### eval
eval_strategy: steps
eval_steps: 50
per_device_eval_batch_size: 1
"""
    (config_dir / "qwen25_7b_plantuml_repair_qlora_sft.yaml").write_text(
        train_yaml,
        encoding="utf-8",
    )

    merge_yaml = """\
### model
model_name_or_path: Qwen/Qwen2.5-7B-Instruct
adapter_name_or_path: saves/qwen2_5_7b_lora/plantuml_repair
template: qwen
trust_remote_code: true

### export
export_dir: exports/qwen2_5_7b_plantuml_repair
export_size: 2
export_device: cpu
export_legacy_format: false
"""
    (config_dir / "merge_qwen25_7b_plantuml_repair_lora.yaml").write_text(
        merge_yaml,
        encoding="utf-8",
    )

    summary = {
        "input": str(args.input),
        "output_dir": str(args.output_dir),
        "total_examples": len(examples),
        "train_examples": len(train_rows),
        "eval_examples": len(eval_rows),
        "dataset_info": str(data_dir / "dataset_info.json"),
        "train_yaml": str(config_dir / "qwen25_7b_plantuml_repair_qlora_sft.yaml"),
        "merge_yaml": str(config_dir / "merge_qwen25_7b_plantuml_repair_lora.yaml"),
    }
    write_json(args.output_dir / "prepare_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
