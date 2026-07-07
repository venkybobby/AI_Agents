"""FastAPI demo API for 837 claims review."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .domains.claims_837 import EDI837ParseError, review_837_file
from .domains.claims_anomaly import ClaimsDomainError


APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = ROOT / "domains" / "claims_anomaly" / "rules" / "claims_anomaly.yaml"
DEFAULT_SCHEMA = ROOT / "domains" / "claims_anomaly" / "reference_data" / "schema.sql"
DEFAULT_SEED = ROOT / "domains" / "claims_anomaly" / "reference_data" / "seed.sql"
DEFAULT_DB = ROOT / ".demo" / "claims_reference.db"
DEFAULT_SCENARIOS = ROOT / "domains" / "claims_anomaly" / "examples"


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class Review837Request(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    edi_text: str = Field(..., min_length=1, max_length=1_000_000)


class ScenarioSummary(BaseModel):
    id: str
    label: str
    file: str


class Review837Response(BaseModel):
    claim_id: str
    route: str
    matched_gate: str | None
    anomaly_score: float
    execution_plan: list[str]
    timeline: list[dict[str, Any]]
    parsed_claim: dict[str, Any]
    tool_outputs: dict[str, Any]
    rule_pack_id: str
    rule_pack_version: str


app = FastAPI(title="AI_Agents Claims Demo", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-AI-Agents-Version"] = APP_VERSION
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/v1/demo/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios() -> list[ScenarioSummary]:
    return [
        ScenarioSummary(id=path.stem, label=_label(path.stem), file=path.name)
        for path in sorted(DEFAULT_SCENARIOS.glob("*.edi"))
    ]


@app.post("/api/v1/claims/review-837", response_model=Review837Response)
async def review_837(payload: Review837Request, request: Request) -> Review837Response:
    try:
        result = await asyncio.to_thread(_review_edi_text, payload.edi_text)
    except (ClaimsDomainError, EDI837ParseError, OSError, ValueError) as exc:
        raise _http_error("CLAIMS_REVIEW_FAILED", str(exc), request) from exc
    return _response_from_payload(result)


@app.post("/api/v1/demo/scenarios/{scenario_id}/run", response_model=Review837Response)
async def run_scenario(scenario_id: str, request: Request) -> Review837Response:
    scenario_path = DEFAULT_SCENARIOS / f"{scenario_id}.edi"
    if not scenario_path.exists():
        raise _http_error("SCENARIO_NOT_FOUND", f"unknown scenario: {scenario_id}", request, status_code=404)
    try:
        result = await asyncio.to_thread(_review_edi_file, scenario_path)
    except (ClaimsDomainError, EDI837ParseError, OSError, ValueError) as exc:
        raise _http_error("SCENARIO_REVIEW_FAILED", str(exc), request) from exc
    return _response_from_payload(result)


def _review_edi_text(edi_text: str) -> dict[str, Any]:
    temp_dir = ROOT / ".demo"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / "_api_payload.edi"
    temp_file.write_text(edi_text, encoding="utf-8")
    return _review_edi_file(temp_file)


def _review_edi_file(edi_file: Path) -> dict[str, Any]:
    db_path = Path(os.getenv("AI_AGENTS_REFERENCE_DB", str(DEFAULT_DB)))
    return review_837_file(
        edi_file,
        rules_path=DEFAULT_RULES,
        db_path=db_path,
        schema_path=DEFAULT_SCHEMA,
        seed_path=DEFAULT_SEED,
    )


def _response_from_payload(payload: dict[str, Any]) -> Review837Response:
    review = payload["review"]
    parsed_claim = payload["parsed_claim"]
    return Review837Response(
        claim_id=str(parsed_claim.get("claim_id", "")),
        route=review["route"],
        matched_gate=review["matched_gate"],
        anomaly_score=float(review["anomaly_score"]),
        execution_plan=list(review["execution_plan"]),
        timeline=_timeline(review),
        parsed_claim=parsed_claim,
        tool_outputs=review["tool_outputs"],
        rule_pack_id=review["rule_pack_id"],
        rule_pack_version=review["rule_pack_version"],
    )


def _timeline(review: dict[str, Any]) -> list[dict[str, Any]]:
    outputs = review["tool_outputs"]
    events: list[dict[str, Any]] = []
    if "oig_exclusion" in outputs:
        excluded = outputs["oig_exclusion"]["is_excluded"]
        events.append({"step": "OIG LEIE", "status": "failed" if excluded else "passed", "detail": outputs["oig_exclusion"]})
    if "ncci_check" in outputs:
        passed = outputs["ncci_check"]["passed"]
        events.append({"step": "NCCI PTP", "status": "passed" if passed else "failed", "detail": outputs["ncci_check"]})
    if "medical_necessity_check" in outputs:
        supported = outputs["medical_necessity_check"]["is_supported"]
        events.append({"step": "Medical Necessity", "status": "passed" if supported else "failed", "detail": outputs["medical_necessity_check"]})
    events.append({"step": "Synthesis / Routing", "status": review["route"], "detail": {"matched_gate": review["matched_gate"], "anomaly_score": review["anomaly_score"]}})
    return events


def _http_error(code: str, message: str, request: Request, status_code: int = 422) -> HTTPException:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    return HTTPException(status_code=status_code, detail=ErrorDetail(code=code, message=message, request_id=request_id).model_dump())


def _label(scenario_id: str) -> str:
    return scenario_id.replace("_", " ").title()
