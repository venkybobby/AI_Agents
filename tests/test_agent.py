from ai_agents import DryRunProvider, run_agent


def test_run_agent_returns_plan_and_provider_response():
    result = run_agent("build provider MVP", DryRunProvider())

    data = result.to_dict()

    assert data["plan"]["goal"] == "build provider MVP"
    assert data["provider_response"]["provider"] == "dry-run"
    assert data["provider_response"]["dry_run"] is True


def test_run_agent_can_include_workspace_summary(tmp_path):
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    result = run_agent("inspect workspace", DryRunProvider(), inspect_path=tmp_path)

    data = result.to_dict()
    assert data["workspace"]["files"] == ["README.md"]
    assert data["workspace"]["actions"][0]["status"] == "ok"
