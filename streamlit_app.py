"""Streamlit UI for dynamic 837 claim processing and work bucket assignment."""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


API_URL = os.getenv("AI_AGENTS_API_URL", "http://localhost:8000")

st.set_page_config(page_title="Claims 837 Agent Workflow", layout="wide")
st.title("Claims 837 Agent Workflow")
st.caption(
    "Submit an 837 transaction, run the backend agent gates, then place the "
    "processed claim into the correct work bucket for assignment."
)


def _get(path: str) -> requests.Response:
    return requests.get(f"{API_URL}{path}", timeout=30)


def _post(path: str, payload: dict[str, Any] | None = None) -> requests.Response:
    return requests.post(f"{API_URL}{path}", json=payload, timeout=60)


def _patch(path: str, payload: dict[str, Any]) -> requests.Response:
    return requests.patch(f"{API_URL}{path}", json=payload, timeout=30)


def _create_work_item(payload: dict[str, Any], source: str) -> dict[str, Any]:
    response = _post(
        "/api/v1/work-items",
        {
            "claim_id": payload["claim_id"],
            "route": payload["route"],
            "matched_gate": payload["matched_gate"],
            "anomaly_score": payload["anomaly_score"],
            "source": source,
            "parsed_claim": payload["parsed_claim"],
            "tool_outputs": payload["tool_outputs"],
        },
    )
    response.raise_for_status()
    return response.json()["item"]


def _render_result(payload: dict[str, Any], source: str) -> None:
    st.subheader(f"Route: {payload['route']}")
    cols = st.columns(4)
    cols[0].metric("Claim ID", payload["claim_id"])
    cols[1].metric("Score", payload["anomaly_score"])
    cols[2].metric("Matched gate", payload["matched_gate"] or "none")
    cols[3].metric(
        "Rule pack", f"{payload['rule_pack_id']}@{payload['rule_pack_version']}"
    )

    work_item = _create_work_item(payload, source)
    st.success(
        f"Created work item `{work_item['id']}` in "
        f"`{work_item['bucket_label']}` assigned to `{work_item['assignee']}`."
    )

    st.markdown("### Execution timeline")
    for event in payload["timeline"]:
        st.write(f"**{event['step']}** — `{event['status']}`")
        st.json(event["detail"])

    with st.expander("Parsed claim"):
        st.json(payload["parsed_claim"])
    with st.expander("Raw tool outputs"):
        st.json(payload["tool_outputs"])


def _run_scenario(scenario_id: str) -> None:
    response = _post(f"/api/v1/demo/scenarios/{scenario_id}/run")
    response.raise_for_status()
    _render_result(response.json(), source=f"scenario:{scenario_id}")


def _run_edi_text(edi_text: str) -> None:
    response = _post("/api/v1/claims/review-837", {"edi_text": edi_text})
    response.raise_for_status()
    _render_result(response.json(), source="uploaded_837")


def _render_bucket_board() -> None:
    st.header("Work buckets")
    response = _get("/api/v1/work-buckets")
    response.raise_for_status()
    buckets = response.json()["buckets"]

    metric_cols = st.columns(min(4, len(buckets)))
    for index, bucket in enumerate(buckets):
        metric_cols[index % len(metric_cols)].metric(
            bucket["label"],
            bucket["open_count"],
            help=f"Total items: {bucket['total_count']}",
        )

    for bucket in buckets:
        with st.expander(
            f"{bucket['label']} — {bucket['open_count']} open / "
            f"{bucket['total_count']} total",
            expanded=bucket["open_count"] > 0,
        ):
            if not bucket["items"]:
                st.info("No processed claims in this bucket yet.")
                continue

            for item in sorted(
                bucket["items"],
                key=lambda value: value.get("created_at", ""),
                reverse=True,
            ):
                cols = st.columns([1.5, 1.2, 1.2, 1.4, 1.2])
                cols[0].write(f"**{item['claim_id']}**")
                cols[1].write(item["route"])
                cols[2].write(item["status"])
                selected_assignee = cols[3].selectbox(
                    "Assignee",
                    bucket["assignable_users"] or [item["assignee"]],
                    index=(
                        bucket["assignable_users"].index(item["assignee"])
                        if item["assignee"] in bucket["assignable_users"]
                        else 0
                    ),
                    key=f"assignee-{item['id']}",
                    label_visibility="collapsed",
                )
                selected_status = cols[4].selectbox(
                    "Status",
                    ["open", "in_progress", "complete"],
                    index=["open", "in_progress", "complete"].index(item["status"]),
                    key=f"status-{item['id']}",
                    label_visibility="collapsed",
                )
                if st.button("Update assignment", key=f"assign-{item['id']}"):
                    assign_response = _patch(
                        f"/api/v1/work-items/{item['id']}/assign",
                        {
                            "assignee": selected_assignee,
                            "status": selected_status,
                        },
                    )
                    assign_response.raise_for_status()
                    st.success(f"Updated {item['claim_id']}")
                    st.rerun()

                with st.expander(f"Details for {item['claim_id']}"):
                    st.json(
                        {
                            "id": item["id"],
                            "bucket": item["bucket"],
                            "matched_gate": item["matched_gate"],
                            "anomaly_score": item["anomaly_score"],
                            "sla_hours": item["sla_hours"],
                            "source": item["source"],
                            "created_at": item["created_at"],
                            "parsed_claim": item["parsed_claim"],
                        }
                    )


with st.sidebar:
    st.header("Backend")
    st.write(API_URL)
    if st.button("Health check"):
        health = _get("/health")
        health.raise_for_status()
        st.json(health.json())

tab_scenario, tab_upload, tab_buckets = st.tabs(
    ["Run scenario", "Paste/upload 837", "Work buckets"]
)

with tab_scenario:
    scenarios_response = _get("/api/v1/demo/scenarios")
    scenarios_response.raise_for_status()
    scenarios = scenarios_response.json()
    scenario_by_label = {scenario["label"]: scenario["id"] for scenario in scenarios}
    selected_label = st.selectbox("Scenario", list(scenario_by_label))
    if st.button("Run selected scenario", type="primary"):
        _run_scenario(scenario_by_label[selected_label])

with tab_upload:
    uploaded = st.file_uploader("Upload .edi/.txt 837 file", type=["edi", "txt"])
    edi_text = ""
    if uploaded is not None:
        edi_text = uploaded.read().decode("utf-8")
    edi_text = st.text_area("837 content", value=edi_text, height=220)
    if st.button("Run pasted/uploaded 837", type="primary"):
        if not edi_text.strip():
            st.error("837 content is required.")
        else:
            _run_edi_text(edi_text)

with tab_buckets:
    if st.button("Refresh buckets"):
        st.rerun()
    _render_bucket_board()
