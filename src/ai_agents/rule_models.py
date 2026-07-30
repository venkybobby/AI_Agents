"""Rule-pack models."""

from __future__ import annotations

from dataclasses import dataclass


class RulePackError(RuntimeError):
    """Raised when a rule pack is missing or invalid."""


@dataclass(frozen=True)
class PlannerStepRule:
    """Rule defining one planner step."""

    title: str
    detail_template: str


@dataclass(frozen=True)
class PlannerRules:
    """Planner rule group."""

    steps: tuple[PlannerStepRule, ...]


@dataclass(frozen=True)
class ReviewerRules:
    """Reviewer rule group."""

    require_proposed_actions: bool
    blocked_terms: tuple[str, ...]
    blocked_finding_template: str
    approval_summary: str
    blocked_summary_template: str


@dataclass(frozen=True)
class RulePack:
    """Validated agent rule pack."""

    schema_version: int
    name: str
    description: str
    planner: PlannerRules
    reviewer: ReviewerRules

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "description": self.description,
        }
