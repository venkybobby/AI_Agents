from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_agents.demo_api import app, _parse_gcs_uri


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_scenarios_includes_demo_cases():
    client = TestClient(app)

    response = client.get("/api/v1/demo/scenarios")

    assert response.status_code == 200
    scenario_ids = {scenario["id"] for scenario in response.json()}
    assert "clean_em_837p" in scenario_ids
    assert "ncci_violation_837p" in scenario_ids
    assert "medical_necessity_failure_837p" in scenario_ids


def test_run_clean_scenario_returns_timeline(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENTS_REFERENCE_DB", str(tmp_path / "claims_reference.db"))
    client = TestClient(app)

    response = client.post("/api/v1/demo/scenarios/clean_em_837p/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "AUTO_PAY"
    assert payload["execution_plan"] == [
        "check_oig_exclusion",
        "run_ncci_ptp_edit_check",
        "analyze_medical_necessity",
        "synthesize_decision",
    ]
    assert [event["step"] for event in payload["timeline"]] == [
        "OIG LEIE",
        "NCCI PTP",
        "Medical Necessity",
        "Synthesis / Routing",
    ]


def test_run_medical_necessity_failure_pends_medical_review(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENTS_REFERENCE_DB", str(tmp_path / "claims_reference.db"))
    client = TestClient(app)

    response = client.post("/api/v1/demo/scenarios/medical_necessity_failure_837p/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "PEND_MR"
    assert payload["matched_gate"] == "medical_necessity_failed"


def test_run_ncci_allowed_modifier_pends_mdr(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENTS_REFERENCE_DB", str(tmp_path / "claims_reference.db"))
    client = TestClient(app)

    response = client.post("/api/v1/demo/scenarios/ncci_allowed_modifier_837p/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "PEND_MDR"
    assert payload["matched_gate"] == "ncci_modifier_review"
    assert payload["tool_outputs"]["ncci_check"]["requires_manual_review"] is True


def test_vertex_predict_accepts_instances(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENTS_REFERENCE_DB", str(tmp_path / "claims_reference.db"))
    client = TestClient(app)
    scenario = Path("domains/claims_anomaly/examples/clean_em_837p.edi")
    edi_text = scenario.read_text(encoding="utf-8")

    response = client.post("/predict", json={"instances": [{"edi_text": edi_text}]})

    assert response.status_code == 200
    payload = response.json()
    assert payload["predictions"][0]["route"] == "AUTO_PAY"


def test_parse_gcs_uri_requires_bucket_and_object():
    assert _parse_gcs_uri("gs://claims-reference/claims_reference.db") == (
        "claims-reference",
        "claims_reference.db",
    )

    with pytest.raises(ValueError, match="must start with gs://"):
        _parse_gcs_uri("https://example.com/claims_reference.db")

    with pytest.raises(ValueError, match="must include bucket and object"):
        _parse_gcs_uri("gs://claims-reference")
