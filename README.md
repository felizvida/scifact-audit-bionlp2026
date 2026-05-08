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
├── paper/                 Camera-ready PDF, .tex source, .bib, ACL style files
├── corrections/           Headline output: corrected gold labels (JSON)
├── data/                  Helper to fetch SciFact (dataset itself not vendored)
├── audit/                 Stage 1: LLM screen + binary classifier (Python, OpenAI)
├── results/               Cached outputs from each stage of the audit
│   ├── stage1_llm_screen/   GPT-5.4 audit JSON + per-pair predictions
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

Everything is in Python. Install once and pick the stage you want:

```bash
# Setup (~30 seconds + ~50 MB SciFact download)
bash data/download_scifact.sh
pip install -r revision/requirements.txt
```

### Offline stages (no API, deterministic)

```bash
# Recompute the binomial tests, Clopper–Pearson CIs, and sensitivity table
python3 revision/stats_compute.py

# Re-build the blind annotator packets (deterministic with seed=42)
python3 revision/build_packets.py
```

### Stage 1 — LLM screen + binary classifier (paid OpenAI calls)

```bash
export OPENAI_API_KEY=sk-...
python3 audit/screen.py                             # ~$0.11 — produces audit JSON
python3 audit/predict_binary.py --model gpt-5.4-mini  # ~$0.05 — paper reports 84.9 → 88.7 F1
python3 audit/predict_binary.py --model gpt-5.4-nano  # ~$0.02 — paper reports 79.5 → 81.2 F1
```

Add `--limit 2` to either for a sub-cent smoke test. Every script writes to `results/stage1_llm_screen/` by default.

### Stage 3 — cross-model verification (paid Anthropic calls)

```bash
export CLAUDE_API_KEY=sk-ant-...
python3 revision/run_haiku_experiments.py           # ~$0.54 — Haiku 4.5 F1 + contamination probe
```

### Cached outputs

If you don't want to spend any API budget, every stage's output is already committed under [`results/`](results/). [`revision/stats_compute.py`](revision/stats_compute.py) and [`revision/build_packets.py`](revision/build_packets.py) read those cached outputs and reproduce every number in the paper offline.

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
