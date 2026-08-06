"""Golden-label regression tests for the local claims eval harness."""

from __future__ import annotations

from evals.claims_eval_harness import build_domain, load_golden_records, run_record


def test_claims_golden_set_size_and_ids_are_demo_ready():
    records = load_golden_records()
    record_ids = [record.record_id for record in records]

    assert 50 <= len(records) <= 80
    assert len(record_ids) == len(set(record_ids))


def test_claims_golden_records_match_business_approved_labels():
    domain = build_domain()

    for record in load_golden_records():
        result = run_record(record, domain)
        assert result.route == record.expected_route, record.record_id
        assert result.matched_gate == record.expected_gate, record.record_id
