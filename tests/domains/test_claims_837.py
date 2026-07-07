from pathlib import Path

import pytest

from ai_agents.domains.claims_837 import EDI837ParseError, parse_837_claim


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "domains" / "claims_anomaly" / "examples"


def test_parse_837_claim_extracts_normalized_claim_data():
    parsed = parse_837_claim((EXAMPLES / "clean_em_837p.edi").read_text())

    assert parsed.claim_id == "CLAIM0001"
    assert parsed.provider_npi == "1234567890"
    assert parsed.cpt_codes == ("99214",)
    assert parsed.diagnosis_codes == ("R51",)
    assert "Moderate MDM" in parsed.clinical_notes


def test_parse_837_claim_rejects_missing_required_fields():
    with pytest.raises(EDI837ParseError, match="provider NPI"):
        parse_837_claim("ST*837*0001~CLM*CLAIM0001*125.00~SV1*HC:99214*125.00~")
