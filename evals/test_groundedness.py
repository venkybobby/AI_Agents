"""Opt-in pytest wrapper for Vertex groundedness judging."""

from __future__ import annotations

import os

import pytest

from evals.groundedness_judge import (
    FAIL_UNGROUNDED,
    FLAG_BOUNDARY_REVIEW,
    PASS_GROUNDED,
    GroundednessRow,
    classification_exit_code,
    classify_groundedness_run,
    evaluate_groundedness,
    groundedness_verdict,
    load_synthetic_cases,
    print_summary,
    synthetic_validation_passed,
)


def test_synthetic_fixtures_are_permanent_and_separate_from_routing_golden():
    cases = load_synthetic_cases()

    assert {case.case_id for case in cases} == {
        "SYN-OBVIOUS-GC01",
        "SYN-INFERENCE-GC05",
        "SYN-DEDUCTIBLE-GC06",
    }
    assert [case for case in cases if case.expectation == "MUST_FAIL_UNGROUNDED"]


def test_groundedness_verdict_flags_boundary_band():
    assert groundedness_verdict(0.39) == FAIL_UNGROUNDED
    assert groundedness_verdict(0.4) == FLAG_BOUNDARY_REVIEW
    assert groundedness_verdict(0.5) == FLAG_BOUNDARY_REVIEW
    assert groundedness_verdict(0.6) == FLAG_BOUNDARY_REVIEW
    assert groundedness_verdict(0.61) == PASS_GROUNDED


def test_synthetic_validation_requires_obvious_fabrication_to_fail():
    assert synthetic_validation_passed(
        [
            GroundednessRow(
                record_id="SYN-OBVIOUS-GC01",
                score=0.2,
                verdict=FAIL_UNGROUNDED,
                boundary_warning=False,
                reason="unsupported facts",
            )
        ]
    )
    assert not synthetic_validation_passed(
        [
            GroundednessRow(
                record_id="SYN-OBVIOUS-GC01",
                score=0.9,
                verdict=PASS_GROUNDED,
                boundary_warning=False,
                reason="missed fabrication",
            )
        ]
    )


def test_classify_groundedness_run_and_exit_policy():
    caught_synthetic = [
        GroundednessRow(
            record_id="SYN-OBVIOUS-GC01",
            score=0.2,
            verdict=FAIL_UNGROUNDED,
            boundary_warning=False,
            reason=None,
        )
    ]
    missed_synthetic = [
        GroundednessRow(
            record_id="SYN-OBVIOUS-GC01",
            score=0.9,
            verdict=PASS_GROUNDED,
            boundary_warning=False,
            reason=None,
        )
    ]
    clean_real = [
        GroundednessRow(
            record_id="GC-01",
            score=0.95,
            verdict=PASS_GROUNDED,
            boundary_warning=False,
            reason=None,
        )
    ]
    boundary_real = [
        GroundednessRow(
            record_id="GC-01",
            score=0.5,
            verdict=FLAG_BOUNDARY_REVIEW,
            boundary_warning=True,
            reason=None,
        )
    ]
    failed_real = [
        GroundednessRow(
            record_id="GC-01",
            score=0.2,
            verdict=FAIL_UNGROUNDED,
            boundary_warning=False,
            reason=None,
        )
    ]

    assert classify_groundedness_run(caught_synthetic, clean_real) == PASS_GROUNDED
    assert (
        classify_groundedness_run(caught_synthetic, boundary_real)
        == FLAG_BOUNDARY_REVIEW
    )
    assert classify_groundedness_run(caught_synthetic, failed_real) == FAIL_UNGROUNDED
    assert classify_groundedness_run(missed_synthetic, clean_real) == FAIL_UNGROUNDED
    assert classification_exit_code(PASS_GROUNDED) == 0
    assert classification_exit_code(FLAG_BOUNDARY_REVIEW) == 0
    assert classification_exit_code(FAIL_UNGROUNDED) == 1


@pytest.mark.skipif(
    os.getenv("SARO_EVAL_JUDGE", "").strip().lower() != "vertex",
    reason="SARO_EVAL_JUDGE=vertex not set; groundedness judge is opt-in",
)
def test_medical_necessity_reasoning_is_grounded():
    run = evaluate_groundedness()
    print_summary(run)
    assert run.classification != FAIL_UNGROUNDED
