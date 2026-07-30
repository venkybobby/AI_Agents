"""Claims rule-pack YAML loader and validators."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .claims_models import ClaimsDomainError, ClaimsDomainRulePack


def load_claims_rule_pack(path: str | Path) -> ClaimsDomainRulePack:
    """Load and validate claims domain rules."""

    rule_path = Path(path).resolve()
    with rule_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ClaimsDomainError("claims rule pack must be a mapping")
    if raw.get("schema_version") != 1:
        raise ClaimsDomainError("claims rule pack schema_version must be 1")

    planning = required_mapping(raw, "planning")
    routing = required_mapping(raw, "routing")
    planning_tools = planning.get("tools")
    routing_gates = routing.get("gates")
    if not isinstance(planning_tools, list) or not planning_tools:
        raise ClaimsDomainError("planning.tools must be a non-empty list")
    if not isinstance(routing_gates, list) or not routing_gates:
        raise ClaimsDomainError("routing.gates must be a non-empty list")

    for tool in planning_tools:
        validate_tool_rule(tool)
    for gate in routing_gates:
        validate_gate(gate)

    return ClaimsDomainRulePack(
        schema_version=1,
        id=required_str(raw, "id"),
        version=required_str(raw, "version"),
        name=required_str(raw, "name"),
        planning_tools=tuple(planning_tools),
        routing_gates=tuple(routing_gates),
        default_route=required_str(routing, "default_route"),
    )


def validate_tool_rule(tool: Any) -> None:
    """Validate one planning tool rule."""

    if not isinstance(tool, dict):
        raise ClaimsDomainError("planning tool rule must be a mapping")
    required_str(tool, "name")
    condition = required_mapping(tool, "condition")
    required_str(condition, "type")


def validate_gate(gate: Any) -> None:
    """Validate one routing gate rule."""

    if not isinstance(gate, dict):
        raise ClaimsDomainError("routing gate must be a mapping")
    required_str(gate, "id")
    required_str(gate, "source")
    required_str(gate, "operator")
    required_str(gate, "route")


def required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a required mapping field."""

    value = raw.get(key)
    if not isinstance(value, dict):
        raise ClaimsDomainError(f"{key} must be a mapping")
    return value


def required_str(raw: dict[str, Any], key: str) -> str:
    """Return a required non-empty string field."""

    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ClaimsDomainError(f"{key} must be a non-empty string")
    return value.strip()
