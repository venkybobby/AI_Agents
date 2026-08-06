"""Local deterministic evaluation harness for claims anomaly records."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ai_agents.domains.claims_anomaly import (
    ClaimsAnomalyDomain,
    ClaimsReferenceRepository,
    initialize_reference_db,
    load_claims_rule_pack,
)
from ai_agents.domains.claims_models import ClaimsReviewResult

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = ROOT / "domains" / "claims_anomaly"
RULES = DOMAIN / "rules" / "claims_anomaly.yaml"
SCHEMA = DOMAIN / "reference_data" / "schema.sql"
SEED = DOMAIN / "reference_data" / "seed.sql"
GOLDEN = Path(__file__).resolve().parent / "golden" / "claims_golden.jsonl"
SMOKE_RECORD_IDS = {
    "GC-01",  # clean E/M auto-pay
    "GC-02",  # OIG NPI hard stop
    "GC-03",  # CCMI-1 no modifier denial
    "GC-04",  # CCMI-1 modifier review
    "GC-05",  # medical necessity failure
    "GC-07",  # CCMI-0 hard denial with modifier
    "GC-12",  # OIG EIN hard stop
    "GC-13",  # OIG SSN hard stop
    "GC-17",  # 99202 MDM-supported pass
    "GC-18",  # 99202 below-threshold fail
    "GC-49",  # reversed CPT order still finds CCMI-1
    "GC-53",  # NCCI modifier review precedes medical necessity failure
}


@dataclass(frozen=True)
class ClaimsGoldenRecord:
    """One claims evaluation record and business-approved expected outcome."""

    record_id: str
    claim_data: dict[str, Any]
    expected_route: str
    expected_gate: str | None
    rationale: str


def load_golden_records(path: str | Path = GOLDEN) -> list[ClaimsGoldenRecord]:
    """Load JSONL golden records."""

    records: list[ClaimsGoldenRecord] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            records.append(
                ClaimsGoldenRecord(
                    record_id=str(raw["record_id"]),
                    claim_data=dict(raw["claim_data"]),
                    expected_route=str(raw["expected_route"]),
                    expected_gate=raw.get("expected_gate"),
                    rationale=str(raw.get("rationale", "")),
                )
            )
    return records


def selected_golden_records(
    records: Iterable[ClaimsGoldenRecord] | None = None,
    scope: str | None = None,
) -> list[ClaimsGoldenRecord]:
    """Return smoke or full golden records for expensive live evals.

    Local deterministic tests should use the full golden set. Live Vertex checks
    default to smoke so CI does not grow linearly with every new golden record.
    Set CLAIMS_AGENT_EVAL_SCOPE=full for release/nightly validation.
    """

    import os

    normalized_scope = (scope or os.getenv("CLAIMS_AGENT_EVAL_SCOPE", "smoke")).lower()
    source_records = list(records if records is not None else load_golden_records())
    if normalized_scope == "full":
        return source_records
    if normalized_scope != "smoke":
        raise ValueError("CLAIMS_AGENT_EVAL_SCOPE must be 'smoke' or 'full'")
    return [record for record in source_records if record.record_id in SMOKE_RECORD_IDS]


def golden_record_signature(record: ClaimsGoldenRecord) -> tuple[Any, ...]:
    """Return a coarse coverage signature for duplicate-scenario review."""

    cpt_codes = {str(code) for code in record.claim_data.get("cpt_codes", [])}
    modifiers = {str(modifier).upper() for modifier in record.claim_data.get("modifiers", [])}
    provider_id_type = str(record.claim_data.get("provider_id_type", "NPI"))
    em_code = next((code for code in sorted(cpt_codes) if code.startswith("99")), "no_em")
    if {"97110", "97530"}.issubset(cpt_codes):
        ncci_family = "ccmi1"
    elif {"11111", "22222"}.issubset(cpt_codes):
        ncci_family = "ccmi0"
    else:
        ncci_family = "no_seeded_ncci"

    valid_modifier_families = {
        "59",
        "XE",
        "XP",
        "XS",
        "XU",
        "25",
        "27",
        "58",
        "78",
        "79",
        "LT",
        "RT",
        "E1",
        "FA",
        "T9",
        "LC",
    }
    if not modifiers:
        modifier_family = "no_modifier"
    elif modifiers & valid_modifier_families:
        modifier_family = "valid_seeded_modifier"
    else:
        modifier_family = "invalid_modifier_only"

    clinical_notes = str(record.claim_data.get("clinical_notes", "")).lower()
    minutes_bucket = "mentions_minutes" if "minute" in clinical_notes else "no_minutes"
    return (
        record.expected_route,
        record.expected_gate,
        provider_id_type,
        em_code,
        ncci_family,
        modifier_family,
        minutes_bucket,
    )


def build_domain(db_path: str | Path | None = None) -> ClaimsAnomalyDomain:
    """Build a local domain using seeded reference data."""

    if db_path is None:
        db_path = Path(tempfile.mkdtemp(prefix="claims-eval-")) / "reference.db"
    initialize_reference_db(db_path, SCHEMA, SEED)
    return ClaimsAnomalyDomain(
        load_claims_rule_pack(RULES),
        ClaimsReferenceRepository(db_path),
    )


def run_record(
    record: ClaimsGoldenRecord,
    domain: ClaimsAnomalyDomain,
) -> ClaimsReviewResult:
    """Run one golden record through the local engine."""

    return domain.review_claim(record.claim_data)


def em_requirement_context(
    record: ClaimsGoldenRecord,
    domain: ClaimsAnomalyDomain,
) -> dict[str, Any] | None:
    """Return the first E/M requirement row exercised by a record."""

    for code in record.claim_data.get("cpt_codes", []):
        if str(code).startswith("99"):
            return domain.repository.em_requirement(str(code))
    return None


def medical_necessity_records(
    records: Iterable[ClaimsGoldenRecord],
) -> list[ClaimsGoldenRecord]:
    """Select records that exercise medical necessity or fail that gate."""

    selected: list[ClaimsGoldenRecord] = []
    for record in records:
        cpt_codes = [str(code) for code in record.claim_data.get("cpt_codes", [])]
        if record.expected_gate == "medical_necessity_failed" or any(
            code.startswith("99") for code in cpt_codes
        ):
            selected.append(record)
    return selected
