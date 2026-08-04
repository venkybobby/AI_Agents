from fastapi.testclient import TestClient

from ai_agents.demo_api import app


def test_processed_claim_creates_route_bucket_item(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_WORK_BUCKETS_PATH", str(tmp_path / "buckets.json"))
    client = TestClient(app)

    response = client.post(
        "/api/v1/work-items",
        json={
            "claim_id": "GC-04",
            "route": "PEND_MDR",
            "matched_gate": "ncci_modifier_review",
            "anomaly_score": 0.05,
            "source": "test",
            "parsed_claim": {"claim_id": "GC-04"},
            "tool_outputs": {"ncci_check": {"requires_manual_review": True}},
        },
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["bucket"] == "medical_director_review"
    assert item["bucket_label"] == "Medical Director Review"
    assert item["assignee"] == "Medical Director"
    assert item["status"] == "open"

    buckets_response = client.get("/api/v1/work-buckets")
    assert buckets_response.status_code == 200
    buckets = buckets_response.json()["buckets"]
    mdr_bucket = next(
        bucket for bucket in buckets if bucket["bucket"] == "medical_director_review"
    )
    assert mdr_bucket["open_count"] == 1
    assert mdr_bucket["items"][0]["claim_id"] == "GC-04"


def test_work_item_assignment_updates_owner_and_status(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAIMS_WORK_BUCKETS_PATH", str(tmp_path / "buckets.json"))
    client = TestClient(app)
    created = client.post(
        "/api/v1/work-items",
        json={
            "claim_id": "GC-05",
            "route": "PEND_MR",
            "matched_gate": "medical_necessity_failed",
            "anomaly_score": 0.80,
            "source": "test",
            "parsed_claim": {"claim_id": "GC-05"},
            "tool_outputs": {},
        },
    ).json()["item"]

    response = client.patch(
        f"/api/v1/work-items/{created['id']}/assign",
        json={"assignee": "Alex Rivera", "status": "in_progress"},
    )

    assert response.status_code == 200
    item = response.json()["item"]
    assert item["assignee"] == "Alex Rivera"
    assert item["status"] == "in_progress"
