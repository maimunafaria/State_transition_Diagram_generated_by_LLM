# Human Evaluation Likert Analysis

Input rows: 166 evaluator responses.

Recommended reporting: medians and IQR for Likert scores, 100% stacked Likert distributions, Kruskal-Wallis tests, and Dunn-Holm posthoc comparisons only when Kruskal-Wallis is significant.

Generated files:
- `descriptive_stats_by_method.csv`
- `descriptive_stats_by_llm_used.csv`
- `likert_distribution_by_method.csv`
- `likert_distribution_by_llm_used.csv`
- `kruskal_wallis_by_method.csv`
- `kruskal_wallis_by_llm_used.csv`
- `dunn_posthoc_by_method.csv`
- `dunn_posthoc_by_llm_used.csv`
- `charts/*.svg`

Interpretation note: means are included only as supplementary descriptive values; medians and IQR are preferable for Likert-scale data.
