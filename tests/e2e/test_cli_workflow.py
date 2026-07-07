import json
import subprocess
import sys


def test_cli_workflow_uses_default_rule_pack():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_agents",
            "Prepare a production rollout plan",
            "--workflow",
            "--rules",
            "rules/agent_rules.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["status"] == "approved"
    assert payload["state"]["plan"]["steps"][0]["title"] == "Clarify success criteria"
    assert payload["events"][-1]["role"] == "reviewer"
