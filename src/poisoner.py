"""
Poisoner: inject 4 types of failure modes into trustworthy answers
to construct an evaluation set with controlled hallucinations.

Each function takes an answer and returns a tuple:
    (modified_answer, success, metadata)
"""

import re
import random


# =========================================================================
# Mode 1: Unsupported claim
# =========================================================================
UNSUPPORTED_TEMPLATES = [
    " This was first reported in 2019 by researchers at MIT.",
    " A 2021 meta-analysis confirmed these findings across multiple cohorts.",
    " Several follow-up studies have replicated this effect.",
    " This mechanism is now considered the standard explanation in the field.",
    " Recent independent reviews have validated this conclusion.",
]


def inject_unsupported_claim(answer: str, rng: random.Random) -> tuple:
    """Append an unsupported generalizing claim."""
    addition = rng.choice(UNSUPPORTED_TEMPLATES)
    poisoned = answer.rstrip(".") + "." + addition
    return poisoned, True, {}


# =========================================================================
# Mode 2: Unsupported numerical claim (with two sub-strategies)
# =========================================================================

SKIP_CONTEXT_AFTER = re.compile(
    r'^\s*(year|years|yr|yrs|age|aged|month|months|day|days|hour|hours|'
    r'patient|patients|subject|subjects|case|cases|condition|conditions|'
    r'group|groups|study|studies)\b',
    re.IGNORECASE,
)
SKIP_CONTEXT_BEFORE = re.compile(
    r'\b(figure|fig|table|tab|n\s*=|chapter|section|step)\s*$',
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(r'\d+(?:\.\d+)?')


def _find_modifiable_number(answer: str):
    """
    Find the first number in `answer` that is safe to modify.
    Skips:
      - Years (1900–2030)
      - Small integers (< 5) — likely list/group counters
      - Numbers followed by year/age/patient/etc context
      - Numbers preceded by Figure/Table/n= context
      - Numbers attached to letters or hyphens (e.g. "IL-7", "TGF-1",
        "p53", "COVID-19", "type-2") — these are compound identifiers,
        not statistical quantities. Modifying them produces invalid
        biological/medical entities, not retrieval-grounded errors.
    """
    for match in NUMBER_PATTERN.finditer(answer):
        try:
            value = float(match.group())
        except ValueError:
            continue

        # Skip: years
        if 1900 <= value <= 2030 and "." not in match.group():
            continue

        # Skip: very small integers (likely list/group counters)
        if value < 5 and "." not in match.group():
            continue

        # Skip: trailing context (e.g. "70 years", "patients")
        trailing = answer[match.end(): match.end() + 30]
        if SKIP_CONTEXT_AFTER.match(trailing):
            continue

        # Skip: leading context (e.g. "Figure 3")
        leading = answer[max(0, match.start() - 30): match.start()]
        if SKIP_CONTEXT_BEFORE.search(leading):
            continue

        # Skip: numbers attached to letters or hyphens (compound identifiers)
        # e.g. "Interleukin-7", "TGF-1", "p53", "COVID-19", "type-2"
        if match.start() > 0:
            prev_char = answer[match.start() - 1]
            if prev_char.isalpha() or prev_char == "-":
                continue

        return match

    return None


def _modify_existing_number(answer: str, rng: random.Random):
    """Try to modify a safely-modifiable number in the answer."""
    match = _find_modifiable_number(answer)
    if match is None:
        return None

    original_str = match.group()
    original_val = float(original_str)
    is_int = "." not in original_str

    factor = rng.choice([1.5, 1.7, 2.0, 2.3, 2.6])
    new_val = original_val * factor

    if is_int:
        new_str = str(int(round(new_val)))
    else:
        new_str = f"{new_val:.1f}"

    return answer[: match.start()] + new_str + answer[match.end():]


FABRICATED_NUMERIC_TEMPLATES = [
    " This effect corresponded to a {n}% reduction in risk.",
    " The intervention improved outcomes by {n}% compared with controls.",
    " This finding was associated with a {n}% higher response rate.",
    " Patients in the treatment group showed a {n}% lower complication rate.",
    " The observed association increased the likelihood of the outcome by {n}%.",
]
FABRICATED_NUMBERS = [18, 23, 31, 37, 42, 48, 56, 63]


def _fabricate_numerical_claim(answer: str, rng: random.Random) -> str:
    """Append a fabricated percentage statement."""
    template = rng.choice(FABRICATED_NUMERIC_TEMPLATES)
    n = rng.choice(FABRICATED_NUMBERS)
    addition = template.format(n=n)
    return answer.rstrip(".") + "." + addition


def inject_unsupported_numerical_claim(
    answer: str,
    rng: random.Random,
    prefer_modify: bool,
) -> tuple:
    """
    Inject an unsupported numerical claim. Two strategies:
      - modified_existing_number: rewrite a safely-modifiable number
      - fabricated_percentage:    append a fabricated statistic
    """
    if prefer_modify:
        modified = _modify_existing_number(answer, rng)
        if modified is not None:
            return modified, True, {"numerical_subtype": "modified_existing_number"}

    fabricated = _fabricate_numerical_claim(answer, rng)
    return fabricated, True, {"numerical_subtype": "fabricated_percentage"}


# =========================================================================
# Mode 3: Hallucinated citation
# =========================================================================
CITATION_TEMPLATES = [
    " (Smith et al., 2020, Journal of Medical Research)",
    " (Chen and Park, 2019, Annals of Clinical Medicine)",
    " (Williams et al., 2021, New England Journal of Health Sciences)",
    " (Patel et al., 2018, Lancet Medical Reviews)",
    " (Rodriguez and Kim, 2022, Nature Medicine Letters)",
]


def inject_hallucinated_citation(answer: str, rng: random.Random) -> tuple:
    """Append a fabricated citation."""
    addition = rng.choice(CITATION_TEMPLATES)
    poisoned = answer.rstrip(".") + "." + addition
    return poisoned, True, {}


# =========================================================================
# Mode 4: Contradiction
# =========================================================================
CONTRADICTION_TEMPLATES = [
    " However, the same evidence also indicates this intervention has no measurable effect.",
    " However, these findings contradict the conclusion and suggest no association.",
    " That said, follow-up analyses found the opposite pattern in independent cohorts.",
    " On the contrary, the data also support the view that this effect does not generalize.",
    " Yet, parallel evidence suggests the relationship may actually be reversed.",
]


def inject_contradiction(answer: str, rng: random.Random) -> tuple:
    """Append a contradicting sentence."""
    addition = rng.choice(CONTRADICTION_TEMPLATES)
    poisoned = answer.rstrip(".") + "." + addition
    return poisoned, True, {}


# =========================================================================
# Sanity check
# =========================================================================
if __name__ == "__main__":
    rng = random.Random(42)

    test_cases = [
        ("no_number",
         "Our findings suggest that mitochondria play a critical role "
         "in developmentally regulated programmed cell death."),
        ("age_70_years",
         "Emergency laparotomy carries a high rate of mortality, "
         "especially in those over the age of 70 years."),
        ("stat_2-fold",
         "Our long-term study showed significantly better 2-fold results "
         "regarding the continence score for the abdominal approach."),
        ("safe_15_percent",
         "The clinical trial showed that 15 percent of patients responded to treatment."),
        ("compound_IL-7",
         "Interleukin-7 concentration in pancreatic juice can discriminate "
         "between normal and diseased pancreas."),
        ("compound_TGF-1",
         "TGF-1 expression was elevated in the lesion tissue compared to controls."),
        ("compound_type-2",
         "Patients with type-2 diabetes showed elevated markers of inflammation."),
        ("compound_p53",
         "Mutations in p53 were observed in 30 percent of the tumor samples."),
    ]

    print("=" * 75)
    print("Sanity check: _find_modifiable_number on edge cases")
    print("=" * 75)

    for label, sample in test_cases:
        match = _find_modifiable_number(sample)
        result = "MODIFY → " + match.group() if match else "SKIP (no safe number)"
        print(f"\n  [{label}]")
        print(f"  TEXT:   {sample}")
        print(f"  RESULT: {result}")
