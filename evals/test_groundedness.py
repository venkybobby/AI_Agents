"""Opt-in pytest wrapper for Vertex groundedness judging."""

from __future__ import annotations

import os

import pytest

from evals.groundedness_judge import (
    FAIL_UNGROUNDED,
    FLAG_BOUNDARY_REVIEW,
    PASS_GROUNDED,
    GroundednessRow,
    build_context,
    classification_exit_code,
    classify_groundedness_run,
    evaluate_groundedness,
    groundedness_verdict,
    load_synthetic_cases,
    print_summary,
    synthetic_validation_passed,
)
from evals.claims_eval_harness import (
    build_domain,
    em_requirement_context,
    load_golden_records,
    medical_necessity_records,
    run_record,
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


def test_real_golden_reasoning_only_mentions_values_present_in_judge_context():
    domain = build_domain()

    for record in medical_necessity_records(load_golden_records()):
        result = run_record(record, domain)
        medical_output = result.tool_outputs.get("medical_necessity_check")
        assert isinstance(medical_output, dict)
        reasoning = str(medical_output.get("reasoning", ""))
        context = build_context(record.claim_data, em_requirement_context(record, domain))

        claim_values = {
            str(value)
            for field in ("claim_id", "provider_npi", "provider_id", "provider_id_type")
            if (value := record.claim_data.get(field)) is not None
        }
        for field in ("cpt_codes", "modifiers", "diagnosis_codes"):
            for value in record.claim_data.get(field, []):
                claim_values.add(str(value))

        leaked_values = sorted(
            value
            for value in claim_values
            if len(value) >= 2 and value in reasoning and value not in context
        )
        assert leaked_values == [], (
            f"{record.record_id} reasoning references values outside judge context: "
            f"{leaked_values}; reasoning={reasoning!r}; context={context!r}"
        )


@pytest.mark.skipif(
    os.getenv("SARO_EVAL_JUDGE", "").strip().lower() != "vertex",
    reason="SARO_EVAL_JUDGE=vertex not set; groundedness judge is opt-in",
)
def test_medical_necessity_reasoning_is_grounded():
    run = evaluate_groundedness()
    print_summary(run)
    assert run.classification != FAIL_UNGROUNDED
