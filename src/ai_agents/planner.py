"""Deterministic MVP planner.

The first MVP intentionally avoids external model calls. This gives the repo a
stable execution path and test loop before provider-backed agents are added.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStep:
    """A single actionable plan step."""

    order: int
    title: str
    detail: str

    def to_dict(self) -> dict[str, int | str]:
        return {
            "order": self.order,
            "title": self.title,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Plan:
    """Plan generated for a user goal."""

    goal: str
    steps: tuple[PlanStep, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
        }


def create_plan(goal: str) -> Plan:
    """Create a deterministic starter plan for a goal.

    Args:
        goal: User-provided task objective.

    Raises:
        ValueError: If the goal is blank.
    """

    normalized_goal = " ".join(goal.split())
    if not normalized_goal:
        raise ValueError("goal must not be blank")

    return Plan(
        goal=normalized_goal,
        steps=(
            PlanStep(
                order=1,
                title="Clarify success criteria",
                detail=f"Define what done means for: {normalized_goal}",
            ),
            PlanStep(
                order=2,
                title="Identify required inputs",
                detail="List files, data, credentials, tools, and constraints needed before execution.",
            ),
            PlanStep(
                order=3,
                title="Break work into safe actions",
                detail="Sequence read-only inspection before write actions, then define validation checks.",
            ),
            PlanStep(
                order=4,
                title="Validate and summarize",
                detail="Run the relevant checks and produce a concise handoff with results and remaining risks.",
            ),
        ),
    )
