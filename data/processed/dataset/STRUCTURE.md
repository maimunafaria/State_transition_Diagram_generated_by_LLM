# Dataset Folder Structure

This folder is organized for two workflows:
- Main datasets for training/evaluation
- One-file-per-entity inspection/editing

## Files and folders
- `dataset_2026-02-24.jsonl`: active working dataset (10 records)
- `dataset.jsonl`: original/legacy full dataset
- `dataset.json`: JSON array version of the legacy dataset
- `entities/`: one JSON per domain/entity
- `subsets/`: sampled subsets (for baselines, e.g., GPT-4o balanced subset)

## Current rule
- Add/update records in `dataset_2026-02-24.jsonl`
- Keep per-entity records in `entities/`
- Do not modify `dataset.jsonl` unless you explicitly want to refresh the legacy dataset
