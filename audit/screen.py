"""Stage 1: LLM-screen the SciFact dev set for candidate gold-label errors.

Sends each of the 209 dev (claim, evidence-doc) pairs to GPT-5.4-mini with a
structured-output JSON schema. The model returns AGREE / DISAGREE / DEBATABLE
plus reasoning, error-type tag, and a suggested correct label. The output is
the input to Stage 2 (manual review).

Full-run cost on all 209 pairs at March 2026 pricing was ~$0.11.

Run:
    export OPENAI_API_KEY=sk-...
    python3 audit/screen.py                  # all 209 pairs
    python3 audit/screen.py --limit 2        # smoke test
    python3 audit/screen.py --out custom.json
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
# Config — matches the audit run that produced the paper's 209-pair screen
# ---------------------------------------------------------------------------
MODEL = "gpt-5.4-mini"
TEMPERATURE = 0.3
MAX_OUTPUT_TOKENS = 600
DEFAULT_CONCURRENCY = 15

# Pricing (per million tokens) for cost estimate
PRICE_IN = 0.25
PRICE_OUT = 1.00

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "stage1_llm_screen"

SYSTEM_PROMPT = """You are a scientific peer reviewer auditing a benchmark dataset for annotation quality. \
Your task is to evaluate whether the gold label assigned to a scientific claim is CORRECT \
given the provided evidence.

The dataset labels claims as either SUPPORT (the evidence supports the claim) or \
CONTRADICT (the evidence contradicts the claim).

Evaluate rigorously:
- Does the evidence actually support/contradict the claim as stated?
- Is the claim precisely worded, or does imprecise wording make the label debatable?
- Are there causal overclaims, generalizations beyond the evidence, or numerical mismatches?
- Would a domain expert agree with this gold label?

Be honest: if the gold label is clearly correct, say AGREE. Only flag issues you are \
confident about. But do not hesitate to flag genuine annotation errors.

Return your assessment as JSON.
"""

LABEL_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "gold_assessment": {
            "type": "string",
            "description": "One of: agree, disagree, debatable",
        },
        "reasoning": {
            "type": "string",
            "description": "Detailed explanation of whether the gold label is correct (3-5 sentences)",
        },
        "error_type": {
            "type": "string",
            "description": (
                "If disagree/debatable: one of: claim_imprecise, causal_overclaim, "
                "generalization_beyond_evidence, numerical_mismatch, negation_missed, "
                "direction_reversed, annotation_convention, other, none"
            ),
        },
        "correct_label": {
            "type": "string",
            "description": "What the label should be: support, contradict, or ambiguous",
        },
    },
    "required": ["gold_assessment", "reasoning", "error_type", "correct_label"],
    "additionalProperties": False,
}


def build_user_prompt(pair: dict) -> str:
    evidence = (
        f"Title: {pair['title']}\n\n"
        f"Abstract: {pair['abstract_text']}\n\n"
        f"Key evidence: {pair['rationale_text']}"
    )
    return (
        f'Scientific claim: "{pair["claim"]}"\n\n'
        f"Gold label: {pair['original_label']}\n\n"
        f"Evidence (from the cited paper):\n{evidence}\n"
    )


async def audit_one(
    client: AsyncOpenAI,
    pair: dict,
    sem: asyncio.Semaphore,
    max_retries: int = 4,
) -> dict:
    async with sem:
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = await client.responses.create(
                    model=MODEL,
                    input=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(pair)},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "label_audit",
                            "strict": True,
                            "schema": LABEL_AUDIT_SCHEMA,
                        }
                    },
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                )
                parsed = json.loads(resp.output_text)
                usage = resp.usage
                return {
                    "id": pair["claim_id"],
                    "claim": pair["claim"],
                    "gold_label": pair["original_label"],
                    "doc_id": pair["doc_id"],
                    "gold_assessment": parsed["gold_assessment"],
                    "reasoning": parsed["reasoning"],
                    "error_type": parsed["error_type"],
                    "correct_label": parsed["correct_label"],
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                }
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                # Final attempt failed — record and continue
                return {
                    "id": pair["claim_id"],
                    "claim": pair["claim"],
                    "gold_label": pair["original_label"],
                    "doc_id": pair["doc_id"],
                    "gold_assessment": "error",
                    "reasoning": f"{type(last_err).__name__}: {last_err}",
                    "error_type": "none",
                    "correct_label": "unknown",
                    "input_tokens": 0,
                    "output_tokens": 0,
                }


async def run(limit: int | None, out_path: Path, concurrency: int):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set in environment.")

    pairs = load_pairs()
    if limit is not None:
        pairs = pairs[:limit]

    print(f"Auditing {len(pairs)} SciFact dev pairs with {MODEL} (concurrency={concurrency})")

    client = AsyncOpenAI(api_key=api_key)
    sem = asyncio.Semaphore(concurrency)

    tasks = [audit_one(client, p, sem) for p in pairs]
    results = []
    done = 0
    for fut in asyncio.as_completed(tasks):
        r = await fut
        results.append(r)
        done += 1
        if done % 25 == 0 or done == len(pairs):
            print(f"  {done}/{len(pairs)} complete")

    # Sort by claim_id, doc_id for stable output ordering
    results.sort(key=lambda r: (r["id"], str(r["doc_id"])))

    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    cost = total_in * PRICE_IN / 1_000_000 + total_out * PRICE_OUT / 1_000_000

    by_assessment = dict(Counter(r["gold_assessment"] for r in results))
    by_error_type = dict(
        Counter(
            r["error_type"]
            for r in results
            if r["gold_assessment"] != "agree"
        )
    )

    print(f"\nAssessment distribution: {by_assessment}")
    print(f"Error types (non-agree): {by_error_type}")
    print(f"Tokens: {total_in} in / {total_out} out  Cost: ${cost:.4f}")

    output = {
        "dataset": "scifact",
        "split": "dev",
        "model": MODEL,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "by_assessment": by_assessment,
            "by_error_type": by_error_type,
        },
        "usage": {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cost_usd": cost,
        },
        "results": results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {out_path}")


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--limit", type=int, default=None, help="Only audit the first N pairs (smoke test).")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--out", type=Path, default=None, help="Output JSON path (default: results/stage1_llm_screen/scifact_audit_<model>_n<N>_<ts>.json).")
    return ap.parse_args()


def main():
    args = parse_args()
    if args.out is None:
        n_pairs = len(load_pairs()) if args.limit is None else args.limit
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        args.out = DEFAULT_OUT_DIR / f"scifact_audit_{MODEL}_n{n_pairs}_{ts}.json"
    asyncio.run(run(args.limit, args.out, args.concurrency))


if __name__ == "__main__":
    main()
