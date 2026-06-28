# Results and Analysis Chapter Notes

## Included scope
- Base methods: Qwen RAG, Mistral RAG, DeepSeek Few-shot, and Llama Few-shot
- Repair methods: Baseline Repair and Syntax-Grounded Repair
- Strict syntax + structural validity
- Relaxed semantic state F1
- Stability across three independent runs
- Human-vs-LLM judge experiment setup (final agreement results can be inserted later)
- Repair error analysis

## Key numerical findings

### Strict syntax + structural validity
- DeepSeek R1 14B: base 22.22%, baseline repair 88.89%, syntax-grounded repair 81.48%.
- Llama 3.1 8B: base 29.63%, baseline repair 55.56%, syntax-grounded repair 62.96%.
- Mistral 7B: base 14.81%, baseline repair 29.63%, syntax-grounded repair 37.04%.
- Qwen 2.5 7B: base 14.81%, baseline repair 40.74%, syntax-grounded repair 51.85%.

### Relaxed semantic state F1
- DeepSeek R1 14B: base 0.478, baseline repair 0.479, syntax-grounded repair 0.507.
- Llama 3.1 8B: base 0.535, baseline repair 0.526, syntax-grounded repair 0.534.
- Mistral 7B: base 0.426, baseline repair 0.420, syntax-grounded repair 0.455.
- Qwen 2.5 7B: base 0.584, baseline repair 0.583, syntax-grounded repair 0.577.

### Stability (base methods across 3 runs)
- DeepSeek R1 14B: mean state F1 0.420, run-level SD 0.066, mean case-wise SD 0.142, syntax consistency 100.00%, structural consistency 0.00%.
- Llama 3.1 8B: mean state F1 0.528, run-level SD 0.005, mean case-wise SD 0.092, syntax consistency 100.00%, structural consistency 25.93%.
- Mistral 7B: mean state F1 0.390, run-level SD 0.041, mean case-wise SD 0.158, syntax consistency 100.00%, structural consistency 55.56%.
- Qwen 2.5 7B: mean state F1 0.507, run-level SD 0.073, mean case-wise SD 0.111, syntax consistency 100.00%, structural consistency 37.04%.

### Error analysis
- Missing final transition: baseline 81.63% vs syntax-grounded 77.55% (better: Baseline).
- Missing initial transition: baseline 71.43% vs syntax-grounded 78.57% (better: Syntax-Grounded).
- Multiple initial transitions: baseline 20.00% vs syntax-grounded 40.00% (better: Syntax-Grounded).
- Unreachable states: baseline 42.11% vs syntax-grounded 57.89% (better: Syntax-Grounded).
- Orphan states: baseline 42.86% vs syntax-grounded 100.00% (better: Syntax-Grounded).
- PlantUML syntax error: baseline 16.67% vs syntax-grounded 25.00% (better: Syntax-Grounded).
- Duplicate transitions: baseline 70.00% vs syntax-grounded 60.00% (better: Baseline).
- Choice without outgoing paths: baseline 50.00% vs syntax-grounded 30.00% (better: Baseline).
- Choice without guards: baseline 33.33% vs syntax-grounded 83.33% (better: Syntax-Grounded).
- Invalid [*] to [*] transition: baseline 50.00% vs syntax-grounded 100.00% (better: Syntax-Grounded).

### Human/LLM judge dataset preparation
- Final valid set after removing repair diagrams that overlap with already-valid raw diagrams: 99 diagrams.
- Diagrams with at least two human ratings currently available: 58.
- Diagrams still missing 2-human coverage: 41.

## Suggested figures
1. `figure_01_validity_base_vs_repairs.png`: strict syntax + structural validity across base and repair methods.
2. `figure_02_relaxed_state_f1_base_vs_repairs.png`: relaxed semantic state F1 across base and repair methods.
3. `figure_03_stability_mean_state_f1.png`: mean state F1 with run-level standard deviation.
4. `figure_04_stability_consistency.png`: syntax and structural consistency percentages across runs.
5. `figure_05_error_resolution_by_type.png`: repair success by structural error type.
6. `figure_06_valid99_human_coverage.png`: composition of the final valid human/LLM evaluation set.

## Figure captions draft
- Figure 1. Strict syntax and structural validity percentages for the four selected LLMs under the base, baseline repair, and syntax-grounded repair settings.
- Figure 2. Mean relaxed semantic state F1 for the same four LLMs before and after repair.
- Figure 3. Mean semantic state F1 across three independent runs, with error bars showing run-level standard deviation.
- Figure 4. Percentage of cases whose syntax-validity and structural-validity outcomes remained consistent across three runs.
- Figure 5. Error-type-wise repair success rates for baseline and syntax-grounded repair.
- Figure 6. Final composition of the 99-diagram human/LLM judge comparison subset.

