from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from peft import LoraConfig, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


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
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc
            if not all(row.get(field) for field in ("instruction", "input", "output")):
                raise ValueError(f"Missing SFT field on line {line_number} of {path}")
            case_id = str(row.get("metadata", {}).get("case_id", "")).strip()
            if not case_id:
                raise ValueError(f"Missing metadata.case_id on line {line_number}")
            rows.append(row)
    if not rows:
        raise ValueError(f"No examples found in {path}")
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def case_id(row: dict[str, Any]) -> str:
    return str(row["metadata"]["case_id"]).strip()


def to_prompt_completion(row: dict[str, Any]) -> dict[str, Any]:
    user_content = (
        f"{str(row['instruction']).strip()}\n\n"
        f"{str(row['input']).strip()}"
    )
    return {
        "prompt": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "completion": [
            {"role": "assistant", "content": str(row["output"]).strip()}
        ],
    }


def load_forbidden_cases(path: Path | None) -> set[str]:
    if path is None:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("test_case_ids", payload)
    if not isinstance(values, list):
        raise ValueError(
            "External test split must be a list or contain test_case_ids."
        )
    return {str(value).strip() for value in values if str(value).strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kaggle QLoRA SFT for PlantUML repair with case-level splitting."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Cleaned repair JSONL containing metadata.case_id.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/kaggle/working/qwen25_7b_plantuml_repair"),
    )
    parser.add_argument(
        "--model",
        default="Qwen/Qwen2.5-7B-Instruct",
    )
    parser.add_argument("--validation-cases", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--learning-rate", type=float, default=1.0e-4)
    parser.add_argument(
        "--external-test-split",
        type=Path,
        help="Optional JSON split whose test_case_ids must not occur in SFT data.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU not found. Enable a GPU accelerator in Kaggle.")

    rows = read_jsonl(args.input)
    all_case_ids = sorted({case_id(row) for row in rows})
    if not 1 <= args.validation_cases < len(all_case_ids):
        raise ValueError(
            f"validation-cases must be between 1 and {len(all_case_ids) - 1}"
        )

    forbidden_cases = load_forbidden_cases(args.external_test_split)
    leakage = sorted(set(all_case_ids) & forbidden_cases)
    if leakage:
        raise ValueError(f"External-test leakage detected: {leakage}")

    shuffled_cases = list(all_case_ids)
    random.Random(args.seed).shuffle(shuffled_cases)
    validation_case_ids = set(shuffled_cases[: args.validation_cases])
    training_case_ids = set(shuffled_cases[args.validation_cases :])

    train_rows = [row for row in rows if case_id(row) in training_case_ids]
    validation_rows = [
        row for row in rows if case_id(row) in validation_case_ids
    ]
    if not train_rows or not validation_rows:
        raise ValueError("The case-level split produced an empty partition.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir = args.output_dir / "data_audit"
    write_jsonl(audit_dir / "train_source.jsonl", train_rows)
    write_jsonl(audit_dir / "validation_source.jsonl", validation_rows)

    split_manifest = {
        "seed": args.seed,
        "source": str(args.input),
        "total_examples": len(rows),
        "total_cases": len(all_case_ids),
        "train_examples": len(train_rows),
        "validation_examples": len(validation_rows),
        "train_case_ids": sorted(training_case_ids),
        "validation_case_ids": sorted(validation_case_ids),
        "forbidden_external_test_case_ids": sorted(forbidden_cases),
        "external_test_overlap": leakage,
    }
    (audit_dir / "split_manifest.json").write_text(
        json.dumps(split_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    train_dataset = Dataset.from_list(
        [to_prompt_completion(row) for row in train_rows]
    )
    validation_dataset = Dataset.from_list(
        [to_prompt_completion(row) for row in validation_rows]
    )

    use_bf16 = torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if use_bf16 else torch.float16
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=quantization_config,
        device_map={"": 0},
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    training_args = SFTConfig(
        output_dir=str(args.output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        weight_decay=0.01,
        max_grad_norm=1.0,
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=10,
        save_strategy="steps",
        save_steps=10,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        max_length=args.max_length,
        completion_only_loss=True,
        eos_token="<|im_end|>",
        packing=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        fp16=not use_bf16,
        bf16=use_bf16,
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        processing_class=tokenizer,
        peft_config=lora_config,
    )
    train_result = trainer.train()

    adapter_dir = args.output_dir / "final_adapter"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(adapter_dir)
    trainer.save_metrics("train", train_result.metrics)
    eval_metrics = trainer.evaluate()
    trainer.save_metrics("eval", eval_metrics)
    trainer.save_state()

    summary = {
        **split_manifest,
        "model": args.model,
        "output_dir": str(args.output_dir),
        "adapter_dir": str(adapter_dir),
        "epochs": args.epochs,
        "max_length": args.max_length,
        "learning_rate": args.learning_rate,
        "bf16": use_bf16,
        "gpu": torch.cuda.get_device_name(0),
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_metrics,
    }
    (args.output_dir / "training_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
