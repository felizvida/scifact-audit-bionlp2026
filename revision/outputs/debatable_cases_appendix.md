# Appendix (Supplementary): Case-by-Case Detail on Debatable Cases

> **Reading note.** The main paper's Appendix A defines the *final* debatable set as **8 cases**, after a second-pass review upgraded 2 of an original 10 to confirmed errors (claims 847 and 1274). This supplementary file lists all **10 originally-debatable cases** for full historical transparency, with each case annotated by its final status. The sensitivity analysis in the main paper is computed on the 8 final debatables only — see `stats_results.md` for the corresponding numbers.

This file enumerates the 10 SciFact dev claims flagged by the LLM auditor and judged "debatable but defensible" at first-pass manual review. Source files:

- `results/stage2_manual_review/scifact_false_alarms_25_review.csv` (5 cases)
- `results/stage2_manual_review/scifact_false_alarms_remaining_24_review.csv` (5 cases)

A row qualifies if `my_verdict == "DEBATABLE"`. Of the 10 cases, **2 (claim 847 and claim 1274) were subsequently upgraded to confirmed errors** in `corrections/dev_corrections.json` (both reclassified to NEI). The remaining 8 stay as defensible-but-borderline. The "Final status" column records the upgrade where it occurred.

Original gold-label distribution among the 10: 7 SUPPORT, 3 CONTRADICT (claims 57, 847, 1041).
Among the 8 final debatables: 6 SUPPORT, 2 CONTRADICT (claims 57, 1041).

---

## Summary table

| Claim ID | Original Gold | LLM Suggestion | LLM Error Type | Final Status |
|---|---|---|---|---|
| 57 | CONTRADICT | ambiguous | causal_overclaim | debatable (not upgraded) |
| 163 | SUPPORT | ambiguous | generalization_beyond_evidence | debatable (not upgraded) |
| 431 | SUPPORT | ambiguous | other | debatable (not upgraded) |
| 540 | SUPPORT | ambiguous | generalization_beyond_evidence | debatable (not upgraded) |
| 847 | CONTRADICT | support | generalization_beyond_evidence | **confirmed error → NEI** |
| 982 | SUPPORT | support | generalization_beyond_evidence | debatable (not upgraded) |
| 1041 | CONTRADICT | ambiguous | other | debatable (not upgraded) |
| 1132 | SUPPORT | ambiguous | other | debatable (not upgraded) |
| 1150 | SUPPORT | ambiguous | causal_overclaim | debatable (not upgraded) |
| 1274 | SUPPORT | ambiguous | other | **confirmed error → NEI** |

---

## Case-by-case justifications

### Claim 57 (CONTRADICT, debatable)
**Claim:** *APOE4 expression in iPSC-derived neurons increases AlphaBeta production and tau phosphorylation, delaying GABA neuron degeneration.*
**Paper:** *Gain of toxic Apolipoprotein E4 effects in Human iPSC-Derived Neurons Is Ameliorated by a Small-Molecule Structure Corrector.*
**LLM reasoning:** the auditor flagged the gold CONTRADICT as a causal_overclaim error and proposed "ambiguous".
**Manual verdict:** the claim is partially right (Aβ and tau-p findings) and partially wrong ("delaying GABA degeneration" is not what the paper shows; the paper shows GABA *degeneration*). Gold = CONTRADICT is reasonable because the conjunctive claim is false on its delay clause. We treat this as defensibly CONTRADICT and exclude from the error set.

### Claim 163 (SUPPORT, debatable)
**Claim:** *Bariatric surgery has a positive impact on mental health.*
**Paper:** *Mental Health Conditions Among Patients Seeking and Undergoing Bariatric Surgery: A Meta-analysis.*
**LLM reasoning:** generalization_beyond_evidence; suggested "ambiguous".
**Manual verdict:** the abstract reports improvement in depression specifically, not "mental health" as a broad construct. SUPPORT is a stretch, but mental-health-as-superset-of-depression is a defensible reading of how a non-expert would interpret the claim. Excluded as borderline.

### Claim 431 (SUPPORT, debatable)
**Claim:** *FoxO3a activation in neuronal death is mediated by reactive oxygen species (ROS).*
**Paper:** *Stress-dependent regulation of FOXO transcription factors by the SIRT1 deacetylase.*
**LLM reasoning:** flagged as "other"; suggested "ambiguous".
**Manual verdict:** the abstract discusses FOXO/SIRT1 stress regulation but does not specifically isolate ROS as the mediator in neurons. SUPPORT is inferential rather than directly stated. Defensible but stretched — excluded.

### Claim 540 (SUPPORT, debatable)
**Claim:** *Hypothalamic glutamate neurotransmission is crucial to energy balance.*
**Paper:** *Synaptic glutamate release by ventromedial hypothalamic neurons is part of the neurocircuitry that prevents hypoglycemia.*
**LLM reasoning:** generalization_beyond_evidence; suggested "ambiguous".
**Manual verdict:** the evidence concerns glucose homeostasis (counter-regulation of hypoglycemia), which is part of, but narrower than, "energy balance". A reader could justify SUPPORT under a broad reading of the construct. Excluded as defensible.

### Claim 847 (CONTRADICT, **upgraded to confirmed error → NEI**)
**Claim:** *New drugs for tuberculosis often do not penetrate the necrotic portion of a tuberculosis lesion in high concentrations.*
**Paper:** *The association between sterilizing activity and drug distribution into tuberculosis lesions.*
**LLM reasoning:** the auditor argued the abstract supports the claim (moxifloxacin penetration is poor); flagged the gold CONTRADICT as wrong and suggested SUPPORT.
**Manual verdict (revised):** the rationale relies on rifampicin (a 1960s drug, not "new"), which does penetrate; moxifloxacin data is one drug, not "often". The claim cannot be evaluated from this evidence — NEI is correct. Listed in `dev_corrections.json` as `entity_mismatch` (C → N). Originally classified as debatable; on review we determined the gold CONTRADICT was indefensible and upgraded to a confirmed error. Already counted in the 11/209 figure.

### Claim 982 (SUPPORT, debatable)
**Claim:** *Proteins synthesized at the growth cone are ubiquitinated at a higher rate than proteins from the cell body.*
**Paper:** *Coupled local translation and degradation regulate growth cone collapse.*
**LLM reasoning:** generalization_beyond_evidence; suggested SUPPORT (i.e., the LLM agreed with gold but flagged the comparison as inferential).
**Manual verdict:** the explicit growth-cone-vs-cell-body comparison is not stated in the abstract; the inference is reasonable but not directly supported. SUPPORT is a stretch. Excluded.

### Claim 1041 (CONTRADICT, debatable)
**Claim:** *Replacement of histone H2A with H2A.Z slows gene activation in yeasts by stabilizing +1 nucleosomes.*
**Paper:** *Nucleosome stability mediated by histone variants H3.3 and H2A.Z.*
**LLM reasoning:** flagged as "other"; suggested "ambiguous".
**Manual verdict:** the cited paper is about vertebrate nucleosomes, not yeast. There is a genuine organism mismatch making evaluation difficult. CONTRADICT can be defended on grounds that the yeast-specific mechanism is not affirmed; "ambiguous" is also defensible. Excluded as borderline.

### Claim 1132 (SUPPORT, debatable)
**Claim:** *TCR/CD3 microdomains are a required to induce the immunologic synapse to activate T cells.*
**Paper:** *Full activation of the T cell receptor requires both clustering and conformational changes at CD3.*
**LLM reasoning:** flagged as "other"; suggested "ambiguous".
**Manual verdict:** the evidence supports TCR/CD3 clustering for activation but does not specifically tie this to the "immunologic synapse" construct. SUPPORT is reasonable on the clustering part; the synapse-specific clause is inferential. Excluded.

### Claim 1150 (SUPPORT, debatable)
**Claim:** *Tetraspanin-3 is a causative factor in the development of acute myelogenous leukemia.*
**Paper:** *Tetraspanin 3 Is Required for the Development and Propagation of Acute Myelogenous Leukemia.*
**LLM reasoning:** causal_overclaim; suggested "ambiguous".
**Manual verdict:** the paper shows Tetraspanin-3 is *required for* development and propagation — "causative factor" is a stronger phrasing than "required for", but in the colloquial reading, "required for development" can fairly imply causation. SUPPORT is a defensible reading. Excluded.

### Claim 1274 (SUPPORT, **upgraded to confirmed error → NEI**)
**Claim:** *The tip of the inner tube of the toxic type VI secretion system (T6SS) antibacterial effector in Escherichia coli (E. coli) carries toxic effector proteins.*
**Paper:** *PAAR-repeat proteins sharpen and diversify the Type VI secretion system spike.*
**LLM reasoning:** flagged as "other"; suggested "ambiguous".
**Manual verdict (revised):** the cited paper studies V. cholerae and A. baylyi T6SS, not E. coli. The general T6SS concept is supported but the species-specific clause is unsupported. On revisit we determined the species mismatch is dispositive: NEI. Listed in `dev_corrections.json` as `entity_mismatch` (S → N). Already counted in the 11/209 figure.

---

## Implications for the paper

These 10 cases are the natural "borderline" pile. The sensitivity analysis in `stats_results.md` shows that even if a reviewer disagreed with all our triage decisions and reclassified all 10 as errors, the dev error rate is bounded at 10.0% (95% CI 6.3%–14.9%), and the directional SUPPORT-skew remains in the 75%–88% range. Two cases (847, 1274) were already upgraded to NEI on internal review and are part of the 11-error tally; the other 8 remain genuinely defensible under either gold label or "ambiguous", and we explain each one above so readers can audit our judgement.
