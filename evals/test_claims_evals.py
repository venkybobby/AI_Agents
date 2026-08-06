"""Golden-label regression tests for the local claims eval harness."""

from __future__ import annotations

from evals.claims_eval_harness import (
    build_domain,
    golden_record_signature,
    load_golden_records,
    selected_golden_records,
    run_record,
)


def test_claims_golden_set_size_and_ids_are_demo_ready():
    records = load_golden_records()
    record_ids = [record.record_id for record in records]

    assert 50 <= len(records) <= 80
    assert len(record_ids) == len(set(record_ids))


def test_live_eval_smoke_scope_is_representative_and_bounded():
    records = load_golden_records()
    smoke_records = selected_golden_records(records, scope="smoke")

    assert len(smoke_records) == 12
    assert {record.expected_route for record in smoke_records} == {
        "AUTO_PAY",
        "DENY",
        "DENY_AND_REPORT",
        "PEND_MDR",
        "PEND_MR",
    }
    assert {record.expected_gate for record in smoke_records} == {
        "anomaly_auto_pay",
        "oig_exclusion",
        "ncci_failed",
        "ncci_modifier_review",
        "medical_necessity_failed",
    }
    assert selected_golden_records(records, scope="full") == records


def test_claims_golden_set_has_meaningful_scenario_family_diversity():
    records = load_golden_records()
    signatures = {golden_record_signature(record) for record in records}

    assert len(signatures) >= 30


def test_claims_golden_records_match_business_approved_labels():
    domain = build_domain()

    for record in load_golden_records():
        result = run_record(record, domain)
        assert result.route == record.expected_route, record.record_id
        assert result.matched_gate == record.expected_gate, record.record_id
