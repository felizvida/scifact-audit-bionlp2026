"""Stage 1: zero-shot binary SUPPORT/CONTRADICT prediction on the SciFact dev set.

Reproduces the F1 numbers reported in the paper for GPT-5.4-mini (84.9 / 88.7
before/after corrections) and GPT-5.4-nano (79.5 / 81.2). Output JSON has the
per-pair predictions; pair the predictions with original or corrected gold
labels to compute F1 deltas.

Run:
    export OPENAI_API_KEY=sk-...
    python3 audit/predict_binary.py --model gpt-5.4-mini
    python3 audit/predict_binary.py --model gpt-5.4-nano --limit 2  # smoke test
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loader import load_pairs

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_CONCURRENCY = 30
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 256

PRICING = {  # ($/M input, $/M output) at March 2026
    "gpt-5.4-mini": (0.25, 1.00),
    "gpt-5.4-nano": (0.10, 0.40),
}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "stage1_llm_screen"

SYSTEM_PROMPT = """You are a careful scientific fact-checking assistant. Given a scientific claim and a paper title, abstract, and key evidence sentences, classify whether the paper SUPPORTS the claim or CONTRADICTS it.

- SUPPORT: the paper provides evidence that affirms the claim.
- CONTRADICT: the paper provides evidence that refutes the claim.

Return your verdict as JSON.
"""

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "description": "Either SUPPORT or CONTRADICT.",
        },
        "reasoning": {
            "type": "string",
            "description": "1-2 sentence explanation.",
        },
    },
    "required": ["verdict", "reasoning"],
    "additionalProperties": False,
}


def build_user_prompt(pair: dict) -> str:
    return (
        f'Scientific claim: "{pair["claim"]}"\n\n'
        f"Paper title: {pair['title']}\n\n"
        f"Paper abstract: {pair['abstract_text']}\n\n"
        f"Key evidence sentences: {pair['rationale_text']}\n\n"
        "Classify the claim as SUPPORT or CONTRADICT."
    )


async def predict_one(
    client: AsyncOpenAI,
    pair: dict,
    model: str,
    sem: asyncio.Semaphore,
    max_retries: int = 4,
) -> dict:
    async with sem:
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = await client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(pair)},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "verdict",
                            "strict": True,
                            "schema": VERDICT_SCHEMA,
                        }
                    },
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                )
                parsed = json.loads(resp.output_text)
                usage = resp.usage
                verdict = parsed["verdict"].upper()
                return {
                    "id": pair["claim_id"],
                    "claim": pair["claim"],
                    "doc_id": pair["doc_id"],
                    "gold_label": pair["original_label"],
                    "predicted": verdict,
                    "reasoning": parsed["reasoning"],
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                }
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "id": pair["claim_id"],
                    "claim": pair["claim"],
                    "doc_id": pair["doc_id"],
                    "gold_label": pair["original_label"],
                    "predicted": "ERROR",
                    "reasoning": f"{type(last_err).__name__}: {last_err}",
                    "input_tokens": 0,
                    "output_tokens": 0,
                }


def macro_f1(results: list[dict]) -> dict:
    """Binary macro F1 on SUPPORT vs CONTRADICT (predictions == gold)."""
    by_class = {"SUPPORT": {"tp": 0, "fp": 0, "fn": 0, "support": 0},
                "CONTRADICT": {"tp": 0, "fp": 0, "fn": 0, "support": 0}}
    correct = 0
    for r in results:
        if r["predicted"] == "ERROR":
            continue
        gold = r["gold_label"]
        pred = r["predicted"]
        by_class[gold]["support"] += 1
        if pred == gold:
            by_class[gold]["tp"] += 1
            correct += 1
        else:
            if pred in by_class:
                by_class[pred]["fp"] += 1
            by_class[gold]["fn"] += 1
    per_class = {}
    for cls, c in by_class.items():
        prec = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else 0.0
        rec = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[cls] = {"precision": prec, "recall": rec, "f1": f1, "support": c["support"]}
    macro = sum(c["f1"] for c in per_class.values()) / len(per_class)
    n = sum(c["support"] for c in per_class.values())
    return {"macro_f1": macro, "accuracy": correct / n if n else 0.0,
            "correct": correct, "total": n, "per_class": per_class}


async def run(model: str, limit: int | None, out_path: Path, concurrency: int):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set in environment.")
    if model not in PRICING:
        print(f"Warning: no pricing entry for {model}; cost estimate will be 0.")

    pairs = load_pairs()
    if limit is not None:
        pairs = pairs[:limit]

    label_dist = dict(Counter(p["original_label"] for p in pairs))
    print(f"Predicting {len(pairs)} SciFact dev pairs with {model} (concurrency={concurrency})")
    print(f"Label distribution: {label_dist}")

    client = AsyncOpenAI(api_key=api_key)
    sem = asyncio.Semaphore(concurrency)

    tasks = [predict_one(client, p, model, sem) for p in pairs]
    results = []
    done = 0
    for fut in asyncio.as_completed(tasks):
        r = await fut
        results.append(r)
        done += 1
        if done % 25 == 0 or done == len(pairs):
            print(f"  {done}/{len(pairs)} complete")

    results.sort(key=lambda r: (r["id"], str(r["doc_id"])))

    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    pin, pout = PRICING.get(model, (0.0, 0.0))
    cost = total_in * pin / 1_000_000 + total_out * pout / 1_000_000

    metrics = macro_f1(results)
    print(f"\nMacro F1: {metrics['macro_f1']*100:.1f}%  Accuracy: {metrics['accuracy']*100:.1f}%")
    for cls, c in metrics["per_class"].items():
        print(f"  {cls}: P={c['precision']*100:.1f}% R={c['recall']*100:.1f}% F1={c['f1']*100:.1f}% (n={c['support']})")
    print(f"Tokens: {total_in} in / {total_out} out  Cost: ${cost:.4f}")

    output = {
        "config": {
            "dataset": "scifact",
            "setting": "oracle",
            "strategy": "single",
            "model": model,
            "split": "dev",
            "n": len(results),
        },
        "metrics": metrics,
        "usage": {"input_tokens": total_in, "output_tokens": total_out},
        "cost_usd": cost,
        "results": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {out_path}")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", default="gpt-5.4-mini", choices=list(PRICING.keys()))
    ap.add_argument("--limit", type=int, default=None, help="Only predict on the first N pairs (smoke test).")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--out", type=Path, default=None)
    return ap.parse_args()


def main():
    args = parse_args()
    if args.out is None:
        n_pairs = len(load_pairs()) if args.limit is None else args.limit
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        args.out = DEFAULT_OUT_DIR / f"scifact_single_{args.model}_n{n_pairs}_{ts}.json"
    asyncio.run(run(args.model, args.limit, args.out, args.concurrency))


if __name__ == "__main__":
    main()
