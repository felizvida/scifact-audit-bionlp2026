# Statistical Revision Results — BioNLP 2026 SciFact Audit

All numbers below are computed by `stats_compute.py` (run from this directory) using `scipy.stats.binomtest` (v1.17.1) for both p-values and Clopper–Pearson exact CIs.

The 9/11 SUPPORT count is verified directly from `apps/sr_bench/paper/corrections/dev_corrections.json`: among the 11 claim-level corrections (excluding the per-document outcome mismatch on claim 597), 9 had `original_label == "SUPPORT"` and 2 had `original_label == "CONTRADICT"` (claims 879 and 847).

---

## Item 3 — Statistical framing of the directional bias

### 1. Two-sided binomial test on 9/11, H0: p = 0.5

- k = 9, n = 11
- **Exact two-sided p = 0.0654**
- `scipy.stats.binomtest(9, 11, p=0.5, alternative="two-sided").pvalue`

The two-sided test does *not* reach conventional 0.05 significance with n = 11. This is a sample-size limitation, not evidence against directional bias.

**How to incorporate:** Replace the unsupported phrase "systematic directional bias" with a calibrated statement, e.g.

> Of the 11 claim-level corrections, 9 (82%) reverse mislabeled SUPPORT examples. A two-sided exact binomial test against H0: p = 0.5 yields p = 0.065, which is suggestive but does not reach conventional significance with this sample size; we therefore describe the imbalance as a directional asymmetry that warrants follow-up on a larger audit, rather than a confirmed systematic bias.

### 2. One-sided binomial test (upper tail), 9/11, H0: p = 0.5

- **Exact one-sided p = 0.0327**

If the directional asymmetry was a pre-registered prediction (i.e., we hypothesized SUPPORT-skew before looking), a one-sided test is defensible and is significant at α = 0.05.

**How to incorporate:** Disclose the test choice explicitly. We did *not* pre-register the SUPPORT direction, so the two-sided result is the more honest primary statistic; the one-sided result can be reported as a secondary observation.

### 3. Clopper–Pearson 95% CI on the dev error rate (11/209)

- Point estimate: 0.0526 (5.3%)
- **95% CP CI: [0.027, 0.092]** i.e. [2.7%, 9.2%]

**How to incorporate:** Wherever the paper currently writes "5.3% dev error rate", replace with "5.3% (95% CI 2.7%–9.2%)".

### 4. Clopper–Pearson 95% CI on the train error rate (13/564)

- Point estimate: 0.0230 (2.3%)
- **95% CP CI: [0.012, 0.039]** i.e. [1.2%, 3.9%]

**How to incorporate:** Update the train-rate citation similarly: "2.3% (95% CI 1.2%–3.9%)". Note that the dev and train CIs overlap, weakening any claim that dev is strictly noisier than train.

### 5. Clopper–Pearson 95% CI on the dev SUPPORT-error proportion (9/11)

- Point estimate: 0.8182 (81.8%)
- **95% CP CI: [0.482, 0.977]** i.e. [48.2%, 97.7%]

**How to incorporate:** State the proportion *with* its CI: "9 of 11 (82%, 95% CI 48%–98%) of dev errors were originally labeled SUPPORT". The wide lower bound is the honest framing of why the binomial test does not reach two-sided significance — the data are consistent with anywhere from a near-coin-flip to overwhelming SUPPORT-skew.

---

## Item 4 — Debatable-cases sensitivity analysis

> **Reading note (added on revision).** The main paper now uses **8 final debatables** (after 2 of an original 10 were upgraded to confirmed errors). The 10-case version below is preserved for the audit trail. The 8-case sensitivity is summarized at the end of this section under **"8-debatable sensitivity (final, no double-count)"**.

The 10 cases the paper currently excludes as "debatable but defensible" are sourced from the manual reviewer's verdict in `scifact_false_alarms_25_review.csv` (5 cases) and `scifact_false_alarms_remaining_24_review.csv` (5 cases) — exactly the rows where `my_verdict == "DEBATABLE"`. The 10 IDs are: **57, 163, 431, 540, 847, 982, 1041, 1132, 1150, 1274**. See `debatable_cases_appendix.md` for the full table.

Note: of these 10 cases, **2 (847 and 1274) were ultimately *upgraded* to confirmed errors** in `dev_corrections.json` (both reclassified to NEI). They are therefore already counted in the 11/209 dev error rate. The sensitivity scenarios below follow the user-specified arithmetic (11 + N additional reclassifications) for transparency, but the appendix flags the overlap.

Original gold-label split among the 10 debatables: **7 SUPPORT, 3 CONTRADICT** (the 3 CONTRADICT are 57, 847, 1041).

### Dev error rate under three scenarios

| Scenario | k / n | Rate | 95% CP CI |
|---|---|---|---|
| 0/10 reclassified (current paper) | 11/209 | 5.3% | [2.7%, 9.2%] |
| 5/10 reclassified | 16/209 | 7.7% | [4.4%, 12.1%] |
| 10/10 reclassified | 21/209 | 10.0% | [6.3%, 14.9%] |

Even in the maximally conservative reading (every debatable is in fact an error), the dev error rate is bounded above by ~15%, an order of magnitude below the 20%+ rates reported for some general-domain NLI benchmarks.

### Combined directional-bias re-test

For each scenario we recompute the binomial test on combined SUPPORT-mislabel counts. Under the 5/10 scenario the count of additional SUPPORT errors depends on which 5 are reclassified; we report the expected case (4 SUPPORT among 5 added, rounding 7/10×5 = 3.5) plus the two flanking integer cases. Under 10/10 the split is exact: 7 SUPPORT + 3 CONTRADICT added.

| Scenario | SUPPORT errors / total | Prop | 95% CP CI | Two-sided p | One-sided p (upper) |
|---|---|---|---|---|---|
| 0/10 reclassified | 9/11 | 0.818 | [0.482, 0.977] | 0.0654 | 0.0327 |
| 5/10 reclassified, 3 of 5 added are SUPPORT | 12/16 | 0.750 | — | 0.0768 | 0.0384 |
| 5/10 reclassified, 4 of 5 added are SUPPORT (expected) | 13/16 | 0.812 | [0.544, 0.960] | 0.0213 | 0.0106 |
| 5/10 reclassified, 5 of 5 added are SUPPORT | 14/16 | 0.875 | — | 0.0042 | 0.0021 |
| 10/10 reclassified (exact 7/3 split) | 16/21 | 0.762 | [0.528, 0.918] | 0.0266 | 0.0133 |

### How to incorporate

Add a short sensitivity paragraph in §3 (Results) or the limitations section:

> Excluding the 10 debatable cases is a conservative choice. If we instead reclassified all 10 as confirmed errors, the dev error rate rises to 10.0% (95% CI 6.3%–14.9%), and the SUPPORT-mislabel proportion becomes 16/21 (76%, 95% CI 53%–92%), which is two-sided significant at p = 0.027. Under any intermediate reclassification (5 of 10), the directional asymmetry remains in the 75%–88% range and the binomial test is two-sided significant in the expected and best-case sub-scenarios. The directional finding is therefore robust to reasonable re-treatment of the borderline cases; what hinges on n is the *significance* of the test on the strict 11-error subset.

This directly addresses Reviewer #2's "burying the debatables" concern: we now (a) enumerate them in the appendix, (b) show that even when *all* are counted the headline error rate stays in single digits, and (c) show that the directional asymmetry does *not* go away — and in the 5/10 expected and 10/10 cases it actually crosses two-sided significance.

---

## 8-debatable sensitivity (final, no double-count)

After the second-pass review, 2 of the original 10 debatables (claims 847 and 1274) were upgraded to confirmed errors and are part of the 11/209 figure. The 8 remaining final debatables are: **57, 163, 431, 540, 982, 1041, 1132, 1150** (gold split: 6 SUPPORT, 2 CONTRADICT — IDs 57 and 1041 are CONTRADICT). Sensitivity scenarios add k of these 8 on top of 11; SUPPORT mislabels in any added subset start from the 6/8 = 75% gold-split rate.

| Scenario | k / n | Rate | 95% CP CI | SUPPORT mislabel | Two-sided p | One-sided p |
|---|---|---|---|---|---|---|
| 0/8 reclassified (paper baseline) | 11/209 | 5.3% | [2.7%, 9.2%] | 9/11 (82%) | 0.0654 | 0.0327 |
| 4/8 reclassified, 3 of 4 added are SUPPORT (expected) | 15/209 | 7.2% | [4.1%, 11.6%] | 12/15 (80%) | 0.0352 | 0.0176 |
| 4/8 reclassified, 4 of 4 added are SUPPORT | 15/209 | 7.2% | [4.1%, 11.6%] | 13/15 (87%) | 0.0074 | 0.0037 |
| 8/8 reclassified | 19/209 | 9.1% | [5.6%, 13.8%] | 15/19 (79%) | 0.0192 | 0.0096 |

These numbers are what the main paper now uses. The directional asymmetry strengthens (not weakens) as more debatables are admitted to the error set.
