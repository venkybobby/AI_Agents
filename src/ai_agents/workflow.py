"""Multi-role workflow orchestration for MVP 4."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .agent import run_agent
from .planner import Plan
from .providers import AgentProvider, ProviderResponse


class WorkflowStatus(StrEnum):
    """Terminal status for a workflow run."""

    APPROVED = "approved"
    NEEDS_INPUT = "needs_input"


@dataclass(frozen=True)
class RoleEvent:
    """Single role-specific event in the workflow timeline."""

    role: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SharedTaskState:
    """State shared across workflow roles."""

    goal: str
    plan: Plan
    proposed_actions: tuple[str, ...]
    reviewer_findings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "goal": self.goal,
            "plan": self.plan.to_dict(),
            "proposed_actions": list(self.proposed_actions),
            "reviewer_findings": list(self.reviewer_findings),
        }


@dataclass(frozen=True)
class WorkflowResult:
    """Complete multi-role workflow result."""

    status: WorkflowStatus
    state: SharedTaskState
    provider_response: ProviderResponse
    events: tuple[RoleEvent, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "state": self.state.to_dict(),
            "provider_response": self.provider_response.to_dict(),
            "events": [event.to_dict() for event in self.events],
        }


def run_workflow(goal: str, provider: AgentProvider) -> WorkflowResult:
    """Run planner, implementer, and reviewer roles over shared state."""

    agent_result = run_agent(goal, provider)
    plan = agent_result.plan

    proposed_actions = tuple(
        f"{step.title}: {step.detail}" for step in plan.steps
    )
    reviewer_findings = _review_actions(proposed_actions)
    status = (
        WorkflowStatus.APPROVED
        if not reviewer_findings
        else WorkflowStatus.NEEDS_INPUT
    )

    events = (
        RoleEvent(
            role="planner",
            status="complete",
            detail=f"Created {len(plan.steps)} deterministic plan steps.",
        ),
        RoleEvent(
            role="implementer",
            status="proposed",
            detail=f"Prepared {len(proposed_actions)} proposed actions without writing files.",
        ),
        RoleEvent(
            role="reviewer",
            status=status.value,
            detail=_review_summary(status, reviewer_findings),
        ),
    )

    return WorkflowResult(
        status=status,
        state=SharedTaskState(
            goal=plan.goal,
            plan=plan,
            proposed_actions=proposed_actions,
            reviewer_findings=reviewer_findings,
        ),
        provider_response=agent_result.provider_response,
        events=events,
    )


def _review_actions(proposed_actions: tuple[str, ...]) -> tuple[str, ...]:
    findings: list[str] = []

    if not proposed_actions:
        findings.append("No proposed actions were generated.")

    write_like_terms = ("write files", "delete", "remove", "push", "deploy")
    for action in proposed_actions:
        lowered = action.lower()
        if any(term in lowered for term in write_like_terms):
            findings.append(
                f"Action needs explicit approval before execution: {action}"
            )

    return tuple(findings)


def _review_summary(
    status: WorkflowStatus, reviewer_findings: tuple[str, ...]
) -> str:
    if status is WorkflowStatus.APPROVED:
        return "Reviewer gate passed. Proposed actions are read-only or validation-focused."

    return f"Reviewer gate found {len(reviewer_findings)} issue(s) requiring input."
