#!/usr/bin/env python3
"""Build the three BioNLP 2026 revision annotation packets.

Inputs:
  - apps/sr_bench/priv/scifact_dataset/claims_dev.jsonl
  - apps/sr_bench/priv/scifact_dataset/corpus.jsonl
  - apps/sr_bench/priv/scifact_results/scifact_audit_gpt-5.4-mini_n209_*.json
  - apps/sr_bench/paper/corrections/dev_corrections.json

Outputs (in this directory):
  - blind_annotator_packet_dev.csv         (Packet 1, 209 rows, blind)
  - blind_annotator_packet_dev_unblinding_key.csv  (Packet 1 key)
  - llm_rejected_random_sample_30.csv      (Packet 2, 30 rows, not blind)

Run:
  python3 build_packets.py
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

# ----- paths -------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent  # repo root
DATASET = REPO_ROOT / "data" / "scifact"
CORRECTIONS_PATH = REPO_ROOT / "corrections" / "dev_corrections.json"
OUT_DIR = REPO_ROOT / "annotator_packets"

CLAIMS_PATH = DATASET / "claims_dev.jsonl"
CORPUS_PATH = DATASET / "corpus.jsonl"
AUDIT_PATH = REPO_ROOT / "results" / "stage1_llm_screen" / "scifact_audit_gpt-5.4-mini_n209_2026-04-02T14-33-55.931576Z.json"

SEED = 42
SAMPLE_SIZE = 30  # for packet 2

# ----- helpers -----------------------------------------------------------


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_pairs(claims: list[dict], corpus_by_id: dict[int, dict]) -> list[dict]:
    """Replicate the join in scifact_loader.ex.

    For each claim with non-empty evidence, emit one (claim, doc) pair per
    evidence doc. The label is the unique label across that doc's evidence
    entries (SciFact rationales for a single doc share a label; we sanity-
    check that). Rationale text is the concatenation of the cited sentences
    from the abstract.
    """
    pairs = []
    for claim in claims:
        ev = claim.get("evidence") or {}
        if not ev:
            continue
        for doc_id_str, ev_list in ev.items():
            doc_id = int(doc_id_str)
            doc = corpus_by_id.get(doc_id)
            if doc is None:
                raise RuntimeError(f"doc_id {doc_id} missing from corpus")
            labels = {e["label"] for e in ev_list}
            if len(labels) != 1:
                raise RuntimeError(
                    f"claim {claim['id']} doc {doc_id} mixed labels {labels}"
                )
            (gold_label,) = labels
            sent_indices = sorted(
                {idx for e in ev_list for idx in e.get("sentences", [])}
            )
            abstract_sents = doc["abstract"]
            rationale_sents = [
                abstract_sents[i] for i in sent_indices if 0 <= i < len(abstract_sents)
            ]
            rationale = " ".join(rationale_sents).strip()
            full_abstract = " ".join(abstract_sents).strip()
            pairs.append(
                {
                    "claim_id": claim["id"],
                    "doc_id": doc_id,
                    "claim": claim["claim"],
                    "paper_title": doc.get("title", ""),
                    "full_abstract": full_abstract,
                    "gold_rationale": rationale,
                    "original_gold": gold_label,
                }
            )
    return pairs


def confirmed_error_set(corrections: list[dict], claims_by_id: dict[int, dict]) -> set[tuple[int, int]]:
    """Return the set of (claim_id, doc_id) pairs that appear in dev_corrections.

    Many corrections list doc_id=null because the claim has a single evidence
    doc; we resolve those automatically. Claim 597 has 3 evidence docs and a
    null doc_id; the corrections file does not disambiguate, so we flag all 3
    (over-inclusive — caller can refine if needed).
    """
    flagged: set[tuple[int, int]] = set()
    for c in corrections:
        cid = c["claim_id"]
        did = c.get("doc_id")
        if cid not in claims_by_id:
            continue
        evidence_docs = [int(x) for x in claims_by_id[cid].get("evidence", {}).keys()]
        if did is not None:
            flagged.add((cid, int(did)))
        else:
            for d in evidence_docs:
                flagged.add((cid, d))
    return flagged


# ----- main --------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    claims = load_jsonl(CLAIMS_PATH)
    corpus = load_jsonl(CORPUS_PATH)
    corpus_by_id = {d["doc_id"]: d for d in corpus}
    claims_by_id = {c["id"]: c for c in claims}

    audit = load_json(AUDIT_PATH)
    audit_by_pair = {(r["id"], int(r["doc_id"])): r for r in audit["results"]}

    corrections_doc = load_json(CORRECTIONS_PATH)
    corrections = corrections_doc["corrections"]
    confirmed = confirmed_error_set(corrections, claims_by_id)

    pairs = build_pairs(claims, corpus_by_id)
    print(f"built {len(pairs)} dev claim-document pairs")
    assert len(pairs) == len(audit["results"]) == 209, (
        f"pair count mismatch: built={len(pairs)} audit={len(audit['results'])}"
    )

    # ---- Packet 1: blind annotator dev packet ---------------------------
    rng = random.Random(SEED)
    shuffled = list(pairs)
    rng.shuffle(shuffled)

    blind_path = OUT_DIR / "blind_annotator_packet_dev.csv"
    key_path = OUT_DIR / "blind_annotator_packet_dev_unblinding_key.csv"

    with blind_path.open("w", encoding="utf-8", newline="") as f_blind, \
         key_path.open("w", encoding="utf-8", newline="") as f_key:
        blind_writer = csv.DictWriter(
            f_blind,
            fieldnames=[
                "pair_uid",
                "claim",
                "paper_title",
                "full_abstract",
                "gold_rationale",
                "annotator_label",
                "annotator_confidence",
                "annotator_notes",
            ],
            quoting=csv.QUOTE_ALL,
        )
        blind_writer.writeheader()

        key_writer = csv.DictWriter(
            f_key,
            fieldnames=[
                "pair_uid",
                "claim_id",
                "doc_id",
                "original_gold",
                "llm_assessment",
                "is_confirmed_error_in_paper",
            ],
            quoting=csv.QUOTE_ALL,
        )
        key_writer.writeheader()

        for uid, p in enumerate(shuffled, start=1):
            blind_writer.writerow(
                {
                    "pair_uid": uid,
                    "claim": p["claim"],
                    "paper_title": p["paper_title"],
                    "full_abstract": p["full_abstract"],
                    "gold_rationale": p["gold_rationale"],
                    "annotator_label": "",
                    "annotator_confidence": "",
                    "annotator_notes": "",
                }
            )
            audit_row = audit_by_pair[(p["claim_id"], p["doc_id"])]
            key_writer.writerow(
                {
                    "pair_uid": uid,
                    "claim_id": p["claim_id"],
                    "doc_id": p["doc_id"],
                    "original_gold": p["original_gold"],
                    "llm_assessment": audit_row["assessment"],
                    "is_confirmed_error_in_paper": (p["claim_id"], p["doc_id"])
                    in confirmed,
                }
            )

    # Validate: confirmed errors should appear in the unblinding key as True.
    n_confirmed_in_key = sum(
        1
        for p in shuffled
        if (p["claim_id"], p["doc_id"]) in confirmed
    )
    print(f"confirmed-error pairs flagged in unblinding key: {n_confirmed_in_key}")
    print(f"  (corrections file lists {len(corrections)} entries; "
          f"{len(confirmed)} unique (claim,doc) flagged)")

    # ---- Packet 2: random sample of LLM-rejected pairs ------------------
    agree_pairs = [
        p for p in pairs
        if audit_by_pair[(p["claim_id"], p["doc_id"])]["assessment"] == "agree"
    ]
    print(f"LLM-rejected (assessment=agree) pairs: {len(agree_pairs)}")

    rng2 = random.Random(SEED)
    sampled = rng2.sample(agree_pairs, min(SAMPLE_SIZE, len(agree_pairs)))

    sample_path = OUT_DIR / "llm_rejected_random_sample_30.csv"
    with sample_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "claim_id",
                "doc_id",
                "original_gold",
                "llm_assessment",
                "claim",
                "paper_title",
                "full_abstract",
                "gold_rationale",
                "user_verdict",
                "user_notes",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for p in sampled:
            writer.writerow(
                {
                    "claim_id": p["claim_id"],
                    "doc_id": p["doc_id"],
                    "original_gold": p["original_gold"],
                    "llm_assessment": "agree",
                    "claim": p["claim"],
                    "paper_title": p["paper_title"],
                    "full_abstract": p["full_abstract"],
                    "gold_rationale": p["gold_rationale"],
                    "user_verdict": "",
                    "user_notes": "",
                }
            )
    print(f"wrote {sample_path.name} with {len(sampled)} rows")
    print(f"wrote {blind_path.name} with {len(shuffled)} rows")
    print(f"wrote {key_path.name}")


if __name__ == "__main__":
    main()
