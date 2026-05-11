# Structural Validity RQ Analysis

Compared methods: Zero-shot, Few-shot, RAG.

Structural validity and violation counts are computed only on diagrams that passed PlantUML syntax checking.

## PlantUML Syntax Validity
| method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- |
| Few-shot | 108 | 101 | 7 | 93.52 |
| RAG | 108 | 97 | 11 | 89.81 |
| Zero-shot | 108 | 31 | 77 | 28.7 |

## Structural Validity on PlantUML-Valid Diagrams
| method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- |
| Few-shot | 101 | 19 | 82 | 18.81 |
| RAG | 97 | 18 | 79 | 18.56 |
| Zero-shot | 31 | 0 | 31 | 0.0 |

## Violation Counts
| method | plantuml_valid_diagrams | mean_violations | median_violations | max_violations | zero_violation_diagrams |
| --- | --- | --- | --- | --- | --- |
| Few-shot | 101 | 1.5248 | 1 | 14 | 19 |
| RAG | 97 | 1.5773 | 1 | 9 | 18 |
| Zero-shot | 31 | 2.2581 | 2 | 3 | 0 |

## Statistical Tests
| df | methods | metric | n_by_method | note | p_value | statistic | table_valid_invalid | test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | Few-shot;RAG;Zero-shot | PlantUML syntax validity |  |  | <1e-8 | 138.089083 | 101/7;97/11;31/77 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural validity |  |  | 0.0315612 | 6.911653 | 19/82;18/79;0/31 | chi-square independence |
| 2 | Few-shot;RAG;Zero-shot | Structural violation count | Few-shot:101;RAG:97;Zero-shot:31 |  | 0.0000151 | 22.202116 |  | Kruskal-Wallis |

## Target Method Error Delta
Negative delta means the target method has lower violation frequency than the reference method. Positive delta means the target method has higher violation frequency.

| target_method | reference_method | violation_type | target_frequency_percent | reference_frequency_percent | delta_percentage_points | status |
| --- | --- | --- | --- | --- | --- | --- |
| RAG | Zero-shot | duplicate_transitions | 11.34 | 9.68 | 1.66 | increased_by_target |
| RAG | Zero-shot | invalid_choice_guards | 22.68 | 0.0 | 22.68 | introduced_by_target |
| RAG | Zero-shot | invalid_choice_node | 11.34 | 0.0 | 11.34 | introduced_by_target |
| RAG | Zero-shot | missing_final_state | 42.27 | 100.0 | -57.73 | mitigated_by_target |
| RAG | Zero-shot | missing_initial_state | 7.22 | 74.19 | -66.97 | mitigated_by_target |
| RAG | Zero-shot | multiple_initial_states | 34.02 | 3.23 | 30.79 | increased_by_target |
| RAG | Zero-shot | orphan_states | 11.34 | 32.26 | -20.92 | mitigated_by_target |
| RAG | Zero-shot | parse_warning | 2.06 | 0.0 | 2.06 | introduced_by_target |
| RAG | Zero-shot | unreachable_states | 15.46 | 6.45 | 9.01 | increased_by_target |
| RAG | Few-shot | duplicate_transitions | 11.34 | 5.94 | 5.4 | increased_by_target |
| RAG | Few-shot | invalid_choice_guards | 22.68 | 7.92 | 14.76 | increased_by_target |
| RAG | Few-shot | invalid_choice_node | 11.34 | 16.83 | -5.49 | mitigated_by_target |
| RAG | Few-shot | missing_final_state | 42.27 | 51.49 | -9.22 | mitigated_by_target |
| RAG | Few-shot | missing_initial_state | 7.22 | 11.88 | -4.66 | mitigated_by_target |
| RAG | Few-shot | multiple_initial_states | 34.02 | 5.94 | 28.08 | increased_by_target |
| RAG | Few-shot | orphan_states | 11.34 | 13.86 | -2.52 | mitigated_by_target |
| RAG | Few-shot | parse_warning | 2.06 | 0.0 | 2.06 | introduced_by_target |
| RAG | Few-shot | unreachable_states | 15.46 | 38.61 | -23.15 | mitigated_by_target |

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
