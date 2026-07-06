"""Read-only workspace tools for agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ToolError(RuntimeError):
    """Raised when a tool cannot safely complete."""


@dataclass(frozen=True)
class ToolAction:
    """Structured record of a tool action."""

    tool: str
    target: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "tool": self.tool,
            "target": self.target,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class WorkspaceSummary:
    """Read-only summary of a workspace path."""

    root: str
    files: tuple[str, ...]
    directories: tuple[str, ...]
    actions: tuple[ToolAction, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "files": list(self.files),
            "directories": list(self.directories),
            "actions": [action.to_dict() for action in self.actions],
        }


def inspect_workspace(path: str | Path, *, max_entries: int = 50) -> WorkspaceSummary:
    """Return a read-only summary of a workspace.

    The tool lists entries only. It does not read file contents, write files, or
    traverse outside the requested root.
    """

    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise ToolError(f"workspace path does not exist: {root}")
    if not root.is_dir():
        raise ToolError(f"workspace path is not a directory: {root}")
    if max_entries < 1:
        raise ToolError("max_entries must be at least 1")

    files: list[str] = []
    directories: list[str] = []

    for child in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        relative_name = child.name
        if child.is_dir():
            directories.append(relative_name)
        elif child.is_file():
            files.append(relative_name)

        if len(files) + len(directories) >= max_entries:
            break

    actions = (
        ToolAction(
            tool="inspect_workspace",
            target=str(root),
            status="ok",
            detail=(
                f"Listed {len(files)} files and {len(directories)} directories "
                "without reading file contents."
            ),
        ),
    )

    return WorkspaceSummary(
        root=str(root),
        files=tuple(files),
        directories=tuple(directories),
        actions=actions,
    )
