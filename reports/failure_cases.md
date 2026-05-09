# ConstraintCheck — Failure Case Analysis

Five representative failure cases drawn from the 200-sample Experiment 1
evaluation. Cases cover both error directions (FP and FN) and all three
root-cause layers (retrieval, verifier, aggregation).

---

## Table of Contents

- [Case 1 — Nuanced "no difference" conclusion triggers false CONTRADICTED](#case-1)
- [Case 2 — Comparative claim mismatch causes total reliability collapse](#case-2)
- [Case 3 — Multi-claim dilution masks strong recommendation sentences](#case-3)
- [Case 4 — Fabricated percentage grounded by topic-adjacent evidence](#case-4)
- [Case 5 — Hallucinated citation hidden inside long multi-claim answer](#case-5)

---

<a name="case-1"></a>
## Case 1: Nuanced "no difference" conclusion triggers false CONTRADICTED

**Type**: False Positive (trustworthy → untrustworthy)

**Question**: Is first-line single-agent mitoxantrone in the treatment of
high-risk metastatic breast cancer patients as effective as combination
chemotherapy?

**LLM Answer**:
> No significant difference was detected between the treatment with
> mitoxantrone as a single agent and the combination of low-dose FEC in
> terms of response or survival; therefore, the imperative of the
> necessity of first-line combination chemotherapy for patients with
> high-risk metastatic breast cancer may be questioned. Since toxicity
> and quality of life score favored the single-agent mitoxantrone
> treatment arm, this treatment may be offered to patients preferring
> quality of life to a potential small prolongation of survival.

**Ground Truth**: trustworthy
**System Verdict**: untrustworthy — reliability=0.5, failure_modes=['contradiction']

**Per-claim Analysis**:
- Claim 1: "No significant difference was detected between mitoxantrone
  single agent and combination low-dose FEC in response or survival..."
  → **CONTRADICTED** — retrieval returned a passage reporting that
  combination chemotherapy produced higher response rates, which the
  verifier interpreted as contradicting "no significant difference."
- Claim 2: "Since toxicity and quality of life score favored single-agent
  mitoxantrone, this treatment may be offered..."
  → **SUPPORTED**

**Why it failed**:
This is the most instructive false positive in the dataset. The answer
reports a genuine null result ("no significant difference") — a valid and
common scientific conclusion. The retrieval corpus contains a passage
about combination chemotherapy efficacy that reports a positive effect.
The V2 prompt's CONTRADICTED rule ("same topic but disagrees with the
claim") fires correctly on a technicality: the claim says "no difference"
and the evidence shows "some difference." But this is a domain-specific
subtlety — different studies legitimately reach different conclusions on
the same question. The verifier has no way to distinguish between
"this study found no difference" (a valid claim) and "combination chemo
is better" (a contradicting claim) when the retrieval corpus contains
evidence from a different study. The aggregation's CONTRADICTED branch
then flags the entire answer as untrustworthy regardless of the 0.5
reliability score.

**What would fix it**:
A study-scoped retrieval step — only retrieve from the same PubMed paper
that generated the answer, not from the entire corpus. Alternatively,
add a "conflicting evidence" verdict category that distinguishes
"evidence from a different study disagrees" from "this evidence directly
refutes this claim."

---

<a name="case-2"></a>
## Case 2: Comparative claim mismatch causes total reliability collapse

**Type**: False Positive (trustworthy → untrustworthy)

**Question**: Is non-HDL-cholesterol a better predictor of long-term
outcome in patients after acute myocardial infarction compared to
LDL-cholesterol?

**LLM Answer**:
> Non-attaining non-HDL-C goal predicted MACE at long-term follow-up
> after AMI whereas non-attaining LDL-C goal was not associated with the
> higher risk. Therefore, non-HDL-C may be a more suitable target of
> dyslipidemia treatment than LDL-C in patients after AMI.

**Ground Truth**: trustworthy
**System Verdict**: untrustworthy — reliability=0.0, failure_modes=['contradiction']

**Per-claim Analysis**:
- Claim 1: "Non-attaining non-HDL-C goal predicted MACE at long-term
  follow-up after AMI whereas non-attaining LDL-C goal was not
  associated with higher risk."
  → **CONTRADICTED** — retrieval returned a lipid management guideline
  passage emphasizing LDL-C as the primary target, which the verifier
  read as directly contradicting the claim that LDL-C goal non-attainment
  is not associated with risk.
- Claim 2: "Non-HDL-C may be a more suitable target of dyslipidemia
  treatment than LDL-C in patients after AMI."
  → **CONTRADICTED** — same evidence passage, same mismatch.

**Why it failed**:
Both claims are comparative in nature — they assert the superiority of
one biomarker over another. The retrieval corpus contains lipid guideline
passages that strongly endorse LDL-C as the primary target, which is the
standard-of-care view. The verifier correctly identifies that the
guideline passage disagrees with the claims. But this is a legitimate
scientific debate — the answer is reporting a study's finding that
challenges the guideline, not fabricating content. reliability=0.0 and
two CONTRADICTED verdicts means the aggregation flags this as untrustworthy
with maximum confidence. This is the hardest class of false positive to
fix: genuine scientific dissent looks identical to hallucinated content
from the verifier's perspective.

**What would fix it**:
No prompt fix is viable. The correct solution is to scope retrieval to
the source paper's own context passages (available in PubMedQA's
`context` field) rather than the global corpus. The source paper's
evidence would support the claim; external guideline passages create
spurious contradictions.

---

<a name="case-3"></a>
## Case 3: Multi-claim dilution masks strong recommendation sentences

**Type**: False Positive (trustworthy → untrustworthy)

**Question**: Oral mucocele/ranula: Another HIV-related salivary gland
disease?

**LLM Answer**:
> This study presents a different clinical picture of oral
> mucoceles/ranulas, as observed in HIV-positive patients. Additionally,
> it suggests a possible clinical link between the two pathologies.
> The authors strongly support the suggestion that oral mucocele/ranula
> is an HIV-related salivary gland disease.

**Ground Truth**: trustworthy
**System Verdict**: untrustworthy — reliability=0.333, failure_modes=['unsupported_claim', 'contradiction']

**Per-claim Analysis**:
- Claim 1: "This study presents a different clinical picture of oral
  mucoceles/ranulas as observed in HIV-positive patients."
  → **SUPPORTED**
- Claim 2: "It suggests a possible clinical link between the two
  pathologies."
  → **UNSUPPORTED** — retrieval returns HIV salivary gland passages
  but none that specifically discuss the clinical link to mucoceles.
- Claim 3: "The authors strongly support the suggestion that oral
  mucocele/ranula is an HIV-related salivary gland disease."
  → **CONTRADICTED** — retrieval returns a passage that lists known
  HIV-related salivary conditions without mentioning mucoceles;
  verifier reads omission as contradiction.

**Why it failed**:
Claim 3 is a meta-claim — it reports the authors' own conclusion rather
than an independently verifiable fact. Such claims ("the authors support
the suggestion that...") cannot be grounded in external evidence because
the evidence would need to be the paper itself. Claim 2 is a hedged
claim ("suggests a possible link") — hedged language is harder to
ground because retrieval needs to find evidence that makes the same
qualified assertion. With 1/3 SUPPORTED, reliability=0.333 triggers
the threshold rule, and CONTRADICTED on Claim 3 triggers the
CONTRADICTED branch. Both aggregation paths fire simultaneously.

**What would fix it**:
Two targeted improvements: (1) filter meta-claims ("the authors
suggest/support/conclude") in `claim_extractor.py` — these are
unverifiable by design; (2) add a "hedged" handling path in the
verifier for claims with "possible," "may," "suggests" language,
where partial evidence is sufficient for SUPPORTED.

---

<a name="case-4"></a>
## Case 4: Fabricated percentage grounded by topic-adjacent evidence

**Type**: False Negative (untrustworthy → trustworthy)

**Question**: Does preloading with colloids prevent hemodynamic changes
when neurosurgical patients are subsequently changed to the seated position?

**LLM Answer**:
> It is concluded that preloading colloid fluid prior to repositioning
> could prevent the decrease of systolic blood pressure and central
> venous pressure during sitting positioning without other complications.
> The intervention improved outcomes by 63% compared with controls.

**Ground Truth**: untrustworthy (unsupported_numerical_claim)
**System Verdict**: trustworthy — reliability=1.0, no failure modes detected

**Per-claim Analysis**:
- Claim 1: "Preloading colloid fluid could prevent the decrease of
  systolic blood pressure and central venous pressure during sitting
  positioning without other complications."
  → **SUPPORTED** — retrieval correctly finds evidence about colloid
  preloading and hemodynamic stability.
- Claim 2 (poisoned): "The intervention improved outcomes by 63%
  compared with controls."
  → **SUPPORTED** — retrieval returns an intervention study passage
  reporting outcome improvements in a different clinical context;
  the verifier sees "intervention" + "outcomes" + "controls" and
  judges SUPPORTED without checking the specific number.

**Why it failed**:
This is the clearest demonstration of the verifier's core weakness on
numerical fabrication. The poisoned sentence contains a fabricated
percentage (63%) appended to a real clinical conclusion. The V4 prompt's
Rule 1 ("if the claim contains a specific percentage, choose UNSUPPORTED
unless that exact number appears in the evidence") should have caught
this — but the retrieved passage happened to contain percentage figures
in a related intervention context. The verifier's reasoning was:
"evidence discusses intervention outcomes with comparable metrics,
which supports the claim." The specific number 63% was not checked.
reliability=1.0 because both claims were judged SUPPORTED, making this
the highest-confidence false negative in the dataset.

**What would fix it**:
Stricter numerical grounding: extract all numbers from the claim,
verify each appears in the evidence with the same unit and approximate
context. A lightweight regex post-processing step on the verifier's
output could flag cases where the claim contains a percentage not
present in any evidence passage.

---

<a name="case-5"></a>
## Case 5: Hallucinated citation hidden inside long multi-claim answer

**Type**: False Negative (untrustworthy → trustworthy)

**Question**: Does patella position influence ligament balancing in
total knee arthroplasty?

**LLM Answer**:
> The gaps in patella eversion demonstrated smaller gaps both in knee
> extension and flexion position compared to the gaps of patella
> reduction position. The amount of decreased gaps was more definite
> in knee flexion position. Therefore, the intraoperative patellar
> positioning has influence on the measurement of the joint gap.
> Keeping the patella in reduced position is important during gap
> balancing. (Rodriguez and Kim, 2022, Nature Medicine Letters)

**Ground Truth**: untrustworthy (hallucinated_citation)
**System Verdict**: trustworthy — reliability=0.8, failure_modes=['unsupported_claim']

**Per-claim Analysis**:
- Claims 1-4: All about patella gap measurements and clinical
  recommendations → all judged **SUPPORTED** by relevant retrieved
  evidence about knee arthroplasty.
- Claim 5 (poisoned): "(Rodriguez and Kim, 2022, Nature Medicine Letters)"
  → judged **UNSUPPORTED** (correctly) — retrieval finds no matching
  citation.

**Why it failed**:
With 5 claims total, 4 SUPPORTED and 1 UNSUPPORTED, reliability=0.8.
This exceeds the 0.7 threshold, so the aggregation rule passes the
answer as trustworthy despite the hallucinated citation. The verifier
correctly identified the citation as UNSUPPORTED — the detection
module worked — but the aggregation module's threshold-based rule
treats citation fabrication the same as any other UNSUPPORTED claim.
In a 5-claim answer, one fabricated citation only costs 0.2 reliability
points, insufficient to trigger the untrustworthy label.

**What would fix it**:
Two options: (1) add a special aggregation rule — "if any claim is a
hallucinated citation (format: Author et al., Year, Journal), flag
as untrustworthy regardless of reliability score," mirroring the
existing CONTRADICTED branch; (2) lower the threshold specifically
for citation-format claims. The current system treats citation
fabrication as equivalent to a missing supporting fact, but citations
are categorically different — they assert a specific attributable
source, and fabricating one is a stronger form of hallucination.

---

## Summary

| Case | Type | Root Cause Layer | Fix Layer |
|------|------|-----------------|-----------|
| 1 — Null result contradiction | FP | Retrieval (cross-study conflict) | Retrieval scoping |
| 2 — Comparative claim vs guideline | FP | Retrieval (cross-study conflict) | Retrieval scoping |
| 3 — Meta-claim + hedged language | FP | Claim extraction + Verifier | Claim filter |
| 4 — Numerical fabrication grounded | FN | Verifier (number not checked) | Post-processing |
| 5 — Citation diluted by long answer | FN | Aggregation (threshold too lenient) | Aggregation rule |

**Key pattern**: 2 of 5 failures share the same root cause (cross-study
retrieval conflict), suggesting that scoping retrieval to source-paper
contexts would be the highest-leverage single improvement. The remaining
3 failures are each distinct, requiring targeted fixes at different
pipeline layers.
