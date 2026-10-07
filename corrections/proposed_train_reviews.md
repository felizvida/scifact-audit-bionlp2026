# Two additional training-pair reviews: claims 417 and 378

Status: **proposed for maintainer adjudication, not confirmed corrections**.
Submitted October 7, 2026. These notes do not modify the released correction
JSON, counts, or reported benchmark results.

Both pairs were flagged during a small abstract-grounded verification pilot.
The suggested label is NEI relative to the specified evidence document, not a
claim that the biological statement is false. SciFact document IDs below are
dataset identifiers, not PubMed IDs. Sentence indices are zero-based.

| Split | Claim ID | SciFact document ID | Original label | Proposed label | Review issue |
| --- | ---: | ---: | --- | --- | --- |
| train | 417 | 6309659 | CONTRADICT | NEI | Effect modification versus a genotype-associated difference in reproductive duration |
| train | 378 | 11886686 | SUPPORT | NEI | Glucose regulation versus the broader energy-balance endpoint |

## Claim 417: companion to the existing claim 416 correction

Claim:

> Female carriers of the Apolipoprotein E4 (APOE4) allele have shorter lifetime exposure to estrogen due to a decreased reproductive period.

Assigned paper: *Reproductive period and risk of dementia in postmenopausal
women*, Geerlings et al. (2001).
[PubMed 11255424](https://pubmed.ncbi.nlm.nih.gov/11255424/),
[DOI](https://doi.org/10.1001/jama.285.11.1475).

The original rationale is sentence **12**. It reports a stronger relationship
between reproductive duration and dementia risk among APOE4 carriers. It does
not report whether carriers have shorter reproductive periods than noncarriers.
Our proposed reading is that this relationship neither establishes the claim
nor establishes its opposite; hence NEI rather than CONTRADICT.

The existing [training correction](train_corrections.json) for claim **416**
changes SUPPORT to NEI because the same document does not establish that APOE4
carriers have a *longer* reproductive period. Claim 417 reverses that direction
to *shorter*, cites the same document and rationale sentence, and currently has
CONTRADICT as its reference label. It is not present in the released corrections
at commit `5711f3fdf2305552df2b6e700dca2ebd7c8806e1`.

This is a request to examine the companion pair explicitly, not to propagate
416's correction automatically. A model's failure to find evidence is not proof
that none exists. If CONTRADICT is retained, which source finding establishes
the opposite of claim 417, rather than a different relationship involving
dementia risk?

## Claim 378: review only document 11886686

Claim:

> Energy balance requires hypothalamic glutamate neurotransmission.

Assigned paper: *Synaptic glutamate release by ventromedial hypothalamic neurons
is part of the neurocircuitry that prevents hypoglycemia*, Tong et al. (2007).
[PubMed 17488640](https://pubmed.ncbi.nlm.nih.gov/17488640/),
[PMC full-text link](https://pmc.ncbi.nlm.nih.gov/articles/PMC1934926/),
[DOI](https://doi.org/10.1016/j.cmet.2007.04.001).

The original rationale is sentence **7**. The abstract describes a role for
glutamate release in preventing low blood glucose. It reports impaired glucose
counterregulation after VGLUT2 deletion in SF1 neurons, but does not report
food-intake, body-weight or energy-expenditure outcomes. Our proposed NEI
reading distinguishes those glucose findings from the broader energy-balance
requirement in the claim.

There is a plausible alternative interpretation: the benchmark may allow the
broader energy-balance claim to be supported through scientific inference from
glucose regulation. Please adjudicate that inference rather than treating the
absence of identical terminology as decisive. Our review is limited to the
SciFact abstract and rationale; it does not establish what the full paper can
support. The full-text link above is supplied for further review, not as a claim
that we completed a full-text adjudication.

This is strictly a **document-level** proposal. Claim 378 has four evidence
documents in the original training data:

- 45154987
- 10534299
- **11886686**, the pair under review
- 17150648

Do not change the other three documents or mark claim 378 globally NEI. We make
no finding about those pairs. If a correction is accepted, please retain the
explicit `doc_id: 11886686` to avoid changing their labels.

## How the cases were identified and checked

- Original claim text, evidence-document mapping, labels and rationale indices
  were checked against SciFact `claims_train.jsonl` and `corpus.jsonl`.
- Astra (`gpt-6-astra`) and Sonnet (`claude-sonnet-5-5`) each assessed the full
  assigned abstract independently. Neither received the reference label or
  reference rationale selection. Both returned NOT_ENOUGH_INFORMATION for
  both pairs, and retained those labels after one paired exchange of their
  evidence assessments. Confidence values and model identities were hidden
  from peers. Separate Astra-only review also retained the labels.
- This agreement is a **screening signal**, not independent human validation.
  Repeated assessments from the same models are not independent expert votes.
  The proposals remain open to rejection or classification as debatable.
- These cases were identified before inspecting the correction release; the
  existing claim 416 correction was noticed in the subsequent literature review.
  No claim is made that this constitutes a blinded independent re-annotation
  study or that either model is scientifically validated.

## Reproduce the identifier and rationale checks

With the original SciFact release available at `data/scifact/`, this read-only
check verifies the three relevant claim/document mappings. It makes no model
calls and does not modify labels:

```python
import json
from pathlib import Path

data = Path("data/scifact")
claims = {
    row["id"]: row
    for row in map(json.loads, (data / "claims_train.jsonl").read_text().splitlines())
}
corpus = {
    str(row["doc_id"]): row
    for row in map(json.loads, (data / "corpus.jsonl").read_text().splitlines())
}
for claim_id, doc_id, label, indices in (
    (416, "6309659", "SUPPORT", {12}),
    (417, "6309659", "CONTRADICT", {12}),
    (378, "11886686", "SUPPORT", {7}),
):
    evidence = claims[claim_id]["evidence"][doc_id]
    assert {item["label"] for item in evidence} == {label}
    assert {i for item in evidence for i in item["sentences"]} == indices
    print(claim_id, doc_id, label, claims[claim_id]["claim"])
    for i in sorted(indices):
        print(i, corpus[doc_id]["abstract"][i])
assert set(claims[378]["evidence"]) == {
    "45154987", "10534299", "11886686", "17150648"
}
```

Underlying claims and evidence are from Wadden et al.,
[Fact or Fiction: Verifying Scientific Claims](https://aclanthology.org/2020.emnlp-main.609/)
(2020). The relationship to claim 416 is based on Sylvestre's
[BioNLP 2026 audit](https://aclanthology.org/2026.bionlp-1.9.pdf) and this
repository's released training corrections. No new adjudicated labels are
asserted by this document.
