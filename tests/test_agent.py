from ai_agents import DryRunProvider, run_agent


def test_run_agent_returns_plan_and_provider_response():
    result = run_agent("build provider MVP", DryRunProvider())

    data = result.to_dict()

    assert data["plan"]["goal"] == "build provider MVP"
    assert data["provider_response"]["provider"] == "dry-run"
    assert data["provider_response"]["dry_run"] is True
