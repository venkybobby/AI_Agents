"""Rule-pack driven planner."""

from __future__ import annotations

from dataclasses import dataclass

from .rules import RulePack, load_rule_pack


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


def create_plan(goal: str, rule_pack: RulePack | None = None) -> Plan:
    """Create a plan from the active rule pack.

    Args:
        goal: User-provided task objective.

    Raises:
        ValueError: If the goal is blank.
    """

    normalized_goal = " ".join(goal.split())
    if not normalized_goal:
        raise ValueError("goal must not be blank")

    active_rule_pack = rule_pack or load_rule_pack()
    return Plan(
        goal=normalized_goal,
        steps=tuple(
            PlanStep(
                order=index,
                title=step_rule.title,
                detail=step_rule.detail_template.format(goal=normalized_goal),
            )
            for index, step_rule in enumerate(active_rule_pack.planner.steps, start=1)
        ),
    )
