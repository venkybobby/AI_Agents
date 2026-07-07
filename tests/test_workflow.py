from ai_agents import DryRunProvider, WorkflowStatus, load_rule_pack, run_workflow


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


def test_workflow_uses_external_rule_pack(tmp_path):
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text(
        """
schema_version: 1
name: custom-test-rules
description: Custom rules for tests.
planner:
  steps:
    - title: Custom planning step
      detail_template: "Custom detail for {goal}"
reviewer:
  require_proposed_actions: true
  blocked_terms:
    - custom detail
  blocked_finding_template: "Blocked by custom rule: {action}"
  approval_summary: "Approved by custom rules."
  blocked_summary_template: "Custom rules blocked {count} action(s)."
""",
        encoding="utf-8",
    )

    result = run_workflow(
        "externalized behavior",
        DryRunProvider(),
        rule_pack=load_rule_pack(rule_file),
    )

    assert result.status is WorkflowStatus.NEEDS_INPUT
    assert result.state.plan.steps[0].title == "Custom planning step"
    assert result.state.reviewer_findings[0].startswith("Blocked by custom rule")
