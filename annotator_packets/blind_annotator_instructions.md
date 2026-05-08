# Blind Second-Annotator Audit: SciFact Dev Set

Thank you for agreeing to act as the independent second annotator for our BioNLP 2026 revision. Your annotations will let us compute Cohen's kappa against the original SciFact gold labels, addressing a reviewer concern about single-annotator bias in our gold-label-error audit.

## Goal

For each of the 209 claim-document pairs in `blind_annotator_packet_dev.csv`, decide whether the claim is **SUPPORT**, **CONTRADICT**, or **NEI** with respect to the assigned evidence paper. You may use **DEBATABLE** when you genuinely cannot decide.

You are blind to the original SciFact gold label and to any LLM screening output. Please do not look these up or attempt to recover them; doing so contaminates the inter-annotator agreement statistic we will report.

## Definitions (from Wadden et al., EMNLP 2020)

- **SUPPORT** — The evidence sentences entail the claim. A reasonable scientific reader, given only those sentences, would conclude the claim is true.
- **CONTRADICT** — The evidence sentences entail the negation of the claim, or directly state the opposite finding.
- **NEI (Not Enough Info)** — The evidence sentences neither support nor contradict the claim. The paper may discuss the same topic without addressing the specific assertion (different outcome, different population, missing comparator, etc.).
- **DEBATABLE** — Use sparingly. Reserved for cases where the claim is plausibly defensible under one reading and rejectable under another (e.g., overgeneralization, imprecise wording, ambiguous quantification). If you can decide after a second careful read, prefer SUPPORT / CONTRADICT / NEI.

## Ground rules

1. **Judge against the assigned paper only.** Do not consult later literature, Google Scholar, or your own subject knowledge to decide whether the claim is "true in the world." We are auditing whether the gold label faithfully reflects what *this paper* says, not whether the claim is correct.
2. **The gold rationale column shows the sentences the original SciFact annotators marked as evidence.** Treat them as a starting point but read the full abstract — the original rationale may be incomplete or misleading.
3. **Do not search for the original SciFact label.** It is intentionally withheld. If you accidentally see it, please tell us.
4. **Confidence (1–3):** 1 = low / unsure, 2 = medium, 3 = high. This is informational; we will not down-weight low-confidence labels.
5. **Notes column:** optional free text. Useful for flagging anything unusual (e.g., "claim is about preterm birth but paper only reports gestational diabetes" or "rationale sentence is taken out of context").

## Format

- File: `blind_annotator_packet_dev.csv` (UTF-8, double-quoted).
- Fill the `annotator_label`, `annotator_confidence`, and (optionally) `annotator_notes` columns. Do not modify any other column or reorder rows.
- Order has been randomized with a fixed seed; please process rows in order.

## Estimated time

3–5 hours total. Most pairs take 30–90 seconds; a handful require 5+ minutes. Please take breaks; calibration drift over a single 5-hour session is real.

## Returning the file

Save the completed CSV under the same filename and return it via the channel agreed in our email (likely encrypted email or shared drive). Do not commit it to a public repository.

## Questions

If you encounter ambiguous cases or suspect the rationale is mis-cited, flag in the notes column rather than asking us mid-audit — to keep the audit blind, we will only discuss specific pairs after you submit.
