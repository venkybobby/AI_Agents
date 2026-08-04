"""Opt-in pytest wrapper for deployed endpoint drift checks."""

from __future__ import annotations

import os

import pytest

from evals.deployed_endpoint_diff import diff_endpoint, print_rows


@pytest.mark.skipif(
    not os.getenv("CLAIMS_AGENT_ENDPOINT_URL"),
    reason="CLAIMS_AGENT_ENDPOINT_URL unset; deployed drift check is opt-in",
)
def test_deployed_endpoint_matches_local_golden_behavior():
    rows = diff_endpoint(
        os.environ["CLAIMS_AGENT_ENDPOINT_URL"],
        os.getenv("CLAIMS_AGENT_ENDPOINT_TOKEN", "").strip() or None,
    )
    print_rows(rows)
    assert not [row for row in rows if not row.match]
