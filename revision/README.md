# Revision Scripts

Python scripts produced for the BioNLP 2026 revision round. All three are deterministic given the cached inputs in `../results/` and `../corrections/`. Only `run_haiku_experiments.py` calls a paid API.

```bash
pip install -r requirements.txt
```

## stats_compute.py

Computes the binomial tests, Clopper–Pearson 95% CIs, and the debatable-cases sensitivity analysis used in the paper:

- Two-sided + one-sided binomial test on the 9-of-11 SUPPORT-mislabel directional asymmetry.
- 95% CIs on the dev (11/209) and train (13/564) error rates.
- 95% CI on the 9/11 SUPPORT-error proportion.
- Three-scenario sensitivity table: 0/10, 5/10, 10/10 reclassification of the original 10 borderline cases (with the historical caveat that 2 of the 10 were upgraded to confirmed errors and are part of the 11/209 figure — see [`outputs/debatable_cases_appendix.md`](outputs/debatable_cases_appendix.md)).

```bash
python3 stats_compute.py
```

Reads:
- `../corrections/dev_corrections.json`
- `../results/stage2_manual_review/scifact_false_alarms_25_review.csv`
- `../results/stage2_manual_review/scifact_false_alarms_remaining_24_review.csv`

The pre-computed result is in [`outputs/stats_results.md`](outputs/stats_results.md).

## build_packets.py

Builds the two annotation CSVs released for the inter-annotator-agreement and false-negative-rate audits. Deterministic with `seed=42`.

```bash
python3 build_packets.py
```

Reads:
- `../data/scifact/claims_dev.jsonl` and `../data/scifact/corpus.jsonl` (run `bash data/download_scifact.sh` first)
- `../results/stage1_llm_screen/scifact_audit_gpt-5.4-mini_n209_*.json`
- `../corrections/dev_corrections.json`

Writes (overwriting):
- `../annotator_packets/blind_annotator_packet_dev.csv`
- `../annotator_packets/blind_annotator_packet_dev_unblinding_key.csv`
- `../annotator_packets/llm_rejected_random_sample_30.csv`

## run_haiku_experiments.py

Runs the Claude Haiku 4.5 cross-model F1 verification + claim-only contamination probe. Requires `CLAUDE_API_KEY` in the environment.

```bash
export CLAUDE_API_KEY=sk-ant-...
python3 run_haiku_experiments.py
```

Reads:
- `../data/scifact/claims_dev.jsonl` and `../data/scifact/corpus.jsonl`
- `../corrections/dev_corrections.json`

Writes:
- `../results/stage3_revision/haiku_f1_n209_dev.json`
- `../results/stage3_revision/contamination_probe_haiku.json`

**Cost:** approximately $0.54 (verified) for both experiments combined. The script uses 20-way concurrent async with structured tool-use output and prompt caching on the system prompt.

## outputs/

Pre-computed reports (reproduce with the scripts above):

- [`outputs/stats_results.md`](outputs/stats_results.md) — every binomial test and CI in the paper.
- [`outputs/haiku_results.md`](outputs/haiku_results.md) — Haiku 4.5 cross-model F1 + contamination-probe summary.
- [`outputs/debatable_cases_appendix.md`](outputs/debatable_cases_appendix.md) — case-by-case detail on the 10 originally-debatable cases (8 final).
