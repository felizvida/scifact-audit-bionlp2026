# Cached Stage-by-Stage Outputs

Each subdirectory holds a frozen artifact from one stage of the audit, so downstream stages can be reproduced without re-running the previous step (and without paying for repeated API calls).

## stage1_llm_screen/

GPT-5.4 outputs from the original audit run on the 209 SciFact dev pairs with gold evidence.

- `scifact_audit_gpt-5.4-mini_n209_2026-04-02T14-33-55.931576Z.json` — the **screen** itself: per-pair AGREE / DISAGREE / DEBATABLE assessment, reasoning, error type, suggested correct label. This is the file that downstream stages consume to identify which pairs to triage manually.
- `scifact_single_gpt-5.4-mini_n209_2026-04-02T12-13-29-668788Z.json` — zero-shot binary SUPPORT/CONTRADICT predictions used for the F1-impact analysis (84.9 → 88.7).
- `scifact_single_gpt-5.4-nano_n209_2026-04-02T12-08-39-098809Z.json` — same, GPT-5.4-nano predictions (79.5 → 81.2).

Each file embeds the full prompt template and per-call usage, so the operating point is fully recoverable.

## stage2_manual_review/

Manual triage CSVs produced when the human annotator (assisted by frontier GPT-5.4 in chat) reviewed each of the 57 mini-flagged disagreements:

- `scifact_audit_disagree_43.csv` and `scifact_audit_disagree_43_with_evidence.csv` — the 43 DISAGREE cases from the screen, with the LLM's reasoning and a column for the manual verdict.
- `scifact_false_alarms_25_review.csv` and `scifact_false_alarms_remaining_24_review.csv` — the cases initially classified as false alarms (`my_verdict == "FALSE_ALARM"`) plus those marked `DEBATABLE` for the second-pass review.

Rows where `my_verdict == "DEBATABLE"` are the 10 originally-debatable cases discussed in Appendix A of the paper (8 of which remained debatable after second-pass review; 2 — claims 847 and 1274 — were upgraded to confirmed errors).

## stage3_revision/

BioNLP-revision experiments (see `revision/run_haiku_experiments.py` for the script that produced these):

- `haiku_f1_n209_dev.json` — Claude Haiku 4.5 zero-shot 3-way predictions on all 209 dev pairs. Binary macro F1: 92.77 → 95.75 (Δ +2.98). 3-way macro F1: 61.85 → 71.09 (Δ +9.24).
- `contamination_probe_haiku.json` — Claude Haiku 4.5 zero-shot predictions given **only** the claim text (no abstract, no rationale). Accuracy 70.81% vs majority-class baseline 66.03% (gap +4.78), with 18% of predictions being NEI. The small gap above majority class argues against label memorization.

Both Haiku-output files include the per-pair predictions, the system and user prompts, token usage, and a metrics block. Total cost of producing both files: USD $0.54.
