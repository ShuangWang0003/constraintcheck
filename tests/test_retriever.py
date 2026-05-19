"""
Unit tests for src/retriever.py.

Verifies:
  - Singleton retrieve() returns the right type / shape
  - top_k controls result count
  - Empty / whitespace queries return empty lists
  - Real medical claims retrieve topically relevant passages
"""

from src.retriever import retrieve


def _print(label, results):
    print(f"  [{label}] -> {len(results)} result(s)")


# -------------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------------

def test_returns_list_of_strings():
    """retrieve() returns a list of strings."""
    r = retrieve("Aspirin and heart disease.", top_k=3)
    assert isinstance(r, list), f"Expected list, got {type(r)}"
    assert all(isinstance(x, str) for x in r), "Not all results are strings"
    _print("returns_list_of_strings", r)


def test_top_k_controls_count():
    """top_k=1 returns 1 result, top_k=5 returns 5."""
    r1 = retrieve("Diabetes management.", top_k=1)
    r5 = retrieve("Diabetes management.", top_k=5)
    assert len(r1) == 1, f"Expected 1, got {len(r1)}"
    assert len(r5) == 5, f"Expected 5, got {len(r5)}"
    _print("top_k_controls_count (k=1)", r1)
    _print("top_k_controls_count (k=5)", r5)


def test_empty_query_returns_empty_list():
    """Empty / whitespace queries return []."""
    assert retrieve("") == []
    assert retrieve("   ") == []
    assert retrieve("\n\t") == []
    print("  [empty_query] -> handled (empty list)")


def test_medical_claim_retrieves_relevant():
    """A clearly medical claim should retrieve topically relevant passages."""
    claim = "Mitochondria play a role in programmed cell death in plants."
    results = retrieve(claim, top_k=3)
    _print("medical_claim_retrieves_relevant", results)
    
    # At least one result should mention "PCD" or "mitochondri" or "cell death"
    keywords = ["PCD", "mitochondri", "cell death", "programmed"]
    matches = [r for r in results if any(k.lower() in r.lower() for k in keywords)]
    assert len(matches) >= 1, (
        f"Expected at least 1 result mentioning {keywords}; got 0"
    )


def test_results_are_passages_not_short_fragments():
    """Retrieved passages should be substantive (>20 words each)."""
    results = retrieve("Inflammation in clinical settings.", top_k=3)
    _print("results_are_passages", results)
    short = [r for r in results if len(r.split()) < 20]
    assert len(short) == 0, f"Some results are very short: {short}"


def test_repeated_query_is_consistent():
    """Same query at different times returns the same top-1 (deterministic)."""
    q = "Cardiovascular outcomes in elderly patients."
    r1 = retrieve(q, top_k=1)
    r2 = retrieve(q, top_k=1)
    assert r1 == r2, "Repeated retrieval should be deterministic"
    _print("repeated_query_consistent", r1)


# -------------------------------------------------------------------------
# Test runner
# -------------------------------------------------------------------------

def main():
    tests = [
        test_returns_list_of_strings,
        test_top_k_controls_count,
        test_empty_query_returns_empty_list,
        test_medical_claim_retrieves_relevant,
        test_results_are_passages_not_short_fragments,
        test_repeated_query_is_consistent,
    ]

    print("Running retriever unit tests")
    print("=" * 60)
    print()

    passed = 0
    failed = 0
    for test_fn in tests:
        print(f"[{test_fn.__name__}]")
        try:
            test_fn()
            passed += 1
            print("  PASS")
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        print()

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed (out of {len(tests)})")


if __name__ == "__main__":
    main()
