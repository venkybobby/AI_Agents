"""Streamlit UI for the 837 claims agent demo."""

from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("AI_AGENTS_API_URL", "http://localhost:8000")

st.set_page_config(page_title="Claims 837 Agent Demo", layout="wide")
st.title("Claims 837 Agent Demo")
st.caption("Upload/select an 837 transaction and watch the backend agent execute OIG, NCCI, medical necessity, and routing gates.")


def _get(path: str):
    return requests.get(f"{API_URL}{path}", timeout=30)


def _post(path: str, payload: dict | None = None):
    return requests.post(f"{API_URL}{path}", json=payload, timeout=60)


def _render_result(payload: dict) -> None:
    st.subheader(f"Route: {payload['route']}")
    cols = st.columns(4)
    cols[0].metric("Claim ID", payload["claim_id"])
    cols[1].metric("Score", payload["anomaly_score"])
    cols[2].metric("Matched gate", payload["matched_gate"] or "none")
    cols[3].metric("Rule pack", f"{payload['rule_pack_id']}@{payload['rule_pack_version']}")

    st.markdown("### Execution timeline")
    for event in payload["timeline"]:
        st.write(f"**{event['step']}** — `{event['status']}`")
        st.json(event["detail"])

    with st.expander("Parsed claim"):
        st.json(payload["parsed_claim"])
    with st.expander("Raw tool outputs"):
        st.json(payload["tool_outputs"])


with st.sidebar:
    st.header("Backend")
    st.write(API_URL)
    if st.button("Health check"):
        response = _get("/health")
        st.json(response.json())

tab_scenario, tab_upload = st.tabs(["Run scenario", "Paste/upload 837"])

with tab_scenario:
    scenarios_response = _get("/api/v1/demo/scenarios")
    scenarios_response.raise_for_status()
    scenarios = scenarios_response.json()
    scenario_by_label = {scenario["label"]: scenario["id"] for scenario in scenarios}
    selected_label = st.selectbox("Scenario", list(scenario_by_label))
    if st.button("Run selected scenario", type="primary"):
        result = _post(f"/api/v1/demo/scenarios/{scenario_by_label[selected_label]}/run")
        result.raise_for_status()
        _render_result(result.json())

with tab_upload:
    uploaded = st.file_uploader("Upload .edi/.txt 837 file", type=["edi", "txt"])
    edi_text = ""
    if uploaded is not None:
        edi_text = uploaded.read().decode("utf-8")
    edi_text = st.text_area("837 content", value=edi_text, height=220)
    if st.button("Run pasted/uploaded 837", type="primary"):
        result = _post("/api/v1/claims/review-837", {"edi_text": edi_text})
        result.raise_for_status()
        _render_result(result.json())
