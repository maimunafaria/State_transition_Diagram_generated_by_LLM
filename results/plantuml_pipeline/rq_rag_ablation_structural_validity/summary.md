# Structural Validity RQ Analysis

Compared methods: RAG, RAG [examples only], RAG [rules only], RAG [theory only].

Structural validity and violation counts are computed only on diagrams that passed PlantUML syntax checking.

## PlantUML Syntax Validity
| method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- |
| RAG | 108 | 97 | 11 | 89.81 |
| RAG [examples only] | 108 | 95 | 13 | 87.96 |
| RAG [rules only] | 108 | 83 | 25 | 76.85 |
| RAG [theory only] | 108 | 70 | 38 | 64.81 |

## Structural Validity on PlantUML-Valid Diagrams
| method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- |
| RAG | 97 | 18 | 79 | 18.56 |
| RAG [examples only] | 95 | 10 | 85 | 10.53 |
| RAG [rules only] | 83 | 25 | 58 | 30.12 |
| RAG [theory only] | 70 | 2 | 68 | 2.86 |

## Violation Counts
| method | plantuml_valid_diagrams | mean_violations | median_violations | max_violations | zero_violation_diagrams |
| --- | --- | --- | --- | --- | --- |
| RAG | 97 | 1.5773 | 1 | 9 | 18 |
| RAG [examples only] | 95 | 2.0211 | 2 | 13 | 10 |
| RAG [rules only] | 83 | 1.0723 | 1 | 3 | 25 |
| RAG [theory only] | 70 | 1.4143 | 1.0 | 3 | 2 |

## Statistical Tests
| df | methods | metric | n_by_method | note | p_value | statistic | table_valid_invalid | test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | PlantUML syntax validity |  |  | 0.00000626 | 26.871364 | 97/11;95/13;83/25;70/38 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural validity |  |  | 0.00002535 | 23.969062 | 18/79;10/85;25/58;2/68 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural violation count | RAG:97;RAG [examples only]:95;RAG [rules only]:83;RAG [theory only]:70 |  | 0.0000757 | 21.689267 |  | Kruskal-Wallis |

## Target Method Error Delta
Negative delta means the target method has lower violation frequency than the reference method. Positive delta means the target method has higher violation frequency.

| target_method | reference_method | violation_type | target_frequency_percent | reference_frequency_percent | delta_percentage_points | status |
| --- | --- | --- | --- | --- | --- | --- |
| RAG | RAG [examples only] | duplicate_transitions | 11.34 | 5.26 | 6.08 | increased_by_target |
| RAG | RAG [examples only] | invalid_choice_guards | 22.68 | 37.89 | -15.21 | mitigated_by_target |
| RAG | RAG [examples only] | invalid_choice_node | 11.34 | 25.26 | -13.92 | mitigated_by_target |
| RAG | RAG [examples only] | missing_final_state | 42.27 | 53.68 | -11.41 | mitigated_by_target |
| RAG | RAG [examples only] | missing_initial_state | 7.22 | 10.53 | -3.31 | mitigated_by_target |
| RAG | RAG [examples only] | multiple_initial_states | 34.02 | 13.68 | 20.34 | increased_by_target |
| RAG | RAG [examples only] | orphan_states | 11.34 | 23.16 | -11.82 | mitigated_by_target |
| RAG | RAG [examples only] | parse_warning | 2.06 | 0.0 | 2.06 | introduced_by_target |
| RAG | RAG [examples only] | unreachable_states | 15.46 | 32.63 | -17.17 | mitigated_by_target |
| RAG | RAG [rules only] | duplicate_transitions | 11.34 | 2.41 | 8.93 | increased_by_target |
| RAG | RAG [rules only] | invalid_choice_guards | 22.68 | 0.0 | 22.68 | introduced_by_target |
| RAG | RAG [rules only] | invalid_choice_node | 11.34 | 0.0 | 11.34 | introduced_by_target |
| RAG | RAG [rules only] | missing_final_state | 42.27 | 43.37 | -1.1 | mitigated_by_target |
| RAG | RAG [rules only] | missing_initial_state | 7.22 | 16.87 | -9.65 | mitigated_by_target |
| RAG | RAG [rules only] | multiple_initial_states | 34.02 | 24.1 | 9.92 | increased_by_target |
| RAG | RAG [rules only] | orphan_states | 11.34 | 9.64 | 1.7 | increased_by_target |
| RAG | RAG [rules only] | parse_warning | 2.06 | 0.0 | 2.06 | introduced_by_target |
| RAG | RAG [rules only] | unreachable_states | 15.46 | 10.84 | 4.62 | increased_by_target |
| RAG | RAG [theory only] | duplicate_transitions | 11.34 | 1.43 | 9.91 | increased_by_target |
| RAG | RAG [theory only] | invalid_choice_guards | 22.68 | 0.0 | 22.68 | introduced_by_target |
| RAG | RAG [theory only] | invalid_choice_node | 11.34 | 0.0 | 11.34 | introduced_by_target |
| RAG | RAG [theory only] | missing_final_state | 42.27 | 94.29 | -52.02 | mitigated_by_target |
| RAG | RAG [theory only] | missing_initial_state | 7.22 | 30.0 | -22.78 | mitigated_by_target |
| RAG | RAG [theory only] | multiple_initial_states | 34.02 | 2.86 | 31.16 | increased_by_target |
| RAG | RAG [theory only] | orphan_states | 11.34 | 4.29 | 7.05 | increased_by_target |
| RAG | RAG [theory only] | parse_warning | 2.06 | 0.0 | 2.06 | introduced_by_target |
| RAG | RAG [theory only] | unreachable_states | 15.46 | 8.57 | 6.89 | increased_by_target |

## By LLM: PlantUML Syntax Validity
| model | method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | RAG | 27 | 23 | 4 | 85.19 |
| DeepSeek R1 14B | RAG [examples only] | 27 | 20 | 7 | 74.07 |
| DeepSeek R1 14B | RAG [rules only] | 27 | 22 | 5 | 81.48 |
| DeepSeek R1 14B | RAG [theory only] | 27 | 17 | 10 | 62.96 |
| Llama 3.1 8B Instruct | RAG | 27 | 27 | 0 | 100.0 |
| Llama 3.1 8B Instruct | RAG [examples only] | 27 | 26 | 1 | 96.3 |
| Llama 3.1 8B Instruct | RAG [rules only] | 27 | 21 | 6 | 77.78 |
| Llama 3.1 8B Instruct | RAG [theory only] | 27 | 24 | 3 | 88.89 |
| Mistral | RAG | 27 | 20 | 7 | 74.07 |
| Mistral | RAG [examples only] | 27 | 24 | 3 | 88.89 |
| Mistral | RAG [rules only] | 27 | 18 | 9 | 66.67 |
| Mistral | RAG [theory only] | 27 | 7 | 20 | 25.93 |
| Qwen 2.5 7B Instruct | RAG | 27 | 27 | 0 | 100.0 |
| Qwen 2.5 7B Instruct | RAG [examples only] | 27 | 25 | 2 | 92.59 |
| Qwen 2.5 7B Instruct | RAG [rules only] | 27 | 22 | 5 | 81.48 |
| Qwen 2.5 7B Instruct | RAG [theory only] | 27 | 22 | 5 | 81.48 |

## By LLM: Structural Validity on PlantUML-Valid Diagrams
| model | method | total | valid | invalid | validity_percent |
| --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | RAG | 23 | 4 | 19 | 17.39 |
| DeepSeek R1 14B | RAG [examples only] | 20 | 2 | 18 | 10.0 |
| DeepSeek R1 14B | RAG [rules only] | 22 | 4 | 18 | 18.18 |
| DeepSeek R1 14B | RAG [theory only] | 17 | 0 | 17 | 0.0 |
| Llama 3.1 8B Instruct | RAG | 27 | 6 | 21 | 22.22 |
| Llama 3.1 8B Instruct | RAG [examples only] | 26 | 4 | 22 | 15.38 |
| Llama 3.1 8B Instruct | RAG [rules only] | 21 | 9 | 12 | 42.86 |
| Llama 3.1 8B Instruct | RAG [theory only] | 24 | 1 | 23 | 4.17 |
| Mistral | RAG | 20 | 4 | 16 | 20.0 |
| Mistral | RAG [examples only] | 24 | 1 | 23 | 4.17 |
| Mistral | RAG [rules only] | 18 | 1 | 17 | 5.56 |
| Mistral | RAG [theory only] | 7 | 0 | 7 | 0.0 |
| Qwen 2.5 7B Instruct | RAG | 27 | 4 | 23 | 14.81 |
| Qwen 2.5 7B Instruct | RAG [examples only] | 25 | 3 | 22 | 12.0 |
| Qwen 2.5 7B Instruct | RAG [rules only] | 22 | 11 | 11 | 50.0 |
| Qwen 2.5 7B Instruct | RAG [theory only] | 22 | 1 | 21 | 4.55 |

## By LLM: Violation Counts
| model | method | plantuml_valid_diagrams | mean_violations | median_violations | max_violations | zero_violation_diagrams |
| --- | --- | --- | --- | --- | --- | --- |
| DeepSeek R1 14B | RAG | 23 | 1.9565 | 1 | 9 | 4 |
| DeepSeek R1 14B | RAG [examples only] | 20 | 1.6 | 1.5 | 4 | 2 |
| DeepSeek R1 14B | RAG [rules only] | 22 | 1.3636 | 2.0 | 2 | 4 |
| DeepSeek R1 14B | RAG [theory only] | 17 | 1.6471 | 2 | 2 | 0 |
| Llama 3.1 8B Instruct | RAG | 27 | 1.3704 | 1 | 6 | 6 |
| Llama 3.1 8B Instruct | RAG [examples only] | 26 | 1.9615 | 2.0 | 6 | 4 |
| Llama 3.1 8B Instruct | RAG [rules only] | 21 | 0.7143 | 1 | 3 | 9 |
| Llama 3.1 8B Instruct | RAG [theory only] | 24 | 1 | 1.0 | 2 | 1 |
| Mistral | RAG | 20 | 1.6 | 1.0 | 5 | 4 |
| Mistral | RAG [examples only] | 24 | 2.5417 | 2.0 | 13 | 1 |
| Mistral | RAG [rules only] | 18 | 1.7222 | 1.0 | 3 | 1 |
| Mistral | RAG [theory only] | 7 | 2.2857 | 2 | 3 | 0 |
| Qwen 2.5 7B Instruct | RAG | 27 | 1.4444 | 1 | 3 | 4 |
| Qwen 2.5 7B Instruct | RAG [examples only] | 25 | 1.92 | 2 | 6 | 3 |
| Qwen 2.5 7B Instruct | RAG [rules only] | 22 | 0.5909 | 0.5 | 2 | 11 |
| Qwen 2.5 7B Instruct | RAG [theory only] | 22 | 1.4091 | 1.0 | 3 | 1 |

## By LLM: Statistical Tests
| df | methods | metric | model | n_by_method | note | p_value | statistic | table_valid_invalid | test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | PlantUML syntax validity | DeepSeek R1 14B |  |  | 0.23519707 | 4.255159 | 23/4;20/7;22/5;17/10 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural validity | DeepSeek R1 14B |  |  | 0.28769778 | 3.767426 | 4/19;2/18;4/18;0/17 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural violation count | DeepSeek R1 14B | RAG:23;RAG [examples only]:20;RAG [rules only]:22;RAG [theory only]:17 |  | 0.83118993 | 0.876106 |  | Kruskal-Wallis |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | PlantUML syntax validity | Llama 3.1 8B Instruct |  |  | 0.02606037 | 9.257143 | 27/0;26/1;21/6;24/3 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural validity | Llama 3.1 8B Instruct |  |  | 0.01244099 | 10.871573 | 6/21;4/22;9/12;1/23 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural violation count | Llama 3.1 8B Instruct | RAG:27;RAG [examples only]:26;RAG [rules only]:21;RAG [theory only]:24 |  | 0.00301762 | 13.918917 |  | Kruskal-Wallis |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | PlantUML syntax validity | Mistral |  |  | 0.00001222 | 25.48495 | 20/7;24/3;18/9;7/20 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural validity | Mistral |  |  | 0.19272678 | 4.729299 | 4/16;1/23;1/17;0/7 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural violation count | Mistral | RAG:20;RAG [examples only]:24;RAG [rules only]:18;RAG [theory only]:7 |  | 0.21472687 | 4.472827 |  | Kruskal-Wallis |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | PlantUML syntax validity | Qwen 2.5 7B Instruct |  |  | 0.08030773 | 6.75 | 27/0;25/2;22/5;22/5 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural validity | Qwen 2.5 7B Instruct |  |  | 0.00062918 | 17.245388 | 4/23;3/22;11/11;1/21 | chi-square independence |
| 3 | RAG;RAG [examples only];RAG [rules only];RAG [theory only] | Structural violation count | Qwen 2.5 7B Instruct | RAG:27;RAG [examples only]:25;RAG [rules only]:22;RAG [theory only]:22 |  | 0.00018556 | 19.813242 |  | Kruskal-Wallis |
