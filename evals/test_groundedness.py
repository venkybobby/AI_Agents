"""Opt-in pytest wrapper for Vertex groundedness judging."""

from __future__ import annotations

import os

import pytest

from evals.groundedness_judge import evaluate_groundedness, print_summary


@pytest.mark.skipif(
    os.getenv("SARO_EVAL_JUDGE", "").strip().lower() != "vertex",
    reason="SARO_EVAL_JUDGE=vertex not set; groundedness judge is opt-in",
)
def test_medical_necessity_reasoning_is_grounded():
    rows = evaluate_groundedness()
    print_summary(rows)
    assert not [row for row in rows if row.verdict == "FAIL"]
