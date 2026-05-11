# Repair Effectiveness Analysis

Repair success is final strict structural validity. Validity recovery is invalid-to-valid transition. Regression means the final diagram introduced at least one violation type not present initially.

## By LLM and Method
| model | method | total | repair_success_rate | structural_improvement_rate | validity_recovery_rate | regression_rate | mean_attempted_repair_iterations | mean_violation_reduction | mean_total_graph_change |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | Few-shot + Repair | 27 | 96.3 | 74.07 | 95.24 | 0.0 | 1.5185 | 1.1111 | 3.8148 |
| Llama 3.1 8B Instruct | Few-shot + Repair | 27 | 55.56 | 48.15 | 36.84 | 18.52 | 2.5556 | 4.3333 | 5.9259 |
| Mistral | RAG + Repair | 27 | 33.33 | 37.04 | 18.18 | 3.7 | 3.5185 | 0.5556 | 2.5926 |
| Qwen 2.5 7B Instruct | RAG + Repair | 27 | 40.74 | 48.15 | 30.43 | 3.7 | 3.3333 | 0.6296 | 1.2593 |
