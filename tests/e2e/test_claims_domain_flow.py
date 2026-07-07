from pathlib import Path

from ai_agents.domains.claims_anomaly import (
    ClaimsAnomalyDomain,
    ClaimsReferenceRepository,
    initialize_reference_db,
    load_claims_rule_pack,
)


def test_claims_domain_end_to_end_seeded_reference_data(tmp_path):
    root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "claims_reference.db"
    initialize_reference_db(
        db_path,
        root / "domains" / "claims_anomaly" / "reference_data" / "schema.sql",
        root / "domains" / "claims_anomaly" / "reference_data" / "seed.sql",
    )
    domain = ClaimsAnomalyDomain(
        load_claims_rule_pack(
            root / "domains" / "claims_anomaly" / "rules" / "claims_anomaly.yaml"
        ),
        ClaimsReferenceRepository(db_path),
    )

    result = domain.review_claim(
        {
            "provider_npi": "1234567890",
            "cpt_codes": ["99215"],
            "modifiers": [],
            "clinical_notes": "High complexity MDM with 45 minutes documented.",
        }
    ).to_dict()

    assert result["rule_pack_id"] == "claims_anomaly"
    assert result["route"] == "AUTO_PAY"
    assert result["matched_gate"] == "anomaly_auto_pay"
    assert result["execution_plan"] == [
        "check_oig_exclusion",
        "analyze_medical_necessity",
        "synthesize_decision",
    ]
