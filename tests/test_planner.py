import pytest

from ai_agents import create_plan
from ai_agents.rules import load_rule_pack


def test_create_plan_normalizes_goal_whitespace():
    plan = create_plan("  build   an agent   MVP  ", load_rule_pack())

    assert plan.goal == "build an agent MVP"
    assert len(plan.steps) == 4
    assert plan.steps[0].order == 1


def test_create_plan_rejects_blank_goal():
    with pytest.raises(ValueError, match="goal must not be blank"):
        create_plan("   ", load_rule_pack())


def test_plan_serializes_to_json_ready_dict():
    plan = create_plan("ship MVP", load_rule_pack())

    data = plan.to_dict()

    assert data["goal"] == "ship MVP"
    assert data["steps"][0]["title"] == "Clarify success criteria"
