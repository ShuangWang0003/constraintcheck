
# Design Decisions Log

This file records non-obvious design decisions made during the build,
along with the reasoning. Useful for résumé writing, interviews, and
future debugging.

---

## Day 1 — 2026-05-02

### D1.1 — Use mock modules before real implementations

**Decision**: Build the full pipeline (claim_extractor, retriever, verifier, agent)
with placeholder mock implementations on Day 1, then replace one module per day.

**Why**:
- Lets the end-to-end JSON schema and aggregation rules be locked in early
- Each subsequent day is a low-risk drop-in replacement, not new wiring
- Tests can be written against the schema independently of any model

**Trade-off**: Day 1 output is meaningless (random verdicts), but the architecture is exercised.

---

### D1.2 — Module-level imports in agent.py (not function-level)

**Decision**: `agent.py` imports modules (`from src import verifier`),
not functions (`from src.verifier import verify`).

**Why**: Function-level imports copy the function object into agent.py's namespace
at import time. Tests that monkey-patch `src.verifier.verify` then have no
effect because agent.py still holds a reference to the original.

**Discovered**: One unit test failed in the first run; this fixed it without
changing any business logic.

**Future benefit**: When we replace mock verifier with Mistral on Day 5,
no change to agent.py is needed — verifier.py changes internally only.

---

### D1.3 — Aggregation rule

**Decision**:
