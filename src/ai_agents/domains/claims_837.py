"""Minimal 837P ingest for claims anomaly demo flows.

This parser intentionally supports a narrow, testable subset of X12 837P needed
for local demos. It is not a full X12 validator or production EDI translator.
Production deployments should swap this adapter for a certified EDI pipeline and
keep the normalized claim contract unchanged.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .claims_anomaly import (
    ClaimsAnomalyDomain,
    ClaimsReferenceRepository,
    initialize_reference_db,
    load_claims_rule_pack,
)


class EDI837ParseError(RuntimeError):
    """Raised when a supported 837 demo transaction cannot be parsed."""


@dataclass(frozen=True)
class Parsed837Claim:
    """Normalized claim extracted from a supported 837 transaction."""

    claim_id: str
    provider_npi: str
    cpt_codes: tuple[str, ...]
    modifiers: tuple[str, ...]
    diagnosis_codes: tuple[str, ...]
    clinical_notes: str

    def to_claim_data(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "provider_id": self.provider_npi,
            "provider_id_type": "NPI",
            "provider_npi": self.provider_npi,
            "cpt_codes": list(self.cpt_codes),
            "modifiers": list(self.modifiers),
            "diagnosis_codes": list(self.diagnosis_codes),
            "clinical_notes": self.clinical_notes,
        }


def parse_837_claim(edi_text: str) -> Parsed837Claim:
    """Parse a minimal 837P demo transaction into normalized claim data."""

    segments = _segments(edi_text)
    claim_id = ""
    provider_npi = ""
    cpt_codes: list[str] = []
    modifiers: list[str] = []
    diagnosis_codes: list[str] = []
    notes: list[str] = []

    for segment in segments:
        elements = segment.split("*")
        tag = elements[0]
        if tag == "BHT" and len(elements) > 3:
            claim_id = elements[3]
        elif tag == "CLM" and len(elements) > 1:
            claim_id = elements[1] or claim_id
        elif tag == "NM1" and len(elements) > 9 and elements[1] == "82":
            provider_npi = elements[9]
        elif tag == "SV1" and len(elements) > 1:
            service = elements[1].split(":")
            if len(service) >= 2:
                cpt_codes.append(service[1])
            modifiers.extend(item for item in service[2:] if item)
        elif tag == "HI":
            diagnosis_codes.extend(_diagnosis_codes(elements[1:]))
        elif tag == "NTE" and len(elements) > 2:
            notes.append(elements[2])

    if not claim_id:
        raise EDI837ParseError("837 transaction is missing claim identifier")
    if not provider_npi:
        raise EDI837ParseError("837 transaction is missing rendering provider NPI")
    if not cpt_codes:
        raise EDI837ParseError("837 transaction is missing service CPT/HCPCS codes")

    return Parsed837Claim(
        claim_id=claim_id,
        provider_npi=provider_npi,
        cpt_codes=tuple(cpt_codes),
        modifiers=tuple(modifiers),
        diagnosis_codes=tuple(diagnosis_codes),
        clinical_notes=" ".join(notes),
    )


def review_837_file(
    edi_path: str | Path,
    *,
    rules_path: str | Path,
    db_path: str | Path,
    schema_path: str | Path,
    seed_path: str | Path,
) -> dict[str, Any]:
    """Parse an 837 file and run claims review.

    If the reference DB does not exist, initialize a small seeded demo DB.
    Existing DBs are preserved so full CMS NCCI reference databases are not
    overwritten during demo/API calls.
    """

    if not Path(db_path).exists():
        initialize_reference_db(db_path, schema_path, seed_path)
    parsed_claim = parse_837_claim(Path(edi_path).read_text(encoding="utf-8"))
    domain = ClaimsAnomalyDomain(
        load_claims_rule_pack(rules_path),
        ClaimsReferenceRepository(db_path),
    )
    result = domain.review_claim(parsed_claim.to_claim_data()).to_dict()
    return {
        "source": "837P",
        "parsed_claim": parsed_claim.to_claim_data(),
        "review": result,
    }


def main(argv: list[str] | None = None) -> int:
    """Small demo CLI for 837-to-claims-domain execution."""

    import argparse
    parser = argparse.ArgumentParser(description="Review a demo 837P claim file.")
    parser.add_argument("edi_file", help="Path to a supported 837P demo file.")
    parser.add_argument(
        "--rules",
        default="domains/claims_anomaly/rules/claims_anomaly.yaml",
        help="Claims anomaly rule-pack path.",
    )
    parser.add_argument(
        "--schema",
        default="domains/claims_anomaly/reference_data/schema.sql",
        help="Reference database schema SQL.",
    )
    parser.add_argument(
        "--seed",
        default="domains/claims_anomaly/reference_data/seed.sql",
        help="Reference database seed SQL.",
    )
    parser.add_argument(
        "--db",
        default=".demo/claims_reference.db",
        help="SQLite reference DB path. Defaults to .demo/claims_reference.db.",
    )
    args = parser.parse_args(argv)

    payload = review_837_file(
        args.edi_file,
        rules_path=args.rules,
        db_path=args.db,
        schema_path=args.schema,
        seed_path=args.seed,
    )
    print(json.dumps(payload, indent=2))
    return 0


def _segments(edi_text: str) -> list[str]:
    return [
        segment.strip()
        for segment in edi_text.replace("\n", "").split("~")
        if segment.strip()
    ]


def _diagnosis_codes(elements: list[str]) -> list[str]:
    codes: list[str] = []
    for element in elements:
        parts = element.split(":")
        if len(parts) >= 2:
            codes.append(parts[1])
    return codes


if __name__ == "__main__":
    raise SystemExit(main())
