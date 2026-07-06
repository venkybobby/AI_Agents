"""High-level agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .planner import Plan, create_plan
from .providers import AgentProvider, ProviderRequest, ProviderResponse
from .tools import WorkspaceSummary, inspect_workspace


@dataclass(frozen=True)
class AgentResult:
    """Complete result for an agent run."""

    plan: Plan
    provider_response: ProviderResponse
    workspace: WorkspaceSummary | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "plan": self.plan.to_dict(),
            "provider_response": self.provider_response.to_dict(),
        }
        if self.workspace is not None:
            data["workspace"] = self.workspace.to_dict()
        return data


def run_agent(
    goal: str,
    provider: AgentProvider,
    *,
    inspect_path: str | Path | None = None,
) -> AgentResult:
    """Plan a goal and ask the provider for a normalized response."""

    plan = create_plan(goal)
    workspace = inspect_workspace(inspect_path) if inspect_path is not None else None
    prompt = _build_provider_prompt(plan)
    response = provider.complete(ProviderRequest(goal=plan.goal, prompt=prompt))
    return AgentResult(plan=plan, provider_response=response, workspace=workspace)


def _build_provider_prompt(plan: Plan) -> str:
    step_lines = "\n".join(
        f"{step.order}. {step.title}: {step.detail}" for step in plan.steps
    )
    return f"Goal: {plan.goal}\n\nPlan:\n{step_lines}"
