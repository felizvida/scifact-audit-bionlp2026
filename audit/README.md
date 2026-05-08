# Stage 1 — LLM Audit + Binary Prediction

Two scripts that produce the inputs to Stages 2 and 3. Both are zero-shot, run against the OpenAI Responses API with structured JSON output, and write to [`../results/stage1_llm_screen/`](../results/stage1_llm_screen/) by default.

```bash
pip install -r ../revision/requirements.txt
export OPENAI_API_KEY=sk-...
```

## screen.py — the audit screen

Sends each of the 209 dev (claim, evidence-doc) pairs to GPT-5.4-mini with the audit prompt and a structured JSON schema (`gold_assessment`: agree/disagree/debatable, plus reasoning, error type, suggested label). The output is the input to Stage 2 (manual review).

```bash
python3 screen.py                  # full run (~$0.11)
python3 screen.py --limit 2        # smoke test (~$0.001)
python3 screen.py --out custom.json
```

Cached reference output: [`../results/stage1_llm_screen/scifact_audit_gpt-5.4-mini_n209_2026-04-02T14-33-55.931576Z.json`](../results/stage1_llm_screen/) — this is the screen the paper's downstream stages were derived from. Re-running will produce a fresh JSON with new timestamps; results should be qualitatively similar but bit-exact match is not guaranteed (the OpenAI API is non-deterministic even at temperature 0.3).

## predict_binary.py — zero-shot SUPPORT/CONTRADICT classifier

Reproduces the per-model F1 numbers reported in the paper. Pair the predictions with original or corrected gold labels (from [`../corrections/`](../corrections/)) to compute the F1 deltas.

```bash
python3 predict_binary.py --model gpt-5.4-mini   # paper reports 84.9 -> 88.7
python3 predict_binary.py --model gpt-5.4-nano   # paper reports 79.5 -> 81.2
python3 predict_binary.py --model gpt-5.4-mini --limit 2  # smoke test
```

Cached reference outputs:
- [`../results/stage1_llm_screen/scifact_single_gpt-5.4-mini_n209_*.json`](../results/stage1_llm_screen/)
- [`../results/stage1_llm_screen/scifact_single_gpt-5.4-nano_n209_*.json`](../results/stage1_llm_screen/)

## Notes

- Both scripts use the OpenAI Responses API (`client.responses.create`) with `text.format = {type: "json_schema", strict: true}` for deterministic parsing.
- `screen.py` uses temperature 0.3, max 600 output tokens, concurrency 15, matching the audit run that produced the paper's 209-pair screen.
- `predict_binary.py` uses temperature 0.0, max 256 output tokens, concurrency 30.
- Costs at March 2026 pricing: ~$0.11 (mini screen), ~$0.05 (mini binary), ~$0.02 (nano binary). Re-running all three is well under $0.25 total.
- `_loader.py` is a small shared utility that joins `data/scifact/claims_dev.jsonl` with `corpus.jsonl` into the 209 audit pairs. It is imported by both scripts and by `revision/run_haiku_experiments.py`.
