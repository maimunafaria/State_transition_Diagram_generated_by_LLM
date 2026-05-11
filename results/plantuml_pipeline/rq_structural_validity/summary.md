# Structural Validity RQ Analysis

Compared methods: Zero-shot, Few-shot, RAG.

Structural validity and violation counts are computed only on diagrams that passed PlantUML syntax checking.

## By LLM: PlantUML Syntax Validity
| model | method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | Few-shot | 27 | 24 | 3 | 88.89 |
| DeepSeek R1 14B | RAG | 27 | 23 | 4 | 85.19 |
| DeepSeek R1 14B | Zero-shot | 27 | 16 | 11 | 59.26 |
| Llama 3.1 8B Instruct | Few-shot | 27 | 25 | 2 | 92.59 |
| Llama 3.1 8B Instruct | RAG | 27 | 27 | 0 | 100.0 |
| Llama 3.1 8B Instruct | Zero-shot | 27 | 8 | 19 | 29.63 |
| Mistral | Few-shot | 27 | 26 | 1 | 96.3 |
| Mistral | RAG | 27 | 20 | 7 | 74.07 |
| Mistral | Zero-shot | 27 | 1 | 26 | 3.7 |
| Qwen 2.5 7B Instruct | Few-shot | 27 | 26 | 1 | 96.3 |
| Qwen 2.5 7B Instruct | RAG | 27 | 27 | 0 | 100.0 |
| Qwen 2.5 7B Instruct | Zero-shot | 27 | 6 | 21 | 22.22 |

## By LLM: Structural Validity on PlantUML-Valid Diagrams
| model | method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | Few-shot | 24 | 6 | 18 | 25.0 |
| DeepSeek R1 14B | RAG | 23 | 4 | 19 | 17.39 |
| DeepSeek R1 14B | Zero-shot | 16 | 0 | 16 | 0.0 |
| Llama 3.1 8B Instruct | Few-shot | 25 | 8 | 17 | 32.0 |
| Llama 3.1 8B Instruct | RAG | 27 | 6 | 21 | 22.22 |
| Llama 3.1 8B Instruct | Zero-shot | 8 | 0 | 8 | 0.0 |
| Mistral | Few-shot | 26 | 2 | 24 | 7.69 |
| Mistral | RAG | 20 | 4 | 16 | 20.0 |
| Mistral | Zero-shot | 1 | 0 | 1 | 0.0 |
| Qwen 2.5 7B Instruct | Few-shot | 26 | 3 | 23 | 11.54 |
| Qwen 2.5 7B Instruct | RAG | 27 | 4 | 23 | 14.81 |
| Qwen 2.5 7B Instruct | Zero-shot | 6 | 0 | 6 | 0.0 |

## By LLM: Violation Counts
| model | method | plantuml_valid_diagrams | mean_violations | median_violations | max_violations | zero_violation_diagrams |
| --- | --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | Few-shot | 24 | 1.125 | 1.0 | 4 | 6 |
| DeepSeek R1 14B | RAG | 23 | 1.9565 | 1 | 9 | 4 |
| DeepSeek R1 14B | Zero-shot | 16 | 2.0625 | 2.0 | 3 | 0 |
| Llama 3.1 8B Instruct | Few-shot | 25 | 1.64 | 1 | 14 | 8 |
| Llama 3.1 8B Instruct | RAG | 27 | 1.3704 | 1 | 6 | 6 |
| Llama 3.1 8B Instruct | Zero-shot | 8 | 2 | 2.0 | 3 | 0 |
| Mistral | Few-shot | 26 | 1.8077 | 2.0 | 5 | 2 |
| Mistral | RAG | 20 | 1.6 | 1.0 | 5 | 4 |
| Mistral | Zero-shot | 1 | 3 | 3 | 3 | 0 |
| Qwen 2.5 7B Instruct | Few-shot | 26 | 1.5 | 1.0 | 4 | 3 |
| Qwen 2.5 7B Instruct | RAG | 27 | 1.4444 | 1 | 3 | 4 |
| Qwen 2.5 7B Instruct | Zero-shot | 6 | 3 | 3.0 | 3 | 0 |

## By LLM: Statistical Tests
| df | methods | metric | model | n_by_method | note | p_value | statistic | table_valid_invalid | test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | Few-shot;RAG;Zero-shot | PlantUML syntax validity | DeepSeek R1 14B |  |  | 0.01705301 | 8.142857 | 24/3;23/4;16/11 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural validity | DeepSeek R1 14B |  |  | 0.10250218 | 4.555742 | 6/18;4/19;0/16 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural violation count | DeepSeek R1 14B | Few-shot:24;RAG:23;Zero-shot:16 |  | 0.00155622 | 12.930995 |  | Kruskal-Wallis |
| 2 | Few-shot;RAG;Zero-shot | PlantUML syntax validity | Llama 3.1 8B Instruct |  |  | <1e-8 | 42.042857 | 25/2;27/0;8/19 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural validity | Llama 3.1 8B Instruct |  |  | 0.17350432 | 3.503106 | 8/17;6/21;0/8 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural violation count | Llama 3.1 8B Instruct | Few-shot:25;RAG:27;Zero-shot:8 |  | 0.12054573 | 4.231452 |  | Kruskal-Wallis |
| 2 | Few-shot;RAG;Zero-shot | PlantUML syntax validity | Mistral |  |  | <1e-8 | 51.803504 | 26/1;20/7;1/26 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural validity | Mistral |  |  | 0.43016357 | 1.687179 | 2/24;4/16;0/1 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural violation count | Mistral | Few-shot:26;RAG:20;Zero-shot:1 |  | 0.35764506 | 2.056428 |  | Kruskal-Wallis |
| 2 | Few-shot;RAG;Zero-shot | PlantUML syntax validity | Qwen 2.5 7B Instruct |  |  | <1e-8 | 52.543914 | 26/1;27/0;6/21 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural validity | Qwen 2.5 7B Instruct |  |  | 0.59597895 | 1.0351 | 3/23;4/23;0/6 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural violation count | Qwen 2.5 7B Instruct | Few-shot:26;RAG:27;Zero-shot:6 |  | 0.001881 | 12.5519 |  | Kruskal-Wallis |
