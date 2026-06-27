"""Eval fixtures for coach agent quality checks."""

FIXTURE_SPIN_QUESTION = "Why did I spin at Turn 7?"
FIXTURE_TECHNIQUE_QUESTION = "What should I do at this corner?"

# Minimum assertions for eval harness
EVAL_ASSERTIONS = [
    "citations_non_empty_or_deterministic",
    "includes_drill_or_how",
    "no_hallucinated_corner_when_scoped",
]
