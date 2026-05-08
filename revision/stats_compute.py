"""
Statistical revision computations for BioNLP 2026 SciFact audit paper.

Item 3: Statistical framing of the directional bias.
  - Two-sided + one-sided binomial test on 9/11.
  - Clopper-Pearson 95% CIs on dev (11/209), train (13/564), and 9/11.

Item 4: Debatable-cases sensitivity analysis.
  - 10 DEBATABLE cases sourced from
    scifact_false_alarms_25_review.csv + scifact_false_alarms_remaining_24_review.csv
    (rows where my_verdict == 'DEBATABLE'). Two of those (847, 1274) were
    later upgraded to confirmed errors and appear in dev_corrections.json.
  - Dev error rate + 95% CI under three scenarios: +0, +5, +10.
  - Combined directional bias: how many of the new errors are mislabeled
    SUPPORT, with binomial tests on the combined counts.

Run: python3 stats_compute.py
"""

import csv
import json
from pathlib import Path

from scipy.stats import binomtest


REPO_ROOT = Path(__file__).resolve().parent.parent  # repo root
DEV_CORRECTIONS = REPO_ROOT / "corrections" / "dev_corrections.json"
FA_25 = REPO_ROOT / "results" / "stage2_manual_review" / "scifact_false_alarms_25_review.csv"
FA_24 = REPO_ROOT / "results" / "stage2_manual_review" / "scifact_false_alarms_remaining_24_review.csv"


# ---------------------------------------------------------------------------
# Item 3: directional-bias statistics
# ---------------------------------------------------------------------------

def load_dev_corrections():
    with open(DEV_CORRECTIONS) as f:
        return json.load(f)


def count_support_directional_bias(corrections):
    """Count claim-level corrections (excluding the per-document error 597)
    whose original gold label was SUPPORT."""
    claim_level = [
        c for c in corrections["corrections"]
        if c["error_type"] != "per_document_outcome_mismatch"
    ]
    n = len(claim_level)
    k_support = sum(1 for c in claim_level if c["original_label"] == "SUPPORT")
    return n, k_support, claim_level


def binom_two_sided(k, n, p=0.5):
    res = binomtest(k, n, p=p, alternative="two-sided")
    return res.pvalue, res.proportion_ci(confidence_level=0.95, method="exact")


def binom_one_sided_upper(k, n, p=0.5):
    res = binomtest(k, n, p=p, alternative="greater")
    return res.pvalue


def clopper_pearson_ci(k, n, conf=0.95):
    """Exact (Clopper-Pearson) CI via binomtest's proportion_ci."""
    res = binomtest(k, n, p=0.5, alternative="two-sided")
    ci = res.proportion_ci(confidence_level=conf, method="exact")
    return ci.low, ci.high


# ---------------------------------------------------------------------------
# Item 4: 10 debatable cases
# ---------------------------------------------------------------------------

def load_debatables():
    rows = []
    for path in (FA_25, FA_24):
        with open(path) as f:
            for r in csv.DictReader(f):
                if r.get("my_verdict", "").strip() == "DEBATABLE":
                    r["_source"] = path.name
                    rows.append(r)
    return rows


def directional_bias_in_debatables(debatables):
    """Of the 10 debatables, how many had original gold label SUPPORT?"""
    support = [d for d in debatables if d["gold_label"] == "SUPPORT"]
    contradict = [d for d in debatables if d["gold_label"] == "CONTRADICT"]
    return len(support), len(contradict)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    out = []

    # Item 3 ----------------------------------------------------------------
    out.append("# Item 3: directional bias statistics\n")

    corr = load_dev_corrections()
    n_claim, k_support, claim_level = count_support_directional_bias(corr)
    out.append(f"Claim-level corrections: n={n_claim}, original SUPPORT={k_support}\n")
    assert n_claim == 11 and k_support == 9, (n_claim, k_support)

    # 1. Two-sided binomial test on 9/11, p0=0.5
    p_two = binomtest(9, 11, p=0.5, alternative="two-sided").pvalue
    out.append(f"Binomial two-sided (9/11, p0=0.5): p = {p_two:.4f}\n")

    # 2. One-sided upper-tail
    p_up = binomtest(9, 11, p=0.5, alternative="greater").pvalue
    out.append(f"Binomial one-sided upper (9/11, p0=0.5): p = {p_up:.4f}\n")

    # 3. Dev error rate CI: 11/209
    lo, hi = clopper_pearson_ci(11, 209)
    out.append(f"Dev error rate 11/209 = {11/209:.4f}, 95% CP CI [{lo:.3f}, {hi:.3f}]\n")

    # 4. Train error rate CI: 13/564
    lo_t, hi_t = clopper_pearson_ci(13, 564)
    out.append(f"Train error rate 13/564 = {13/564:.4f}, 95% CP CI [{lo_t:.3f}, {hi_t:.3f}]\n")

    # 5. Dev SUPPORT-error proportion CI: 9/11
    lo_s, hi_s = clopper_pearson_ci(9, 11)
    out.append(f"Dev SUPPORT-error proportion 9/11 = {9/11:.4f}, 95% CP CI [{lo_s:.3f}, {hi_s:.3f}]\n")

    # Item 4 ----------------------------------------------------------------
    out.append("\n# Item 4: debatable-cases sensitivity analysis\n")

    debatables = load_debatables()
    out.append(f"Debatable cases identified: {len(debatables)}\n")
    assert len(debatables) == 10, len(debatables)

    n_supp_deb, n_contra_deb = directional_bias_in_debatables(debatables)
    out.append(
        f"Of 10 debatables: {n_supp_deb} originally SUPPORT, {n_contra_deb} originally CONTRADICT\n"
    )

    # Already-confirmed overlap
    confirmed_ids = {593, 879, 1385, 343, 1368, 770, 1216, 1274, 208, 808, 847}
    overlap = [int(d["id"]) for d in debatables if int(d["id"]) in confirmed_ids]
    out.append(f"Debatables already in confirmed-11: {sorted(overlap)} (these contributed to the 9/11 SUPPORT count already; reclassifying them again is conceptually a no-op).\n")

    # Sensitivity analysis: scenarios as specified by reviewer
    # Treat per the user's framing: 11/209 baseline + N reclassified additions
    scenarios = [
        ("0/10 reclassified (current paper)", 11, 209, 9, 11),
        ("5/10 reclassified", 16, 209, None, 16),
        ("10/10 reclassified", 21, 209, None, 21),
    ]

    # For 5/10 and 10/10 we need to assume which 5 are reclassified.
    # Conservative directional-bias estimate: assume the 5/10 added errors
    # respect the marginal proportion of SUPPORT among the debatables
    # (7/10 = 70%). For the 10/10 case, it is exact (7 SUPPORT among the 10).
    n_supp_added = {
        "0/10 reclassified (current paper)": 0,
        "5/10 reclassified": 5 * (n_supp_deb / 10),  # expected 3.5
        "10/10 reclassified": n_supp_deb,            # exact 7
    }

    out.append("\nDev error rate sensitivity:\n")
    for label, k_total, n_total, k_supp_existing, k_supp_combined in scenarios:
        rate = k_total / n_total
        lo_e, hi_e = clopper_pearson_ci(k_total, n_total)
        out.append(
            f"  {label}: {k_total}/{n_total} = {rate:.4f}, "
            f"95% CP CI [{lo_e:.3f}, {hi_e:.3f}]\n"
        )

    out.append("\nCombined directional-bias under each scenario:\n")
    out.append("(assumption: 5/10 scenario adds 5 random debatables; expected SUPPORT = 7/10*5 = 3.5; "
               "for the integer test we round to 4.)\n")

    # 0/10
    p2_0 = binomtest(9, 11, p=0.5, alternative="two-sided").pvalue
    p1_0 = binomtest(9, 11, p=0.5, alternative="greater").pvalue
    out.append(f"  0/10 reclassified: 9/11 SUPPORT, two-sided p={p2_0:.4f}, one-sided p={p1_0:.4f}\n")

    # 5/10 reclassified -> add 4 SUPPORT (round of 3.5) of 5 -> 13/16
    k_supp_5 = 9 + 4
    n_5 = 16
    p2_5 = binomtest(k_supp_5, n_5, p=0.5, alternative="two-sided").pvalue
    p1_5 = binomtest(k_supp_5, n_5, p=0.5, alternative="greater").pvalue
    lo_5, hi_5 = clopper_pearson_ci(k_supp_5, n_5)
    out.append(
        f"  5/10 reclassified (assumed 4 SUPPORT among the 5 added): "
        f"{k_supp_5}/{n_5} SUPPORT, prop {k_supp_5/n_5:.3f} "
        f"95% CP CI [{lo_5:.3f},{hi_5:.3f}], two-sided p={p2_5:.4f}, one-sided p={p1_5:.4f}\n"
    )

    # Also report the worst-case (5/5 added are CONTRADICT) and best-case (5/5 SUPPORT)
    for added_supp in (3, 5):
        k = 9 + added_supp
        p2 = binomtest(k, 16, p=0.5, alternative="two-sided").pvalue
        p1 = binomtest(k, 16, p=0.5, alternative="greater").pvalue
        out.append(
            f"    sensitivity within 5/10: if {added_supp}/5 added are SUPPORT, "
            f"{k}/16, two-sided p={p2:.4f}, one-sided p={p1:.4f}\n"
        )

    # 10/10 reclassified -> add 7 SUPPORT, 3 CONTRADICT, total 16 SUPPORT in 21
    k_supp_10 = 9 + n_supp_deb
    n_10 = 21
    p2_10 = binomtest(k_supp_10, n_10, p=0.5, alternative="two-sided").pvalue
    p1_10 = binomtest(k_supp_10, n_10, p=0.5, alternative="greater").pvalue
    lo_10, hi_10 = clopper_pearson_ci(k_supp_10, n_10)
    out.append(
        f"  10/10 reclassified (exact 7 SUPPORT, 3 CONTRADICT added): "
        f"{k_supp_10}/{n_10} SUPPORT, prop {k_supp_10/n_10:.3f} "
        f"95% CP CI [{lo_10:.3f},{hi_10:.3f}], two-sided p={p2_10:.4f}, one-sided p={p1_10:.4f}\n"
    )

    # Print everything
    for line in out:
        print(line, end="")

    return out, debatables


if __name__ == "__main__":
    main()
