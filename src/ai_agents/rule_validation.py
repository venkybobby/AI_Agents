"""Rule-pack validation helpers."""

from __future__ import annotations

from string import Formatter
from typing import Any

from .rule_models import (
    PlannerRules,
    PlannerStepRule,
    ReviewerRules,
    RulePack,
    RulePackError,
)


def parse_rule_pack(raw: dict[str, Any]) -> RulePack:
    """Parse and validate one raw rule-pack mapping."""

    schema_version = required_int(raw, "schema_version")
    if schema_version != 1:
        raise RulePackError(f"unsupported rule-pack schema_version: {schema_version}")

    planner_raw = required_mapping(raw, "planner")
    reviewer_raw = required_mapping(raw, "reviewer")

    return RulePack(
        schema_version=schema_version,
        name=required_str(raw, "name"),
        description=required_str(raw, "description"),
        planner=PlannerRules(steps=parse_planner_steps(planner_raw)),
        reviewer=ReviewerRules(
            require_proposed_actions=required_bool(
                reviewer_raw, "require_proposed_actions"
            ),
            blocked_terms=tuple(
                term.lower()
                for term in required_str_list(reviewer_raw, "blocked_terms")
            ),
            blocked_finding_template=required_template(
                reviewer_raw,
                "blocked_finding_template",
                allowed_tokens={"action"},
                required_placeholder="{action}",
            ),
            approval_summary=required_str(reviewer_raw, "approval_summary"),
            blocked_summary_template=required_template(
                reviewer_raw,
                "blocked_summary_template",
                allowed_tokens={"count"},
                required_placeholder="{count}",
            ),
        ),
    )


def parse_planner_steps(raw: dict[str, Any]) -> tuple[PlannerStepRule, ...]:
    """Parse planner step rules."""

    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RulePackError("planner.steps must be a non-empty list")

    parsed: list[PlannerStepRule] = []
    for index, item in enumerate(steps, start=1):
        if not isinstance(item, dict):
            raise RulePackError(f"planner.steps[{index}] must be a mapping")
        parsed.append(
            PlannerStepRule(
                title=required_str(item, "title"),
                detail_template=required_template(
                    item, "detail_template", allowed_tokens={"goal"}
                ),
            )
        )
    return tuple(parsed)


def required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise RulePackError(f"{key} must be a mapping")
    return value


def required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RulePackError(f"{key} must be a non-empty string")
    return value.strip()


def required_template(
    raw: dict[str, Any],
    key: str,
    *,
    allowed_tokens: set[str],
    required_placeholder: str | None = None,
) -> str:
    value = required_str(raw, key)
    if required_placeholder is not None and required_placeholder not in value:
        raise RulePackError(f"{key} must include {required_placeholder}")
    field_names = {
        field_name
        for _, field_name, _, _ in Formatter().parse(value)
        if field_name is not None
    }
    unknown_fields = field_names - allowed_tokens
    if unknown_fields:
        unknown = ", ".join(sorted(unknown_fields))
        raise RulePackError(f"{key} contains unsupported template field(s): {unknown}")
    return value


def required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise RulePackError(f"{key} must be an integer")
    return value


def required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise RulePackError(f"{key} must be a boolean")
    return value


def required_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list) or not value:
        raise RulePackError(f"{key} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise RulePackError(f"{key} must contain only non-empty strings")
    return [item.strip() for item in value]
