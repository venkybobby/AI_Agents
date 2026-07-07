from ai_agents import DryRunProvider, WorkflowStatus, run_workflow


def test_run_workflow_returns_role_events_and_shared_state():
    result = run_workflow("coordinate MVP4", DryRunProvider())

    data = result.to_dict()

    assert result.status is WorkflowStatus.APPROVED
    assert data["state"]["goal"] == "coordinate MVP4"
    assert [event["role"] for event in data["events"]] == [
        "planner",
        "implementer",
        "reviewer",
    ]
    assert data["provider_response"]["provider"] == "dry-run"


def test_reviewer_gate_blocks_write_like_actions():
    result = run_workflow("publish and push a repo", DryRunProvider())

    assert result.status is WorkflowStatus.NEEDS_INPUT
    assert result.state.reviewer_findings
    assert "explicit approval" in result.state.reviewer_findings[0]
