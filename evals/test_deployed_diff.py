"""Opt-in pytest wrapper for deployed endpoint drift checks."""

from __future__ import annotations

import os

import pytest

from evals.deployed_endpoint_diff import (
    DeploymentFreshness,
    DiffRow,
    classification_exit_code,
    classify_result,
    diff_endpoint,
    image_tag,
    parse_vertex_endpoint_resource,
    prediction_url,
    print_deployment_freshness,
    print_network_proof,
    print_rows,
)


def test_prediction_url_supports_container_and_vertex_api_routes():
    assert prediction_url("https://example.com") == "https://example.com/predict"
    assert prediction_url("https://example.com/predict") == "https://example.com/predict"
    assert (
        prediction_url("https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/endpoints/123:predict")
        == "https://us-central1-aiplatform.googleapis.com/v1/projects/p/locations/us-central1/endpoints/123:predict"
    )


def test_parse_vertex_endpoint_resource_from_predict_url():
    resource = parse_vertex_endpoint_resource(
        "https://us-central1-aiplatform.googleapis.com/v1/projects/claimsanamolyagent/locations/us-central1/endpoints/1022533169447960576:predict"
    )

    assert resource is not None
    assert resource.project == "claimsanamolyagent"
    assert resource.region == "us-central1"
    assert resource.endpoint_id == "1022533169447960576"


def test_image_tag_extracts_artifact_registry_tag():
    assert (
        image_tag("us-central1-docker.pkg.dev/claimsanamolyagent/ai-agents/claims-agent:b161dfa")
        == "b161dfa"
    )
    assert image_tag("us-central1-docker.pkg.dev/claimsanamolyagent/ai-agents/claims-agent") is None


def test_classify_result_distinguishes_current_stale_and_drift():
    matching_rows = [
        DiffRow(
            record_id="GC-01",
            local_route="AUTO_PAY",
            deployed_route="AUTO_PAY",
            local_gate="anomaly_auto_pay",
            deployed_gate="anomaly_auto_pay",
            match=True,
        )
    ]
    drift_rows = [
        DiffRow(
            record_id="GC-01",
            local_route="AUTO_PAY",
            deployed_route="DENY",
            local_gate="anomaly_auto_pay",
            deployed_gate="ncci_failed",
            match=False,
        )
    ]

    assert (
        classify_result(
            matching_rows,
            DeploymentFreshness(
                repo_head="b161dfa",
                deployed_image_uri="image:b161dfa",
                deployed_image_tag="b161dfa",
                is_current=True,
            ),
        )
        == "PASS_CURRENT"
    )
    assert (
        classify_result(
            matching_rows,
            DeploymentFreshness(
                repo_head="9c7665b",
                deployed_image_uri="image:b161dfa",
                deployed_image_tag="b161dfa",
                is_current=False,
            ),
        )
        == "PASS_STALE"
    )
    assert (
        classify_result(
            drift_rows,
            DeploymentFreshness(
                repo_head="b161dfa",
                deployed_image_uri="image:b161dfa",
                deployed_image_tag="b161dfa",
                is_current=True,
            ),
        )
        == "FAIL_DRIFT"
    )
    assert (
        classify_result(
            drift_rows,
            DeploymentFreshness(
                repo_head="9c7665b",
                deployed_image_uri="image:b161dfa",
                deployed_image_tag="b161dfa",
                is_current=False,
            ),
        )
        == "FAIL_STALE_AND_DRIFT"
    )
    assert (
        classify_result(
            matching_rows,
            DeploymentFreshness(
                repo_head="9c7665b",
                deployed_image_uri=None,
                deployed_image_tag=None,
                is_current=None,
                reason="gcloud metadata lookup failed",
            ),
        )
        == "FAIL_UNKNOWN_DEPLOYMENT"
    )
    assert (
        classify_result(
            drift_rows,
            DeploymentFreshness(
                repo_head="9c7665b",
                deployed_image_uri=None,
                deployed_image_tag=None,
                is_current=None,
                reason="gcloud metadata lookup failed",
            ),
        )
        == "FAIL_DRIFT_UNKNOWN_DEPLOYMENT"
    )


def test_classification_exit_code_warns_on_stale_and_fails_closed():
    assert classification_exit_code("PASS_CURRENT") == 0
    assert classification_exit_code("PASS_STALE") == 0
    assert classification_exit_code("FAIL_DRIFT") == 1
    assert classification_exit_code("FAIL_STALE_AND_DRIFT") == 1
    assert classification_exit_code("FAIL_UNKNOWN_DEPLOYMENT") == 1
    assert classification_exit_code("FAIL_DRIFT_UNKNOWN_DEPLOYMENT") == 1


def test_stale_deployment_with_route_mismatch_fails_as_stale_and_drift():
    rows = [
        DiffRow(
            record_id="GC-SYN-STale-DRIFT",
            local_route="PEND_MR",
            deployed_route="AUTO_PAY",
            local_gate="medical_necessity_failed",
            deployed_gate="anomaly_auto_pay",
            match=False,
        )
    ]
    freshness = DeploymentFreshness(
        repo_head="newhead1",
        deployed_image_uri="us-central1-docker.pkg.dev/project/repo/claims-agent:oldhead",
        deployed_image_tag="oldhead",
        is_current=False,
    )

    classification = classify_result(rows, freshness)

    assert classification == "FAIL_STALE_AND_DRIFT"
    assert classification_exit_code(classification) == 1


def test_print_deployment_freshness_labels_stale_deployment(capsys):
    print_deployment_freshness(
        DeploymentFreshness(
            repo_head="9c7665b",
            deployed_image_uri="us-central1-docker.pkg.dev/claimsanamolyagent/ai-agents/claims-agent:b161dfa",
            deployed_image_tag="b161dfa",
            is_current=False,
        ),
        "PASS_STALE",
    )

    output = capsys.readouterr().out
    assert "classification: PASS_STALE" in output
    assert "repo_head: 9c7665b" in output
    assert "deployed_image_tag: b161dfa" in output


def test_print_network_proof_omits_authorization_token(capsys):
    print_network_proof(
        [
            DiffRow(
                record_id="GC-01",
                local_route="AUTO_PAY",
                deployed_route="AUTO_PAY",
                local_gate="anomaly_auto_pay",
                deployed_gate="anomaly_auto_pay",
                match=True,
                http_status=200,
                elapsed_ms=321.4,
                request_url="https://example.com/endpoints/123:predict",
            )
        ]
    )

    output = capsys.readouterr().out
    assert "GC-01" in output
    assert "321.4" in output
    assert "Authorization" not in output
    assert "Bearer" not in output


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
