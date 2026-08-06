"""Diff local golden claims behavior against a deployed Vertex endpoint."""

from __future__ import annotations

import os
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ai_agents.demo_api import VertexPredictRequest, VertexPredictResponse
from evals.claims_eval_harness import build_domain, selected_golden_records, run_record

REQUEST_TIMEOUT_SECONDS = 10.0

VERTEX_ENDPOINT_RE = re.compile(
    r"/projects/(?P<project>[^/]+)/locations/(?P<region>[^/]+)/endpoints/(?P<endpoint_id>[^/:]+)"
)


@dataclass(frozen=True)
class VertexEndpointResource:
    project: str
    region: str
    endpoint_id: str


@dataclass(frozen=True)
class DeploymentFreshness:
    repo_head: str | None
    deployed_image_uri: str | None
    deployed_image_tag: str | None
    is_current: bool | None
    reason: str | None = None


@dataclass(frozen=True)
class DiffRow:
    record_id: str
    local_route: str
    deployed_route: str | None
    local_gate: str | None
    deployed_gate: str | None
    match: bool
    http_status: int | None = None
    elapsed_ms: float | None = None
    request_url: str | None = None


@dataclass(frozen=True)
class DeployedPrediction:
    payload: dict[str, Any]
    http_status: int
    elapsed_ms: float
    request_url: str


def run_command(args: list[str]) -> str:
    """Run a metadata command and return stdout."""

    executable = args[0]
    if executable == "gcloud":
        executable = (
            shutil.which("gcloud")
            or shutil.which("gcloud.cmd")
            or shutil.which("gcloud.ps1")
            or executable
        )

    result = subprocess.run(
        [executable, *args[1:]],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def configured_endpoint_url() -> str | None:
    """Return endpoint URL or None when drift checking is not configured."""

    value = os.getenv("CLAIMS_AGENT_ENDPOINT_URL", "").strip()
    return value or None


def prediction_url(endpoint_url: str) -> str:
    """Build the deployed `/predict` URL without inventing a new schema."""

    trimmed = endpoint_url.rstrip("/")
    if trimmed.endswith("/predict") or trimmed.endswith(":predict"):
        return trimmed
    return f"{trimmed}/predict"


def parse_vertex_endpoint_resource(endpoint_url: str) -> VertexEndpointResource | None:
    """Extract project, region, and endpoint id from a Vertex predict URL."""

    match = VERTEX_ENDPOINT_RE.search(endpoint_url)
    if match is None:
        return None
    return VertexEndpointResource(
        project=match.group("project"),
        region=match.group("region"),
        endpoint_id=match.group("endpoint_id"),
    )


def repo_head_short() -> str | None:
    """Return current git HEAD short SHA, or None outside a git checkout."""

    override = os.getenv("CLAIMS_AGENT_REPO_HEAD", "").strip()
    if override:
        return override
    try:
        return run_command(["git", "rev-parse", "--short", "HEAD"])
    except (OSError, subprocess.CalledProcessError):
        return None


def image_tag(image_uri: str | None) -> str | None:
    """Extract the image tag from an Artifact Registry image URI."""

    if not image_uri:
        return None
    last_segment = image_uri.rsplit("/", 1)[-1]
    if ":" not in last_segment:
        return None
    return last_segment.rsplit(":", 1)[-1] or None


def deployed_image_uri(endpoint_url: str) -> tuple[str | None, str | None]:
    """Resolve the container image currently serving a Vertex endpoint."""

    override = os.getenv("CLAIMS_AGENT_DEPLOYED_IMAGE_URI", "").strip()
    if override:
        return override, None

    resource = parse_vertex_endpoint_resource(endpoint_url)
    if resource is None:
        return None, "endpoint URL is not a Vertex AI predict URL"

    try:
        endpoint_raw = run_command(
            [
                "gcloud",
                "ai",
                "endpoints",
                "describe",
                resource.endpoint_id,
                "--project",
                resource.project,
                "--region",
                resource.region,
                "--format=json",
            ]
        )
        endpoint = json.loads(endpoint_raw)
        deployed_models = endpoint.get("deployedModels") or []
        if not deployed_models:
            return None, "endpoint has no deployed models"

        traffic_split = endpoint.get("trafficSplit") or {}
        active_deployed_model_id = None
        if traffic_split:
            active_deployed_model_id = max(
                traffic_split.items(),
                key=lambda item: int(item[1]),
            )[0]

        deployed_model = None
        if active_deployed_model_id is not None:
            deployed_model = next(
                (
                    candidate
                    for candidate in deployed_models
                    if str(candidate.get("id")) == str(active_deployed_model_id)
                ),
                None,
            )
        deployed_model = deployed_model or deployed_models[0]
        model_name = deployed_model.get("model")
        if not model_name:
            return None, "deployed model record does not include model name"

        model_id = str(model_name).rsplit("/", 1)[-1]
        model_raw = run_command(
            [
                "gcloud",
                "ai",
                "models",
                "describe",
                model_id,
                "--project",
                resource.project,
                "--region",
                resource.region,
                "--format=json",
            ]
        )
        model = json.loads(model_raw)
        image_uri = (model.get("containerSpec") or {}).get("imageUri")
        if not image_uri:
            return None, "model does not include containerSpec.imageUri"
        return str(image_uri), None
    except FileNotFoundError:
        return None, "gcloud is not installed or not on PATH"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        return None, stderr or f"gcloud metadata lookup failed with exit code {exc.returncode}"
    except json.JSONDecodeError:
        return None, "gcloud returned invalid JSON"


def deployment_freshness(endpoint_url: str) -> DeploymentFreshness:
    """Compare deployed Vertex image tag with the current repo HEAD."""

    head = repo_head_short()
    image_uri, reason = deployed_image_uri(endpoint_url)
    tag = image_tag(image_uri)
    if head is None:
        return DeploymentFreshness(head, image_uri, tag, None, "repo HEAD could not be resolved")
    if image_uri is None:
        return DeploymentFreshness(head, image_uri, tag, None, reason)
    if tag is None:
        return DeploymentFreshness(head, image_uri, tag, None, "deployed image URI has no tag")
    return DeploymentFreshness(head, image_uri, tag, tag == head, None)


def classify_result(rows: list[DiffRow], freshness: DeploymentFreshness) -> str:
    """Classify the run so green route matches are not ambiguous."""

    has_drift = any(not row.match for row in rows)
    if freshness.is_current is None:
        return "FAIL_DRIFT_UNKNOWN_DEPLOYMENT" if has_drift else "FAIL_UNKNOWN_DEPLOYMENT"
    if freshness.is_current:
        return "FAIL_DRIFT" if has_drift else "PASS_CURRENT"
    return "FAIL_STALE_AND_DRIFT" if has_drift else "PASS_STALE"


def classification_exit_code(classification: str) -> int:
    """Return the CI exit code for a deployment diff classification."""

    return 1 if classification.startswith("FAIL_") else 0


def deployed_prediction(
    endpoint_url: str,
    claim_data: dict[str, Any],
    token: str | None,
) -> DeployedPrediction:
    """Call the deployed endpoint using demo_api.VertexPredictRequest shape."""

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = prediction_url(endpoint_url)
    started = time.perf_counter()
    response = httpx.post(
        url,
        json=VertexPredictRequest(instances=[{"claim_data": claim_data}]).model_dump(),
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    payload = VertexPredictResponse.model_validate(response.json())
    predictions = payload.predictions
    if not predictions:
        raise ValueError("deployed endpoint returned no predictions")
    return DeployedPrediction(
        payload=predictions[0].model_dump(),
        http_status=response.status_code,
        elapsed_ms=elapsed_ms,
        request_url=url,
    )


def diff_endpoint(endpoint_url: str, token: str | None = None) -> list[DiffRow]:
    """Run golden records locally and against the deployed endpoint."""

    domain = build_domain()
    rows: list[DiffRow] = []
    records = selected_golden_records()
    print(f"eval_scope_records={len(records)}")
    for record in records:
        local = run_record(record, domain)
        deployed = deployed_prediction(endpoint_url, record.claim_data, token)
        deployed_route = deployed.payload.get("route")
        deployed_gate = deployed.payload.get("matched_gate")
        rows.append(
            DiffRow(
                record_id=record.record_id,
                local_route=local.route,
                deployed_route=str(deployed_route) if deployed_route is not None else None,
                local_gate=local.matched_gate,
                deployed_gate=str(deployed_gate) if deployed_gate is not None else None,
                match=local.route == deployed_route
                and local.matched_gate == deployed_gate,
                http_status=deployed.http_status,
                elapsed_ms=deployed.elapsed_ms,
                request_url=deployed.request_url,
            )
        )
    return rows


def print_rows(rows: list[DiffRow]) -> None:
    print("record_id | local_route | deployed_route | match")
    print("----------|-------------|----------------|------")
    for row in rows:
        print(
            f"{row.record_id} | {row.local_route}/{row.local_gate} | "
            f"{row.deployed_route}/{row.deployed_gate} | {row.match}"
        )


def print_network_proof(rows: list[DiffRow]) -> None:
    """Print non-secret HTTP evidence proving the diff used the deployed endpoint."""

    print("\nnetwork proof")
    print("record_id | http_status | elapsed_ms | request_url")
    print("----------|-------------|------------|------------")
    for row in rows:
        print(
            f"{row.record_id} | {row.http_status} | "
            f"{row.elapsed_ms:.1f} | {row.request_url}"
        )


def print_deployment_freshness(freshness: DeploymentFreshness, classification: str) -> None:
    """Print non-secret deployment freshness evidence."""

    print("\ndeployment freshness")
    print(f"classification: {classification}")
    print(f"repo_head: {freshness.repo_head}")
    print(f"deployed_image_tag: {freshness.deployed_image_tag}")
    print(f"deployed_image_uri: {freshness.deployed_image_uri}")
    if freshness.reason:
        print(f"freshness_reason: {freshness.reason}")


def main() -> int:
    endpoint_url = configured_endpoint_url()
    if endpoint_url is None:
        print("endpoint not configured, skipping drift check")
        return 0

    token = os.getenv("CLAIMS_AGENT_ENDPOINT_TOKEN", "").strip() or None
    freshness = deployment_freshness(endpoint_url)
    rows = diff_endpoint(endpoint_url, token)
    print_rows(rows)
    classification = classify_result(rows, freshness)
    print_deployment_freshness(freshness, classification)
    if os.getenv("CLAIMS_AGENT_DIFF_VERBOSE", "").strip().lower() in {"1", "true", "yes"}:
        print_network_proof(rows)
    return classification_exit_code(classification)


if __name__ == "__main__":
    raise SystemExit(main())
