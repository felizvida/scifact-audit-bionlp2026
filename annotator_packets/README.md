# Annotator Packets

Two artifacts released for independent re-audit work the paper recommends.

## Packet 1: Blind dev re-annotation

For computing inter-annotator agreement (Cohen's κ) against the original SciFact gold labels and against our 11 confirmed corrections.

- [`blind_annotator_packet_dev.csv`](blind_annotator_packet_dev.csv) — 209 rows, columns `pair_uid, claim, paper_title, full_abstract, gold_rationale, annotator_label, annotator_confidence, annotator_notes`. Order randomized with `seed=42`. **Critically: no `claim_id`, no original gold label, no LLM signal in the file the annotator sees.**
- [`blind_annotator_packet_dev_unblinding_key.csv`](blind_annotator_packet_dev_unblinding_key.csv) — the lookup table mapping `pair_uid` to `claim_id`, `doc_id`, `original_gold`, `llm_assessment`, and `is_confirmed_error_in_paper`. **The annotator must not see this file** — it's used after the annotation is complete to compute κ and per-stratum agreement (correct vs. error-flagged subsets).
- [`blind_annotator_instructions.md`](blind_annotator_instructions.md) — one-page brief for the annotator: definitions of SUPPORT / CONTRADICT / NEI, the DEBATABLE option, the "judge against the assigned evidence only" rule, estimated time (3–5 hours).

To regenerate (deterministically, in case the dataset is updated upstream):

```bash
python3 ../revision/build_packets.py
```

## Packet 2: LLM-rejected false-negative-rate audit

For estimating the FN rate of the GPT-5.4-mini screen. The paper currently reports recall 8/11 = 73% on the small confirmed-errors set; a random-sample audit on the 152 LLM-rejected (AGREE) pairs gives a tighter estimate.

- [`llm_rejected_random_sample_30.csv`](llm_rejected_random_sample_30.csv) — 30 rows randomly sampled from the 152 pairs the LLM auditor rated AGREE (`seed=42`). Columns include `claim_id`, `original_gold`, `llm_assessment` (`agree` for all), `claim`, `paper_title`, `full_abstract`, `gold_rationale`, plus blank `user_verdict` and `user_notes` columns.
- [`llm_rejected_sample_instructions.md`](llm_rejected_sample_instructions.md) — instructions: judge each pair against the assigned evidence, mark `confirmed` / `error` / `debatable`, then compute estimated FN rate as (errors found) / 30 with a Clopper–Pearson 95% CI.

This packet is **not blind** — the annotator sees the original gold label, since the question is whether the LLM correctly rejected an audit on this pair.
