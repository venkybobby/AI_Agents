from pathlib import Path

import pytest

from ai_agents.tools import ToolError, inspect_workspace


def test_inspect_workspace_lists_top_level_entries(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    summary = inspect_workspace(tmp_path)

    assert summary.files == ("README.md",)
    assert summary.directories == ("src",)
    assert summary.actions[0].tool == "inspect_workspace"
    assert summary.actions[0].status == "ok"


def test_inspect_workspace_rejects_missing_path(tmp_path: Path):
    with pytest.raises(ToolError, match="does not exist"):
        inspect_workspace(tmp_path / "missing")


def test_inspect_workspace_rejects_file_path(tmp_path: Path):
    file_path = tmp_path / "README.md"
    file_path.write_text("# Test\n", encoding="utf-8")

    with pytest.raises(ToolError, match="not a directory"):
        inspect_workspace(file_path)
