# LLM-Rejected Random Sample: False-Negative Rate Audit

## Why this audit exists

Our submission's GPT-5.4-mini screening pass marked **152 of 209 dev pairs** as `agree` (i.e., the LLM accepted the original SciFact gold label and did not flag it as a candidate error). Of the remaining 57 pairs, 11 turned out to be confirmed gold-label errors after manual review.

Reviewer #3 correctly pointed out that we have only an *upper-bound* recall estimate from this design: the paper currently reports recall 8/11 against confirmed errors found via the LLM screen, but we have not measured the false-negative rate of the screen itself. Errors that the LLM wrongly accepted (`agree` when the gold label was in fact wrong) would never enter the candidate pool and would not be counted.

This sample lets us estimate that false-negative rate. If you find `K` confirmed errors out of 30 random `agree` pairs, the FN rate is roughly `K/30` with a Clopper-Pearson 95% CI; the paper's methodology section can then report a tighter bound on overall recall.

## What to do

1. Open `llm_rejected_random_sample_30.csv`.
2. For each row, read the claim, the paper title, the full abstract, and the gold rationale (the sentences SciFact's original annotators picked).
3. Decide whether the original SciFact gold label is correct **with respect to the paper's own evidence**.
4. Fill in `user_verdict`:
   - `confirmed` — the gold label is correct; the LLM was right to skip this pair.
   - `error` — the gold label is wrong; the LLM missed a real error. We have a new candidate gold-label error.
   - `debatable` — genuinely ambiguous (overgeneralization, imprecise wording, etc.).
5. Optional: fill `user_notes` with a one-sentence justification, especially for `error` and `debatable` verdicts.

## Ground rules

- **Not blind.** You see the original gold label and the LLM verdict (always `agree` here). That's intentional — this is a targeted FN check, not an inter-annotator agreement study.
- Judge against the assigned paper only. Do not search later literature.
- Use the same SUPPORT / CONTRADICT / NEI definitions as Wadden et al. (EMNLP 2020): see `blind_annotator_instructions.md` for the canonical definitions.
- Sample is drawn with `random.seed(42)`; if you want to expand to 60 or 100, the build script can re-sample reproducibly.

## After review

Counts feed directly into the paper's revised methodology paragraph. Paste the verdict tally back into the chat and we will:

1. Compute Clopper-Pearson 95% CI for FN rate `K/30`.
2. Update the methodology section with the new bound on overall recall.
3. Add any newly-confirmed errors to `dev_corrections.json` (with full justifications).

Estimated time: 30–60 minutes for 30 pairs.
