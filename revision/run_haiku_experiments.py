"""
Haiku 4.5 SciFact revision experiments for BioNLP 2026.

Experiment 1: Re-run zero-shot 3-way classification on 209 SciFact dev pairs (with gold evidence)
              using Haiku 4.5, to measure F1 delta from corrections (matching the GPT-5.4-mini setup).
Experiment 2: Contamination probe - claim-only classification (no abstract/evidence) on the same
              209 claims to test for SciFact dataset memorization.

Both experiments use:
- Anthropic Messages API with claude-haiku-4-5-20251001
- Structured tool-use output via a `submit_label` tool (deterministic parsing)
- Prompt caching on the system prompt (cache_control: ephemeral)
- 20-way concurrent async with retry on 429/529
"""

import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Paths (repo-relative)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent  # repo root
CLAIMS_DEV = ROOT / "data" / "scifact" / "claims_dev.jsonl"
CORPUS = ROOT / "data" / "scifact" / "corpus.jsonl"
CORRECTIONS = ROOT / "corrections" / "dev_corrections.json"
RESULTS_DIR = ROOT / "results" / "stage3_revision"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
EXP1_OUT = RESULTS_DIR / "haiku_f1_n209_dev.json"
EXP2_OUT = RESULTS_DIR / "contamination_probe_haiku.json"

if not CLAIMS_DEV.exists():
    raise SystemExit(
        f"SciFact dataset not found at {CLAIMS_DEV.parent}. "
        "Run `bash data/download_scifact.sh` from the repo root first."
    )

MODEL = "claude-haiku-4-5-20251001"
CONCURRENCY = 20

# Pricing: input $1/M, output $5/M (per task spec)
INPUT_PRICE_PER_TOKEN = 1.0 / 1_000_000
OUTPUT_PRICE_PER_TOKEN = 5.0 / 1_000_000


# ---------------------------------------------------------------------------
# Data loading: join evidence-doc pairs (one (claim, doc) per evidence doc)
# ---------------------------------------------------------------------------
def load_corpus() -> dict:
    corpus = {}
    with open(CORPUS) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            doc_id = str(doc["doc_id"])
            sentences = doc.get("abstract") or []
            corpus[doc_id] = {
                "title": doc.get("title", ""),
                "sentences": sentences,
                "abstract_text": " ".join(sentences),
            }
    return corpus


def load_pairs() -> list[dict]:
    """Load all (claim, doc) pairs that have gold evidence in dev set."""
    corpus = load_corpus()
    pairs = []
    with open(CLAIMS_DEV) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            evidence = raw.get("evidence") or {}
            if not evidence:
                continue  # skip NEI in original (no gold evidence)
            for doc_id_str, rationales in evidence.items():
                doc = corpus.get(doc_id_str)
                if not doc or not rationales:
                    continue
                label = rationales[0]["label"]  # SUPPORT or CONTRADICT
                rationale_sentences = sorted(set(
                    s for r in rationales for s in (r.get("sentences") or [])
                ))
                if rationale_sentences:
                    rationale_text = " ".join(
                        doc["sentences"][i] if i < len(doc["sentences"]) else ""
                        for i in rationale_sentences
                    )
                else:
                    rationale_text = doc["abstract_text"]
                pairs.append({
                    "claim_id": raw["id"],
                    "claim": raw["claim"],
                    "doc_id": doc_id_str,
                    "title": doc["title"],
                    "abstract_text": doc["abstract_text"],
                    "rationale_text": rationale_text,
                    "original_label": label,  # "SUPPORT" or "CONTRADICT"
                })
    return pairs


def load_corrections() -> dict:
    with open(CORRECTIONS) as f:
        data = json.load(f)
    by_claim = {}
    for c in data["corrections"]:
        by_claim[c["claim_id"]] = c
    return by_claim


# ---------------------------------------------------------------------------
# Prompts and tool definitions
# ---------------------------------------------------------------------------
EXP1_SYSTEM = """You are a careful scientific fact-checking assistant. Given a scientific claim, the title and abstract of a paper, and the gold-standard rationale sentences from that paper, classify whether the paper SUPPORTS the claim, CONTRADICTS the claim, or provides Not Enough Information (NEI).

- SUPPORT: the paper provides evidence that affirms the claim.
- CONTRADICT: the paper provides evidence that refutes the claim.
- NEI: the paper does not provide enough information to judge the claim (e.g., wrong outcome measure, wrong population/entity, off-topic).

Use the `submit_label` tool to return exactly one label."""

EXP2_SYSTEM = """You are a scientific fact-checking assistant. You will be given ONLY a scientific claim, with no evidence. Based purely on your prior knowledge, classify the claim as SUPPORT (the claim is consistent with established scientific knowledge), CONTRADICT (the claim contradicts established scientific knowledge), or NEI (you cannot determine without additional evidence).

Use the `submit_label` tool to return exactly one label."""

SUBMIT_LABEL_TOOL = {
    "name": "submit_label",
    "description": "Submit the final classification label for the claim.",
    "input_schema": {
        "type": "object",
        "properties": {
            "label": {
                "type": "string",
                "enum": ["SUPPORT", "CONTRADICT", "NEI"],
                "description": "The classification label.",
            }
        },
        "required": ["label"],
    },
}


def build_exp1_user(pair: dict) -> str:
    return (
        f"CLAIM: {pair['claim']}\n\n"
        f"PAPER TITLE: {pair['title']}\n\n"
        f"PAPER ABSTRACT: {pair['abstract_text']}\n\n"
        f"GOLD RATIONALE SENTENCES: {pair['rationale_text']}\n\n"
        "Classify the claim with respect to this paper using `submit_label`."
    )


def build_exp2_user(pair: dict) -> str:
    return (
        f"CLAIM: {pair['claim']}\n\n"
        "Based purely on your prior knowledge (no evidence has been provided), "
        "classify this claim using `submit_label`."
    )


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------
async def call_haiku(
    client: anthropic.AsyncAnthropic,
    system_text: str,
    user_text: str,
    sem: asyncio.Semaphore,
    max_retries: int = 5,
) -> dict:
    """Returns dict with prediction, input_tokens, output_tokens, cache_creation, cache_read."""
    async with sem:
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = await client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    system=[
                        {
                            "type": "text",
                            "text": system_text,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=[SUBMIT_LABEL_TOOL],
                    tool_choice={"type": "tool", "name": "submit_label"},
                    messages=[{"role": "user", "content": user_text}],
                )
                # Extract label from tool_use block
                label = None
                for block in resp.content:
                    if block.type == "tool_use" and block.name == "submit_label":
                        label = block.input.get("label")
                        break
                return {
                    "prediction": label,
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "cache_creation_input_tokens": getattr(
                        resp.usage, "cache_creation_input_tokens", 0
                    ) or 0,
                    "cache_read_input_tokens": getattr(
                        resp.usage, "cache_read_input_tokens", 0
                    ) or 0,
                    "stop_reason": resp.stop_reason,
                }
            except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
                # Retry on 429 / 529 / 5xx
                status = getattr(e, "status_code", None)
                if status in (429, 529) or (status and status >= 500):
                    last_err = e
                    delay = min(2 ** attempt + 0.5 * attempt, 30)
                    await asyncio.sleep(delay)
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
        raise last_err


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def confusion(preds: list[str], golds: list[str], labels: list[str]) -> dict:
    """Returns dict[gold][pred] = count."""
    cm = {g: {p: 0 for p in labels} for g in labels}
    for p, g in zip(preds, golds):
        if g not in cm:
            continue
        if p not in cm[g]:
            # Unknown label - treat as wrong
            continue
        cm[g][p] += 1
    return cm


def per_class_prf(preds: list[str], golds: list[str], labels: list[str]) -> dict:
    out = {}
    for lab in labels:
        tp = sum(1 for p, g in zip(preds, golds) if p == lab and g == lab)
        fp = sum(1 for p, g in zip(preds, golds) if p == lab and g != lab)
        fn = sum(1 for p, g in zip(preds, golds) if p != lab and g == lab)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        out[lab] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}
    return out


def macro_f1(prf: dict) -> float:
    return sum(v["f1"] for v in prf.values()) / len(prf)


def accuracy(preds: list[str], golds: list[str]) -> float:
    correct = sum(1 for p, g in zip(preds, golds) if p == g)
    return correct / len(golds) if golds else 0.0


# ---------------------------------------------------------------------------
# Experiment 1
# ---------------------------------------------------------------------------
async def run_experiment_1(pairs: list[dict], corrections: dict) -> dict:
    print(f"[Exp 1] Running {len(pairs)} pairs through Haiku 4.5 with evidence...", flush=True)
    client = anthropic.AsyncAnthropic(api_key=os.environ["CLAUDE_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)

    t0 = time.time()
    # Use gather to preserve order of results matching pairs
    results = await asyncio.gather(*[
        call_haiku(client, EXP1_SYSTEM, build_exp1_user(p), sem)
        for p in pairs
    ])
    elapsed = time.time() - t0
    print(f"  [Exp 1] Done in {elapsed:.1f}s", flush=True)

    # Build per-pair records
    records = []
    total_in = 0
    total_out = 0
    total_cache_create = 0
    total_cache_read = 0
    for pair, res in zip(pairs, results):
        cid = pair["claim_id"]
        corr = corrections.get(cid)
        # corrected_label_if_any: only set if there's a correction
        corrected_label = None
        if corr:
            corrected_label = corr["corrected_label"]  # may be SUPPORT/CONTRADICT/NEI
        records.append({
            "claim_id": cid,
            "doc_id": pair["doc_id"],
            "claim": pair["claim"],
            "prediction": res["prediction"],
            "original_label": pair["original_label"],
            "corrected_label": corrected_label,
            "input_tokens": res["input_tokens"],
            "output_tokens": res["output_tokens"],
            "cache_creation_input_tokens": res["cache_creation_input_tokens"],
            "cache_read_input_tokens": res["cache_read_input_tokens"],
        })
        total_in += res["input_tokens"]
        total_out += res["output_tokens"]
        total_cache_create += res["cache_creation_input_tokens"]
        total_cache_read += res["cache_read_input_tokens"]

    # ---- Metric 1: Binary F1 (S vs C) on original labels (209 pairs) ----
    # NEI predictions count as wrong. Map NEI to "WRONG" - i.e., not equal to
    # gold for either class. We document the choice: NEI predictions are kept
    # as a separate label for F1 purposes (they get 0 TPs for both classes).
    preds_209 = [r["prediction"] for r in records]
    gold_orig_209 = [r["original_label"] for r in records]

    prf_bin_orig = per_class_prf(preds_209, gold_orig_209, ["SUPPORT", "CONTRADICT"])
    macro_bin_orig = macro_f1(prf_bin_orig)
    cm_bin_orig = confusion(preds_209, gold_orig_209, ["SUPPORT", "CONTRADICT", "NEI"])
    acc_bin_orig = accuracy(preds_209, gold_orig_209)

    # ---- Metric 2: Binary F1 on corrected labels, EXCLUDE 6 NEI pairs (203 pairs) ----
    NEI_EXCLUDE_IDS = {343, 1368, 770, 1216, 1274, 847}
    SC_REVERSAL_IDS = {593, 879, 1385, 808, 208}
    preds_203 = []
    gold_corr_203 = []
    for r in records:
        if r["claim_id"] in NEI_EXCLUDE_IDS:
            continue
        gold = r["original_label"]
        if r["claim_id"] in SC_REVERSAL_IDS:
            gold = r["corrected_label"]  # already SUPPORT or CONTRADICT (the reversal)
        preds_203.append(r["prediction"])
        gold_corr_203.append(gold)

    prf_bin_corr = per_class_prf(preds_203, gold_corr_203, ["SUPPORT", "CONTRADICT"])
    macro_bin_corr = macro_f1(prf_bin_corr)
    cm_bin_corr = confusion(preds_203, gold_corr_203, ["SUPPORT", "CONTRADICT", "NEI"])
    acc_bin_corr = accuracy(preds_203, gold_corr_203)

    # ---- Metric 3: 3-way macro F1 on original labels (209 pairs) ----
    # Originals are S/C only; NEI predictions count as wrong against both.
    prf_3way_orig = per_class_prf(preds_209, gold_orig_209, ["SUPPORT", "CONTRADICT", "NEI"])
    macro_3way_orig = macro_f1(prf_3way_orig)
    cm_3way_orig = cm_bin_orig  # same 3x3
    acc_3way_orig = acc_bin_orig

    # ---- Metric 4: 3-way macro F1 on corrected labels (209 pairs) ----
    gold_corr_209 = []
    for r in records:
        gold = r["original_label"]
        if r["claim_id"] in (NEI_EXCLUDE_IDS | SC_REVERSAL_IDS) and r["corrected_label"]:
            gold = r["corrected_label"]
        gold_corr_209.append(gold)
    prf_3way_corr = per_class_prf(preds_209, gold_corr_209, ["SUPPORT", "CONTRADICT", "NEI"])
    macro_3way_corr = macro_f1(prf_3way_corr)
    cm_3way_corr = confusion(preds_209, gold_corr_209, ["SUPPORT", "CONTRADICT", "NEI"])
    acc_3way_corr = accuracy(preds_209, gold_corr_209)

    cost = (
        total_in * INPUT_PRICE_PER_TOKEN
        + total_out * OUTPUT_PRICE_PER_TOKEN
        + total_cache_create * INPUT_PRICE_PER_TOKEN * 1.25
        + total_cache_read * INPUT_PRICE_PER_TOKEN * 0.1
    )

    summary = {
        "experiment": "Experiment 1: Haiku 4.5 zero-shot 3-way with evidence",
        "model": MODEL,
        "n_pairs": len(records),
        "elapsed_seconds": round(elapsed, 1),
        "tokens": {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cache_creation_input_tokens": total_cache_create,
            "cache_read_input_tokens": total_cache_read,
        },
        "estimated_cost_usd": round(cost, 4),
        "metric_1_binary_original": {
            "n": len(preds_209),
            "macro_f1_SC": macro_bin_orig,
            "accuracy": acc_bin_orig,
            "per_class": prf_bin_orig,
            "confusion_matrix_3way": cm_bin_orig,
            "note": "Binary S vs C macro F1 on 209 pairs with original labels. NEI predictions count as wrong (contribute 0 TP to either class).",
        },
        "metric_2_binary_corrected": {
            "n": len(preds_203),
            "macro_f1_SC": macro_bin_corr,
            "accuracy": acc_bin_corr,
            "per_class": prf_bin_corr,
            "confusion_matrix_3way": cm_bin_corr,
            "note": "Binary S vs C macro F1 on 203 pairs (5 S<->C reversals applied; 6 NEI pairs excluded).",
        },
        "metric_3_3way_original": {
            "n": len(preds_209),
            "macro_f1": macro_3way_orig,
            "accuracy": acc_3way_orig,
            "per_class": prf_3way_orig,
            "confusion_matrix": cm_3way_orig,
            "note": "3-way macro F1 (S/C/NEI) on 209 pairs with original labels (no NEI in gold).",
        },
        "metric_4_3way_corrected": {
            "n": len(preds_209),
            "macro_f1": macro_3way_corr,
            "accuracy": acc_3way_corr,
            "per_class": prf_3way_corr,
            "confusion_matrix": cm_3way_corr,
            "note": "3-way macro F1 (S/C/NEI) on 209 pairs with corrected labels (5 reversals + 6 NEI).",
        },
        "predictions": records,
    }
    return summary


# ---------------------------------------------------------------------------
# Experiment 2: contamination probe (claim only)
# ---------------------------------------------------------------------------
async def run_experiment_2(pairs: list[dict]) -> dict:
    print(f"[Exp 2] Running {len(pairs)} claims claim-only (contamination probe)...", flush=True)
    client = anthropic.AsyncAnthropic(api_key=os.environ["CLAUDE_API_KEY"])
    sem = asyncio.Semaphore(CONCURRENCY)

    t0 = time.time()
    results = await asyncio.gather(*[
        call_haiku(client, EXP2_SYSTEM, build_exp2_user(p), sem)
        for p in pairs
    ])
    elapsed = time.time() - t0

    total_in = sum(r["input_tokens"] for r in results)
    total_out = sum(r["output_tokens"] for r in results)
    total_cache_create = sum(r["cache_creation_input_tokens"] for r in results)
    total_cache_read = sum(r["cache_read_input_tokens"] for r in results)

    records = []
    for pair, res in zip(pairs, results):
        records.append({
            "claim_id": pair["claim_id"],
            "doc_id": pair["doc_id"],
            "claim": pair["claim"],
            "prediction": res["prediction"],
            "original_label": pair["original_label"],
        })

    preds = [r["prediction"] for r in records]
    golds = [r["original_label"] for r in records]

    # Baselines
    label_counts = Counter(golds)
    majority_class = label_counts.most_common(1)[0][0]
    majority_acc = label_counts[majority_class] / len(golds)
    random_acc = 1.0 / 3  # 3-way

    haiku_acc = accuracy(preds, golds)
    prf = per_class_prf(preds, golds, ["SUPPORT", "CONTRADICT", "NEI"])
    macro = macro_f1(prf)
    cm = confusion(preds, golds, ["SUPPORT", "CONTRADICT", "NEI"])

    cost = (
        total_in * INPUT_PRICE_PER_TOKEN
        + total_out * OUTPUT_PRICE_PER_TOKEN
        + total_cache_create * INPUT_PRICE_PER_TOKEN * 1.25
        + total_cache_read * INPUT_PRICE_PER_TOKEN * 0.1
    )

    return {
        "experiment": "Experiment 2: Contamination probe (claim-only, no evidence)",
        "model": MODEL,
        "n_pairs": len(records),
        "elapsed_seconds": round(elapsed, 1),
        "tokens": {
            "input_tokens": total_in,
            "output_tokens": total_out,
            "cache_creation_input_tokens": total_cache_create,
            "cache_read_input_tokens": total_cache_read,
        },
        "estimated_cost_usd": round(cost, 4),
        "haiku_accuracy": haiku_acc,
        "haiku_macro_f1_3way": macro,
        "haiku_per_class": prf,
        "confusion_matrix": cm,
        "baselines": {
            "random_3way_accuracy": random_acc,
            "majority_class": majority_class,
            "majority_class_accuracy": majority_acc,
            "label_counts_gold": dict(label_counts),
        },
        "predictions": records,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    if not os.environ.get("CLAUDE_API_KEY"):
        print("ERROR: CLAUDE_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    pairs = load_pairs()
    corrections = load_corrections()
    print(f"Loaded {len(pairs)} (claim, doc) pairs from dev set with gold evidence.")
    print(f"Loaded {len(corrections)} corrections.")

    # Run Experiment 1
    exp1 = await run_experiment_1(pairs, corrections)
    EXP1_OUT.write_text(json.dumps(exp1, indent=2))
    print(f"\n[Exp 1] Saved -> {EXP1_OUT}")
    print(f"[Exp 1] Cost: ${exp1['estimated_cost_usd']:.4f}")
    print(f"[Exp 1] Binary macro F1 (original): {exp1['metric_1_binary_original']['macro_f1_SC']:.4f}")
    print(f"[Exp 1] Binary macro F1 (corrected): {exp1['metric_2_binary_corrected']['macro_f1_SC']:.4f}")
    print(f"[Exp 1] 3-way macro F1 (original): {exp1['metric_3_3way_original']['macro_f1']:.4f}")
    print(f"[Exp 1] 3-way macro F1 (corrected): {exp1['metric_4_3way_corrected']['macro_f1']:.4f}")

    # Run Experiment 2
    exp2 = await run_experiment_2(pairs)
    EXP2_OUT.write_text(json.dumps(exp2, indent=2))
    print(f"\n[Exp 2] Saved -> {EXP2_OUT}")
    print(f"[Exp 2] Cost: ${exp2['estimated_cost_usd']:.4f}")
    print(f"[Exp 2] Haiku accuracy: {exp2['haiku_accuracy']:.4f}")
    print(f"[Exp 2] Majority class baseline: {exp2['baselines']['majority_class']} = {exp2['baselines']['majority_class_accuracy']:.4f}")
    print(f"[Exp 2] Random baseline: {exp2['baselines']['random_3way_accuracy']:.4f}")

    total = exp1["estimated_cost_usd"] + exp2["estimated_cost_usd"]
    print(f"\n=== TOTAL COST: ${total:.4f} ===")


if __name__ == "__main__":
    asyncio.run(main())
