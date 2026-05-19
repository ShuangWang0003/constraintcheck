"""
Golden verdict test cases for Mistral-7B verifier prompt tuning.

These 10 hand-crafted (claim, evidence, expected_verdict) tuples are the
gold standard for Day 5 prompt iteration. They cover:
  - 4 SUPPORTED: 2 easy (direct factual match) + 2 hard (semantic match)
  - 3 UNSUPPORTED: 2 easy (off-topic) + 1 hard (related topic but missing claim)
  - 3 CONTRADICTED: 2 easy (direct opposition) + 1 hard (implicit contradiction)

Use these to:
  - Iterate on prompt design (must achieve >=9/10 to consider stable)
  - Detect format-parsing regressions
  - Run as a quick sanity check before scaling to 30 / 50 samples
"""

GOLDEN_CASES = [
    # =====================================================================
    # SUPPORTED — 4 cases (2 easy, 2 hard)
    # =====================================================================
    {
        "case_id": "S1_easy_aspirin",
        "difficulty": "easy",
        "claim": "Aspirin reduces heart attack risk in patients with cardiovascular disease.",
        "evidence": [
            "A 2018 meta-analysis of 13 randomized controlled trials concluded that low-dose aspirin reduces the risk of myocardial infarction by 22% in adults with established cardiovascular disease.",
        ],
        "expected_verdict": "SUPPORTED",
        "rationale": "Evidence directly states the same conclusion as claim.",
    },
    {
        "case_id": "S2_easy_smoking",
        "difficulty": "easy",
        "claim": "Smoking is associated with an increased risk of lung cancer.",
        "evidence": [
            "Long-term tobacco smoking is the leading cause of lung cancer worldwide, accounting for an estimated 80-90% of all lung cancer cases according to multiple cohort studies.",
        ],
        "expected_verdict": "SUPPORTED",
        "rationale": "Evidence directly affirms the smoking-cancer link.",
    },
    {
        "case_id": "S3_hard_paraphrase",
        "difficulty": "hard",
        "claim": "Regular exercise improves cardiovascular fitness in elderly populations.",
        "evidence": [
            "Among adults aged 65 and older enrolled in a 12-month walking program, peak oxygen uptake (VO2 max) increased by an average of 14% compared to sedentary controls, indicating significant aerobic improvement.",
        ],
        "expected_verdict": "SUPPORTED",
        "rationale": "Evidence uses different vocabulary (VO2 max, walking program) but supports the same conclusion as claim (exercise improves cardio fitness in elderly).",
    },
    {
        "case_id": "S4_hard_indirect",
        "difficulty": "hard",
        "claim": "The treatment was effective for reducing tumor size.",
        "evidence": [
            "After 8 weeks of therapy, MRI imaging showed a mean tumor volume reduction of 31% (95% CI: 22-39%, p<0.001) compared to baseline measurements in the treatment cohort.",
        ],
        "expected_verdict": "SUPPORTED",
        "rationale": "Evidence quantitatively confirms tumor size reduction; semantically equivalent to 'effective for reducing tumor size'.",
    },

    # =====================================================================
    # UNSUPPORTED — 3 cases (2 easy, 1 hard)
    # =====================================================================
    {
        "case_id": "U1_easy_offtopic",
        "difficulty": "easy",
        "claim": "Vitamin D supplementation prevents osteoporosis in postmenopausal women.",
        "evidence": [
            "We performed a systematic review of laparoscopic cholecystectomy outcomes in patients with cholelithiasis, finding similar complication rates between elective and emergency procedures.",
        ],
        "expected_verdict": "UNSUPPORTED",
        "rationale": "Evidence is about gallbladder surgery; completely unrelated to vitamin D or osteoporosis.",
    },
    {
        "case_id": "U2_easy_fabricated_citation",
        "difficulty": "easy",
        "claim": "(Smith et al., 2020, Journal of Medical Research)",
        "evidence": [
            "MEDLINE, EMBASE, Cochrane Register of Controlled Trials, and citation review of relevant primary and review articles were searched for randomized trials.",
            "We performed a MEDLINE search for articles published from August 1955 to December 2008.",
        ],
        "expected_verdict": "UNSUPPORTED",
        "rationale": "Citation 'Smith et al., 2020' is a standalone reference; evidence is generic search-methodology text and does not contain or reference this specific citation.",
    },
    {
        "case_id": "U3_hard_partial_topic",
        "difficulty": "hard",
        "claim": "MIT researchers first reported this mechanism in 2019.",
        "evidence": [
            "The mechanism by which mitochondria regulate programmed cell death has been studied since the 1990s, with multiple research groups across Europe and Asia contributing to the current understanding.",
        ],
        "expected_verdict": "UNSUPPORTED",
        "rationale": "Evidence discusses mitochondrial PCD mechanism (relevant topic) but does NOT mention MIT or 2019. Specific institutional/year claim is unsupported.",
    },

    # =====================================================================
    # CONTRADICTED — 3 cases (2 easy, 1 hard)
    # =====================================================================
    {
        "case_id": "C1_easy_direct_opposite",
        "difficulty": "easy",
        "claim": "The drug significantly increased patient survival compared to placebo.",
        "evidence": [
            "After 24 months of follow-up, no significant difference in overall survival was observed between the treatment arm (median 18.2 months) and the placebo arm (median 17.9 months); hazard ratio 0.98 (95% CI: 0.85-1.13, p=0.78).",
        ],
        "expected_verdict": "CONTRADICTED",
        "rationale": "Evidence explicitly states no survival difference; claim asserts significant increase. Direct contradiction.",
    },
    {
        "case_id": "C2_easy_inverse",
        "difficulty": "easy",
        "claim": "High-dose vitamin C reduces the duration of common cold symptoms.",
        "evidence": [
            "A randomized controlled trial of 700 healthy adults found no significant difference in cold duration between those receiving 1000mg vitamin C daily and those receiving placebo (mean duration 6.8 vs 6.9 days, p=0.42).",
        ],
        "expected_verdict": "CONTRADICTED",
        "rationale": "Evidence shows no effect of vitamin C on cold duration; claim asserts reduction. Contradiction.",
    },
    {
        "case_id": "C3_hard_implicit",
        "difficulty": "hard",
        "claim": "The intervention had no effect on long-term complication rates.",
        "evidence": [
            "At 5-year follow-up, patients in the intervention group had a complication rate of 12%, compared to 28% in the control group (relative risk 0.43, p<0.001), demonstrating a sustained protective effect.",
        ],
        "expected_verdict": "CONTRADICTED",
        "rationale": "Evidence shows clear long-term complication reduction (12% vs 28%, p<0.001); claim asserts 'no effect'. Implicit contradiction.",
    },
]


# -------------------------------------------------------------------------
# Quick inspection
# -------------------------------------------------------------------------
if __name__ == "__main__":
    from collections import Counter

    print(f"Total golden cases: {len(GOLDEN_CASES)}")
    print()

    verdict_counts = Counter(c["expected_verdict"] for c in GOLDEN_CASES)
    print("By verdict:")
    for v, n in verdict_counts.most_common():
        print(f"  {v}: {n}")
    print()

    diff_counts = Counter(c["difficulty"] for c in GOLDEN_CASES)
    print("By difficulty:")
    for d, n in diff_counts.most_common():
        print(f"  {d}: {n}")
    print()

    print("=" * 75)
    print("All cases:")
    print("=" * 75)
    for c in GOLDEN_CASES:
        print(f"\n[{c['case_id']}]  ({c['difficulty']}, {c['expected_verdict']})")
        print(f"  CLAIM:    {c['claim']}")
        print(f"  EVIDENCE: {c['evidence'][0][:100]}...")
        print(f"  RATIONALE: {c['rationale']}")
