from pathlib import Path

from ai_agents.domains.claims_837 import review_837_file


ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "domains" / "claims_anomaly"
RULES = DOMAIN / "rules" / "claims_anomaly.yaml"
SCHEMA = DOMAIN / "reference_data" / "schema.sql"
SEED = DOMAIN / "reference_data" / "seed.sql"
EXAMPLES = DOMAIN / "examples"


def test_837_clean_em_claim_runs_all_four_steps_and_auto_pays(tmp_path):
    payload = review_837_file(
        EXAMPLES / "clean_em_837p.edi",
        rules_path=RULES,
        db_path=tmp_path / "reference.db",
        schema_path=SCHEMA,
        seed_path=SEED,
    )

    review = payload["review"]
    assert review["execution_plan"] == [
        "check_oig_exclusion",
        "run_ncci_ptp_edit_check",
        "analyze_medical_necessity",
        "synthesize_decision",
    ]
    assert review["route"] == "AUTO_PAY"
    assert review["matched_gate"] == "anomaly_auto_pay"


def test_837_ncci_claim_executes_ncci_and_denies(tmp_path):
    payload = review_837_file(
        EXAMPLES / "ncci_violation_837p.edi",
        rules_path=RULES,
        db_path=tmp_path / "reference.db",
        schema_path=SCHEMA,
        seed_path=SEED,
    )

    review = payload["review"]
    assert "run_ncci_ptp_edit_check" in review["execution_plan"]
    assert review["route"] == "DENY"
    assert review["matched_gate"] == "ncci_failed"


def test_837_oig_claim_executes_oig_and_denies_with_report(tmp_path):
    payload = review_837_file(
        EXAMPLES / "oig_excluded_837p.edi",
        rules_path=RULES,
        db_path=tmp_path / "reference.db",
        schema_path=SCHEMA,
        seed_path=SEED,
    )

    review = payload["review"]
    assert review["tool_outputs"]["oig_exclusion"]["is_excluded"] is True
    assert review["route"] == "DENY_AND_REPORT"
    assert review["matched_gate"] == "oig_exclusion"
