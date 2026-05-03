"""
Unit tests for src/claim_extractor.py.

Covers edge cases that period-based splitting (the Day 1 mock) would fail on:
abbreviations, decimals, citations, et al. patterns, sentence-final periods,
empty / very short inputs.
"""

from src.claim_extractor import extract_claims, MIN_CLAIM_WORDS


def _print_result(label, claims):
    print(f"  [{label}] -> {len(claims)} claim(s)")
    for i, c in enumerate(claims, 1):
        print(f"     {i}. {c}")


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------

def test_handles_doctor_abbreviation():
    """'Dr. Smith' should not be split at the period after 'Dr'."""
    text = "Dr. Smith reported strong evidence for the treatment effect."
    claims = extract_claims(text)
    _print_result("doctor_abbrev", claims)
    assert len(claims) == 1, f"Expected 1 claim, got {len(claims)}"
    assert "Dr. Smith" in claims[0], "Lost 'Dr.' abbreviation"


def test_handles_decimal_number():
    """'5.7%' should not split at the decimal point."""
    text = "The treatment showed a 5.7% improvement compared to placebo."
    claims = extract_claims(text)
    _print_result("decimal_number", claims)
    assert len(claims) == 1
    assert "5.7" in claims[0], "Lost decimal number"


def test_handles_p_value():
    """'p=0.05' should not be split at the decimal."""
    text = "The result was statistically significant with p=0.05 in both cohorts."
    claims = extract_claims(text)
    _print_result("p_value", claims)
    assert len(claims) == 1
    assert "0.05" in claims[0]


def test_handles_citation_with_year():
    """'(Smith et al., 2018)' should stay attached to its sentence."""
    text = "Aspirin reduces heart attack risk (Smith et al., 2018)."
    claims = extract_claims(text)
    _print_result("citation_with_year", claims)
    assert len(claims) == 1
    assert "Smith" in claims[0] and "2018" in claims[0], "Lost citation"


def test_handles_ie_eg_abbreviations():
    """'i.e.' and 'e.g.' should not break sentences."""
    text = (
        "Many cardiovascular risk factors, e.g., high cholesterol and smoking, "
        "can be modified through lifestyle changes."
    )
    claims = extract_claims(text)
    _print_result("ie_eg", claims)
    assert len(claims) == 1, f"Expected 1 claim, got {len(claims)}: {claims}"


def test_multi_sentence_medical_answer():
    """A typical medical answer should split into multiple claims."""
    text = (
        "Aspirin reduces heart attack risk by 22 percent. "
        "This was confirmed in a 2018 meta-analysis. "
        "However, the benefit may not extend to patients over 70 years."
    )
    claims = extract_claims(text)
    _print_result("multi_sentence", claims)
    assert len(claims) == 3, f"Expected 3 claims, got {len(claims)}"


def test_filters_short_fragments():
    """Sentences shorter than MIN_CLAIM_WORDS should be filtered out."""
    text = "Yes. The treatment is effective in clinical trials."
    claims = extract_claims(text)
    _print_result("short_fragments", claims)
    # "Yes." (1 word) should be dropped; the second sentence kept
    assert len(claims) == 1, f"Expected 1 claim, got {len(claims)}"
    assert "treatment" in claims[0]


def test_empty_input():
    """Empty or whitespace-only input returns an empty list."""
    assert extract_claims("") == []
    assert extract_claims("   ") == []
    assert extract_claims("\n\t") == []
    print("  [empty_input] -> handled (empty list)")


def test_single_short_word():
    """A single very short answer returns no claims."""
    text = "Yes."
    claims = extract_claims(text)
    _print_result("single_short_word", claims)
    assert claims == [], f"Expected empty list, got {claims}"


def test_very_long_answer():
    """A long answer with many sentences should split correctly."""
    text = (
        "The clinical trial enrolled 240 patients across three sites. "
        "Patients were randomized to receive either the active drug or placebo. "
        "The primary endpoint was measured at 12 weeks. "
        "Adverse events were monitored throughout the study. "
        "The active drug group showed significant improvement compared to placebo."
    )
    claims = extract_claims(text)
    _print_result("long_answer", claims)
    assert len(claims) == 5, f"Expected 5 claims, got {len(claims)}"


# -------------------------------------------------------------------------
# Test runner
# -------------------------------------------------------------------------

def main():
    tests = [
        test_handles_doctor_abbreviation,
        test_handles_decimal_number,
        test_handles_p_value,
        test_handles_citation_with_year,
        test_handles_ie_eg_abbreviations,
        test_multi_sentence_medical_answer,
        test_filters_short_fragments,
        test_empty_input,
        test_single_short_word,
        test_very_long_answer,
    ]

    print("Running claim_extractor unit tests")
    print("=" * 60)
    print(f"MIN_CLAIM_WORDS = {MIN_CLAIM_WORDS}")
    print()

    passed = 0
    failed = 0
    for test_fn in tests:
        print(f"[{test_fn.__name__}]")
        try:
            test_fn()
            passed += 1
            print(f"  PASS")
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed (out of {len(tests)})")


if __name__ == "__main__":
    main()
