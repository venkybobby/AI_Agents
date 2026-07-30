"""Shared models for the claims anomaly domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ClaimsDomainError(RuntimeError):
    """Raised when claims domain configuration or execution fails."""


@dataclass(frozen=True)
class ClaimsDomainRulePack:
    """Validated claims domain rules."""

    schema_version: int
    id: str
    version: str
    name: str
    planning_tools: tuple[dict[str, Any], ...]
    routing_gates: tuple[dict[str, Any], ...]
    default_route: str


@dataclass(frozen=True)
class ClaimsReviewResult:
    """Result of a claims anomaly review."""

    rule_pack_id: str
    rule_pack_version: str
    execution_plan: tuple[str, ...]
    tool_outputs: dict[str, Any]
    anomaly_score: float
    route: str
    matched_gate: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_pack_id": self.rule_pack_id,
            "rule_pack_version": self.rule_pack_version,
            "execution_plan": list(self.execution_plan),
            "tool_outputs": self.tool_outputs,
            "anomaly_score": self.anomaly_score,
            "route": self.route,
            "matched_gate": self.matched_gate,
        }
