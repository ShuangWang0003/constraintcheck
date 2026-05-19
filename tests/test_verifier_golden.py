"""
Step 5.4: Run the verifier on all 10 golden cases and report accuracy.

This is the canonical Day 5 sanity check. Goal: prompt iteration target
is >= 9/10. Below that, iterate the prompt template in src/verifier.py.
"""

import sys
import time
from collections import Counter

from src.verifier import verify
from tests.golden_verdict_cases import GOLDEN_CASES


def main():
    print("=" * 75)
    print(f"Verifier on {len(GOLDEN_CASES)} golden test cases")
    print("=" * 75)

    correct = 0
    correct_easy = 0
    correct_hard = 0
    total_easy = sum(1 for c in GOLDEN_CASES if c["difficulty"] == "easy")
    total_hard = sum(1 for c in GOLDEN_CASES if c["difficulty"] == "hard")
    confusion = Counter()  # (expected, predicted)
    failures = []

    t0 = time.time()
    for i, case in enumerate(GOLDEN_CASES, 1):
        result = verify(case["claim"], case["evidence"])
        expected = case["expected_verdict"]
        predicted = result["verdict"]
        is_correct = predicted == expected

        if is_correct:
            correct += 1
            if case["difficulty"] == "easy":
                correct_easy += 1
            else:
                correct_hard += 1
            mark = "✓"
        else:
            failures.append((case, predicted, result["reasoning"]))
            mark = "✗"

        confusion[(expected, predicted)] += 1

        print(f"\n[{i:2d}/10] {case['case_id']:30s} ({case['difficulty']:4s})  "
              f"{mark}  expected={expected}  got={predicted}")

    total_time = time.time() - t0

    # ---- Summary ---------------------------------------------------------
    print()
    print("=" * 75)
    print(f"Results: {correct}/10 correct ({correct*10}%)")
    print(f"  Easy: {correct_easy}/{total_easy}")
    print(f"  Hard: {correct_hard}/{total_hard}")
    print(f"  Total time: {total_time:.1f}s ({total_time/10:.1f}s/case)")
    print()

    # Confusion matrix
    print("Confusion matrix (rows=expected, cols=predicted):")
    verdicts = ["SUPPORTED", "UNSUPPORTED", "CONTRADICTED"]
    print(f"{'':16s}  " + "  ".join(f"{v:>13s}" for v in verdicts))
    for exp in verdicts:
        row = [confusion.get((exp, pred), 0) for pred in verdicts]
        print(f"{exp:16s}  " + "  ".join(f"{n:>13d}" for n in row))
    print()

    # ---- Failure details -------------------------------------------------
    if failures:
        print("=" * 75)
        print(f"Failed cases ({len(failures)}):")
        print("=" * 75)
        for case, predicted, reasoning in failures:
            print(f"\n[{case['case_id']}]  ({case['difficulty']})")
            print(f"  CLAIM: {case['claim']}")
            print(f"  EVIDENCE: {case['evidence'][0][:150]}...")
            print(f"  EXPECTED: {case['expected_verdict']}")
            print(f"  GOT:      {predicted}")
            print(f"  MODEL REASONING: {reasoning}")
            print(f"  CASE RATIONALE:  {case['rationale']}")
    else:
        print("All cases passed.")

    # Exit code
    sys.exit(0 if correct >= 9 else 1)


if __name__ == "__main__":
    main()
