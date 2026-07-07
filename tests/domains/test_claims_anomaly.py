from pathlib import Path

from ai_agents.domains.claims_anomaly import (
    ClaimsAnomalyDomain,
    ClaimsReferenceRepository,
    initialize_reference_db,
    load_claims_rule_pack,
)


ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "domains" / "claims_anomaly" / "rules" / "claims_anomaly.yaml"
SCHEMA = ROOT / "domains" / "claims_anomaly" / "reference_data" / "schema.sql"
SEED = ROOT / "domains" / "claims_anomaly" / "reference_data" / "seed.sql"


def _domain(tmp_path: Path) -> ClaimsAnomalyDomain:
    db_path = tmp_path / "reference.db"
    initialize_reference_db(db_path, SCHEMA, SEED)
    return ClaimsAnomalyDomain(
        load_claims_rule_pack(RULES),
        ClaimsReferenceRepository(db_path),
    )


def test_claims_domain_auto_pays_clean_claim(tmp_path):
    domain = _domain(tmp_path)

    result = domain.review_claim(
        {
            "provider_npi": "1234567890",
            "cpt_codes": ["99214"],
            "modifiers": [],
            "clinical_notes": "Moderate MDM documented with 35 minutes total time.",
        }
    )

    assert result.route == "AUTO_PAY"
    assert result.matched_gate == "anomaly_auto_pay"
    assert result.anomaly_score == 0.05
    assert "analyze_medical_necessity" in result.execution_plan


def test_claims_domain_denies_oig_excluded_provider(tmp_path):
    domain = _domain(tmp_path)

    result = domain.review_claim(
        {
            "provider_npi": "9990000000",
            "cpt_codes": ["99214"],
            "modifiers": [],
            "clinical_notes": "Moderate MDM documented.",
        }
    )

    assert result.route == "DENY_AND_REPORT"
    assert result.matched_gate == "oig_exclusion"
    assert result.tool_outputs["oig_exclusion"]["is_excluded"] is True


def test_claims_domain_denies_ncci_violation_without_modifier(tmp_path):
    domain = _domain(tmp_path)

    result = domain.review_claim(
        {
            "provider_npi": "1234567890",
            "cpt_codes": ["97110", "97530"],
            "modifiers": [],
            "clinical_notes": "Therapy note.",
        }
    )

    assert result.route == "DENY"
    assert result.matched_gate == "ncci_failed"
    assert result.tool_outputs["ncci_check"]["passed"] is False
