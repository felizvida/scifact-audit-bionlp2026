# Stage 1: LLM Audit Screen (Original)

This directory contains the **original Elixir source** used to run the GPT-5.4-mini screen over the 209 SciFact dev pairs. The screen's output is cached in [`../results/stage1_llm_screen/`](../results/stage1_llm_screen/) so downstream analysis does not require re-running this code.

## What's here

```
elixir/
├── scifact_loader.ex   Joins claims_dev.jsonl with corpus.jsonl into (claim, doc) pairs
├── scifact_auditor.ex  Sends each pair to GPT-5.4-mini with the audit prompt + JSON schema
└── scifact_pilot.ex    Runs binary zero-shot prediction (used for the original F1 numbers)
```

The audit prompt and structured JSON schema (AGREE / DISAGREE / DEBATABLE assessment, reasoning, error type, suggested label) live inside `scifact_auditor.ex` (`@audit_prompt`, `@audit_schema`).

## Why this is reference-only

These files were originally part of an Elixir umbrella project (`colonyOS`) that wired them up to a `ClaimVerifier` GenServer, a configured OpenAI-compatible LLM client, and a results-saving pipeline. They are included here for transparency about the exact prompt and schema we used, not as a runnable artifact.

If you want to re-run the screen from scratch, you have three options:

1. **Use the cached output.** `results/stage1_llm_screen/scifact_audit_gpt-5.4-mini_n209_*.json` contains every per-pair verdict, reasoning string, and suggested label. This is what we recommend for any reproduction work, since it bit-exactly reproduces the input to Stages 2 and 3.

2. **Port the prompt to your own client.** The audit prompt and JSON schema in `scifact_auditor.ex` are short and self-contained; rewriting them as a 100-line Python script against the OpenAI Responses API takes about an hour. Use temperature 0.3 and the structured-output mode.

3. **Stand up the original Elixir pipeline.** Drop these files into a Mix project, install `req` and `jason` and the OpenAI client, supply an `OPENAI_API_KEY`, and call `SrBench.ScifactAuditor.audit_all/1`. You will need to also provide the `SrBench.ScifactLoader` config (it caches the SciFact tarball under `priv/scifact_dataset/`).

## Cost

The original screen cost **$0.11** in OpenAI API fees (approximately 440K input tokens at March 2026 GPT-5.4-mini pricing; cached-input rates applied to repeated system-prompt content).
