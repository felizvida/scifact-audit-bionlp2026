# Corrected SciFact Gold Labels

Two JSON files containing the gold-label corrections identified in the audit:

- [`dev_corrections.json`](dev_corrections.json) — 11 claim-level corrections + 1 per-document outcome mismatch in the SciFact dev set (300 claims, 209 audited with gold evidence).
- [`train_corrections.json`](train_corrections.json) — 13 claim-level corrections in the SciFact training set (809 claims, 564 audited).

## Schema

```json
{
  "description": "...",
  "source_paper": "Gold Label Errors in the SciFact Benchmark: An LLM-Assisted Annotation Audit",
  "corrections": [
    {
      "claim_id": 593,
      "doc_id": 19675911,            // null if correction applies to all evidence docs of this claim
      "original_label": "SUPPORT",
      "corrected_label": "CONTRADICT",
      "error_type": "label_reversal",
      "justification": "Evidence states incidence 'did not change over time'; claim says 'decreased by 10%'"
    },
    ...
  ]
}
```

### Error types

- `label_reversal` — gold label directly contradicts the assigned evidence
- `outcome_mismatch` — claim asks about one outcome but evidence reports a different one
- `entity_mismatch` — claim and evidence refer to different biological entities (organism, drug class, cell type)
- `overgeneralization` — claim is broader than what the evidence supports
- `causal_misread` — claim reads effect modification as direct causation
- `rationale_error` — evidence text does not contain the asserted facts
- `modality_mismatch` — claim treats a modeled projection as observed result
- `numerical_mismatch` — quantitative discrepancy between claim and evidence
- `per_document_outcome_mismatch` — only one of multiple evidence documents is mismatched (claim 597 has 3 evidence documents; the third one labels mortality as if it were incidence)

## How to apply these corrections

```python
import json

with open("corrections/dev_corrections.json") as f:
    corr = {c["claim_id"]: c for c in json.load(f)["corrections"]}

# In your evaluation loop, after loading SciFact dev claims:
for claim in dev_claims:
    if claim["id"] in corr:
        claim["label"] = corr[claim["id"]]["corrected_label"]
        # Note: a corrected_label of "NEI" means the original label is unsupported
        # by the assigned evidence and the pair should be excluded from binary
        # SUPPORT/CONTRADICT evaluation.
```

## Important caveats

1. **Single-annotator caveat.** These corrections were made by one human annotator (the paper's first author), assisted on the 57 LLM-flagged disagreements by a frontier-LLM second opinion in chat mode. They have not yet been ratified by an independent second human rater. The blind annotator packet in [`../annotator_packets/`](../annotator_packets/) is provided for that purpose.

2. **Defensible-but-borderline cases.** 8 cases were identified as "debatable but defensible" and intentionally left at their original gold labels. See `revision/outputs/debatable_cases_appendix.md` for the case-by-case justifications and the sensitivity analysis showing the headline error rate stays under 10% even if all 8 were reclassified.

3. **Source-paper grounding.** Corrected labels are determined solely by the paper assigned as evidence in SciFact, not by later literature or external knowledge. Several of the corrected claims happen to be true in light of subsequent research, but the *assigned evidence* does not establish them; we therefore mark them NEI relative to that evidence.

4. **Recommendation, not replacement.** The paper recommends that an independent multi-annotator re-audit (rather than these single-annotator corrections) be the basis of any official corrected SciFact release.
