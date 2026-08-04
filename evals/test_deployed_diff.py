"""Opt-in pytest wrapper for deployed endpoint drift checks."""

from __future__ import annotations

import os

import pytest

from evals.deployed_endpoint_diff import diff_endpoint, prediction_url, print_rows


def test_prediction_url_supports_container_and_vertex_api_routes():
    assert prediction_url("https://example.com") == "https://example.com/predict"
    assert prediction_url("https://example.com/predict") == "https://example.com/predict"
    assert (
        prediction_url("https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/endpoints/123:predict")
        == "https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/endpoints/123:predict"
    )


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
