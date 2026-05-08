# Gold Label Errors in the SciFact Benchmark — Companion Repository

Companion artifacts for the BioNLP 2026 paper *Gold Label Errors in the SciFact Benchmark: An LLM-Assisted Annotation Audit* by Julien Sylvestre.

The paper identifies 11 gold-label errors in the SciFact dev set (5.3%, 95% CI 2.7–9.2%) and 13 in the training set (2.3%, 95% CI 1.2–3.9%), exhibits a directional asymmetry (9/11 mislabel SUPPORT; one-sided binomial p=0.033), and shows F1 deltas of 1.7–3.8 points across two model families (GPT-5.4 and Claude Haiku 4.5).

This repository releases the corrected annotations, the LLM screen outputs, the manual-review trail, the cross-model verification scripts, and a blind annotator packet for an independent multi-annotator re-audit.

## What you probably want

- **Just the corrected labels:** [`corrections/dev_corrections.json`](corrections/dev_corrections.json) and [`corrections/train_corrections.json`](corrections/train_corrections.json). 11 dev + 1 per-document + 13 train, with claim ID, original gold, corrected label, error type, and a one-line justification each. Schema documented in [`corrections/README.md`](corrections/README.md).
- **The paper PDF:** [`paper/scifact_audit_bionlp2026.pdf`](paper/scifact_audit_bionlp2026.pdf).
- **A blind 209-pair re-annotation packet** for inter-annotator agreement studies: [`annotator_packets/blind_annotator_packet_dev.csv`](annotator_packets/blind_annotator_packet_dev.csv) (instructions inline).

## Repository layout

```
.
├── paper/                 The camera-ready PDF, .tex source, .bib, ACL style files
├── corrections/           The headline output: corrected gold labels (JSON)
├── data/                  Helper to fetch SciFact (dataset itself not vendored)
├── audit/                 Stage 1 source: original Elixir LLM-screen code
├── results/               Cached outputs from each stage of the audit
│   ├── stage1_llm_screen/   GPT-5.4-mini audit JSON + per-pair predictions
│   ├── stage2_manual_review/ CSVs of the manual-triage step
│   └── stage3_revision/     Haiku 4.5 cross-model F1 + contamination probe
├── revision/              Python scripts for the BioNLP-revision experiments
│   ├── run_haiku_experiments.py   F1 on dev with Haiku 4.5 + contamination probe
│   ├── stats_compute.py           Binomial tests + Clopper–Pearson CIs + sensitivity
│   ├── build_packets.py           Builds the blind annotator packets
│   └── outputs/                   Pre-computed reports (stats, Haiku, debatables)
└── annotator_packets/     Blind dev-set packet + LLM-rejected FN-audit sample
```

## Reproducing the analysis

The original Stage-1 LLM screen used GPT-5.4-mini via Elixir; its raw output is in `results/stage1_llm_screen/` so you can skip Stage 1 and re-derive Stages 2–3 from the cached predictions.

### Stage 2 + 3 (Python — recommended for reproduction)

```bash
# 1. Fetch the SciFact dataset (~50 MB)
bash data/download_scifact.sh

# 2. Install Python deps
pip install -r revision/requirements.txt

# 3. Recompute the binomial tests, Clopper–Pearson CIs, and sensitivity table
python3 revision/stats_compute.py

# 4. Re-build the blind annotator packets (deterministic, seed=42)
python3 revision/build_packets.py

# 5. Re-run the Haiku 4.5 cross-model F1 + contamination probe (~$0.50 on Anthropic API)
export CLAUDE_API_KEY=sk-ant-...
python3 revision/run_haiku_experiments.py
```

`stats_compute.py` and `build_packets.py` are deterministic and offline; `run_haiku_experiments.py` is the only script that calls a paid API.

### Stage 1 (Elixir — original screen)

The original GPT-5.4-mini screen lives in `audit/elixir/`. It depends on the `colonyOS` umbrella's `ClaimVerifier` and Elixir runtime infrastructure that is not vendored here; the cached JSON output (`results/stage1_llm_screen/scifact_audit_gpt-5.4-mini_n209_*.json`) contains the screen verdicts, per-pair reasoning, and suggested labels, which is what downstream stages consume. The Elixir source is included for transparency about the prompt template and structured-output schema. To re-run from scratch you would need to port `scifact_auditor.ex` into a standalone Mix project or rewrite it against the OpenAI Responses API in any language.

## Citation

```bibtex
@inproceedings{sylvestre2026scifact,
  title     = {Gold Label Errors in the {SciFact} Benchmark: An {LLM}-Assisted Annotation Audit},
  author    = {Sylvestre, Julien},
  booktitle = {Proceedings of BioNLP},
  year      = {2026}
}
```

See also `CITATION.cff` for citation metadata in standard form.

## License

Code: MIT (see `LICENSE`).
Corrections, manual-review CSVs, and annotator packets: CC BY 4.0 — derived from the SciFact dataset (which is itself ODC-BY 1.0 / CC BY-NC 4.0; check the original release for terms applying to the underlying claims and abstracts).
