from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "supabase" / "migrations" / "001_claims_reference.sql"


def test_supabase_schema_contains_claims_reference_tables():
    sql = SCHEMA.read_text(encoding="utf-8")

    for table in [
        "runtime_thresholds",
        "oig_exclusions",
        "ncci_ptp_edits",
        "ncci_bypass_modifiers",
        "em_requirements",
        "rule_packs",
        "claim_reviews",
    ]:
        assert f"public.{table}" in sql


def test_supabase_schema_enables_rls():
    sql = SCHEMA.read_text(encoding="utf-8")

    assert "enable row level security" in sql
    assert "authenticated read ncci edits" in sql
