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
