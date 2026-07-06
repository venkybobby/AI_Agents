"""High-level agent orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from .planner import Plan, create_plan
from .providers import AgentProvider, ProviderRequest, ProviderResponse


@dataclass(frozen=True)
class AgentResult:
    """Complete result for an agent run."""

    plan: Plan
    provider_response: ProviderResponse

    def to_dict(self) -> dict[str, object]:
        return {
            "plan": self.plan.to_dict(),
            "provider_response": self.provider_response.to_dict(),
        }


def run_agent(goal: str, provider: AgentProvider) -> AgentResult:
    """Plan a goal and ask the provider for a normalized response."""

    plan = create_plan(goal)
    prompt = _build_provider_prompt(plan)
    response = provider.complete(ProviderRequest(goal=plan.goal, prompt=prompt))
    return AgentResult(plan=plan, provider_response=response)


def _build_provider_prompt(plan: Plan) -> str:
    step_lines = "\n".join(
        f"{step.order}. {step.title}: {step.detail}" for step in plan.steps
    )
    return f"Goal: {plan.goal}\n\nPlan:\n{step_lines}"
