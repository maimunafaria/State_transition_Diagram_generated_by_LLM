# LLM-as-a-Judge Results

This directory contains the final reference-free LLM judgements for 97 unique
PlantUML state-transition diagrams that passed syntactic and strict structural
validation.

## Files

- `llm_judge_scores_final97.csv`: 291 final judgement records (97 diagrams
  evaluated independently by three judges). It includes the four Likert scores,
  concise feedback, diagram identifiers, generator metadata, judge model tags,
  model digests, and prompt versions.
- `llm_inter_judge_agreement.csv`: pairwise agreement metrics calculated only
  from the three LLM judges' scores.
- `experiment_manifest.json`: judge models, immutable Ollama digests, inference
  parameters, prompt versions, and record counts.

## Judges

- `deepseek-r1:14b`
- `llama3.1:8b-instruct-q4_K_M`
- `ggozad/prometheus2`

All evaluations were reference-free and inference-only. Each judge scored
completeness, correctness, understandability, and terminological alignment on a
1--5 Likert scale.

No human ratings, human consensus scores, human--LLM agreement results, or
personally identifying evaluator information are included in this package.
