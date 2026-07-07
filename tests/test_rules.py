import pytest

from ai_agents.rules import RulePackError, load_rule_pack


def test_load_rule_pack_loads_default_rules():
    rule_pack = load_rule_pack()

    assert rule_pack.schema_version == 1
    assert rule_pack.name == "production-agent-baseline"
    assert rule_pack.planner.steps
    assert "push" in rule_pack.reviewer.blocked_terms


def test_load_rule_pack_rejects_missing_file(tmp_path):
    with pytest.raises(RulePackError, match="does not exist"):
        load_rule_pack(tmp_path / "missing.yaml")


def test_load_rule_pack_rejects_unknown_template_token(tmp_path):
    rule_file = tmp_path / "invalid.yaml"
    rule_file.write_text(
        """
schema_version: 1
name: invalid
description: Unknown template token.
planner:
  steps:
    - title: Bad
      detail_template: "Unknown {customer_id} token"
reviewer:
  require_proposed_actions: true
  blocked_terms:
    - deploy
  blocked_finding_template: "Blocked {action}"
  approval_summary: "Approved."
  blocked_summary_template: "Blocked {count}."
""",
        encoding="utf-8",
    )

    with pytest.raises(RulePackError, match="unsupported template field"):
        load_rule_pack(rule_file)
