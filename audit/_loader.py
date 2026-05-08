"""SciFact dev-set loader.

Joins claims_dev.jsonl with corpus.jsonl into one (claim, doc) pair per
gold evidence document. Returns the 209 pairs with gold SUPPORT/CONTRADICT
labels that are the audit subset.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAIMS_DEV = REPO_ROOT / "data" / "scifact" / "claims_dev.jsonl"
CORPUS = REPO_ROOT / "data" / "scifact" / "corpus.jsonl"


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
    """Load all (claim, doc) pairs that have gold evidence in the dev set."""
    if not CLAIMS_DEV.exists():
        raise SystemExit(
            f"SciFact dataset not found at {CLAIMS_DEV.parent}. "
            "Run `bash data/download_scifact.sh` from the repo root first."
        )

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
                continue  # skip NEI-in-original (no gold evidence)
            for doc_id_str, rationales in evidence.items():
                doc = corpus.get(doc_id_str)
                if not doc or not rationales:
                    continue
                label = rationales[0]["label"]  # "SUPPORT" or "CONTRADICT"
                rationale_idxs = sorted({
                    idx for r in rationales for idx in r.get("sentences", [])
                })
                if rationale_idxs:
                    rationale_text = " ".join(
                        doc["sentences"][i] for i in rationale_idxs
                        if 0 <= i < len(doc["sentences"])
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
