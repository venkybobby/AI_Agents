"""Diff local golden claims behavior against a deployed Vertex endpoint."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ai_agents.demo_api import VertexPredictRequest, VertexPredictResponse
from evals.claims_eval_harness import build_domain, load_golden_records, run_record

REQUEST_TIMEOUT_SECONDS = 10.0


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
    for record in load_golden_records():
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


def main() -> int:
    endpoint_url = configured_endpoint_url()
    if endpoint_url is None:
        print("endpoint not configured, skipping drift check")
        return 0

    token = os.getenv("CLAIMS_AGENT_ENDPOINT_TOKEN", "").strip() or None
    rows = diff_endpoint(endpoint_url, token)
    print_rows(rows)
    if os.getenv("CLAIMS_AGENT_DIFF_VERBOSE", "").strip().lower() in {"1", "true", "yes"}:
        print_network_proof(rows)
    return 1 if any(not row.match for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
