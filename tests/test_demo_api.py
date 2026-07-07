from fastapi.testclient import TestClient

from ai_agents.demo_api import app


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


def test_run_medical_necessity_failure_escalates(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENTS_REFERENCE_DB", str(tmp_path / "claims_reference.db"))
    client = TestClient(app)

    response = client.post("/api/v1/demo/scenarios/medical_necessity_failure_837p/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "ESCALATE_SIU"
    assert payload["matched_gate"] == "medical_necessity_failed"
