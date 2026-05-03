"""
End-to-end pipeline test for ConstraintCheck.

This test runs the full audit pipeline (with mock modules on Day 1)
and verifies that the output schema is correct and the aggregation
logic behaves as expected.
"""

import random
from src.agent import audit


def test_audit_returns_required_fields():
    """The audit() output must contain all required top-level fields."""
    result = audit(
        question="Does aspirin reduce heart attack risk?",
        answer="Aspirin reduces heart attack risk by 22 percent. This was confirmed in a 2018 meta-analysis."
    )

    required_fields = {
        "question", "answer", "claims",
        "reliability_score", "prediction", "failure_modes"
    }
    missing = required_fields - set(result.keys())
    assert not missing, f"Missing fields: {missing}"
    print("  [PASS] All required fields present")


def test_claims_have_required_subfields():
    """Each claim entry must have claim/evidence/verdict/reasoning."""
    result = audit(
        question="Does aspirin reduce heart attack risk?",
        answer="Aspirin reduces heart attack risk. This was confirmed in trials."
    )

    assert len(result["claims"]) > 0, "Should extract at least one claim"

    required_subfields = {"claim", "evidence", "verdict", "reasoning"}
    for i, c in enumerate(result["claims"]):
        missing = required_subfields - set(c.keys())
        assert not missing, f"Claim {i} missing fields: {missing}"
    print(f"  [PASS] All {len(result['claims'])} claims well-formed")


def test_verdict_values_are_valid():
    """Verdicts must be one of SUPPORTED/UNSUPPORTED/CONTRADICTED."""
    result = audit(
        question="Test",
        answer="Aspirin reduces heart attack risk. Trials confirm this. Doctors recommend caution."
    )

    valid = {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}
    for c in result["claims"]:
        assert c["verdict"] in valid, f"Invalid verdict: {c['verdict']}"
    print("  [PASS] All verdicts are valid values")


def test_prediction_is_binary():
    """Prediction must be 'trustworthy' or 'untrustworthy'."""
    result = audit(
        question="Test",
        answer="Aspirin reduces heart attack risk. Trials confirm this."
    )
    assert result["prediction"] in {"trustworthy", "untrustworthy"}
    print("  [PASS] Prediction is binary")


def test_reliability_score_in_range():
    """Reliability score must be in [0, 1]."""
    result = audit(
        question="Test",
        answer="Aspirin reduces heart attack risk. Trials confirm this."
    )
    score = result["reliability_score"]
    assert 0.0 <= score <= 1.0, f"Score out of range: {score}"
    print(f"  [PASS] Reliability score = {score} (in [0, 1])")


def test_aggregation_with_all_supported():
    """If all verdicts are SUPPORTED, prediction should be trustworthy."""
    # Force all SUPPORTED by patching the verifier
    from src import verifier as v_module

    original = v_module.verify
    v_module.verify = lambda c, e: {"verdict": "SUPPORTED", "reasoning": "forced"}

    try:
        result = audit(
            question="Test",
            answer="Claim one is fine. Claim two is also fine. Claim three is good too."
        )
        assert result["prediction"] == "trustworthy"
        assert result["reliability_score"] == 1.0
        assert result["failure_modes"] == []
        print("  [PASS] All-SUPPORTED -> trustworthy with score=1.0")
    finally:
        v_module.verify = original


def test_aggregation_with_one_contradiction():
    """One CONTRADICTED verdict should flip prediction to untrustworthy."""
    from src import verifier as v_module

    call_count = [0]

    def staged(c, e):
        call_count[0] += 1
        if call_count[0] == 1:
            return {"verdict": "CONTRADICTED", "reasoning": "forced"}
        return {"verdict": "SUPPORTED", "reasoning": "forced"}

    original = v_module.verify
    v_module.verify = staged

    try:
        result = audit(
            question="Test",
            answer="Claim one is fine. Claim two is also fine. Claim three is good too."
        )
        assert result["prediction"] == "untrustworthy"
        assert "contradiction" in result["failure_modes"]
        print("  [PASS] One CONTRADICTED -> untrustworthy")
    finally:
        v_module.verify = original


# --- Test runner ---------------------------------------------------------
def main():
    random.seed(42)

    tests = [
        test_audit_returns_required_fields,
        test_claims_have_required_subfields,
        test_verdict_values_are_valid,
        test_prediction_is_binary,
        test_reliability_score_in_range,
        test_aggregation_with_all_supported,
        test_aggregation_with_one_contradiction,
    ]

    print("Running ConstraintCheck pipeline tests")
    print("=" * 60)

    passed = 0
    failed = 0
    for test_fn in tests:
        print(f"\n[{test_fn.__name__}]")
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed.")
    else:
        print(f"{failed} test(s) failed.")


if __name__ == "__main__":
    main()
