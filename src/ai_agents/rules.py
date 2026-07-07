"""Rule-pack loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml


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


def default_rule_pack_path() -> Path:
    """Return the repository default rule-pack path."""

    package_root = files("ai_agents")
    return Path(str(package_root)).parents[1] / "rules" / "agent_rules.yaml"


def load_rule_pack(path: str | Path | None = None) -> RulePack:
    """Load and validate a rule pack."""

    rule_path = Path(path).expanduser() if path is not None else default_rule_pack_path()
    rule_path = rule_path.resolve()
    if not rule_path.exists():
        raise RulePackError(f"rule pack does not exist: {rule_path}")
    if not rule_path.is_file():
        raise RulePackError(f"rule pack path is not a file: {rule_path}")

    with rule_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise RulePackError("rule pack must be a YAML mapping")

    return _parse_rule_pack(raw)


def _parse_rule_pack(raw: dict[str, Any]) -> RulePack:
    schema_version = _required_int(raw, "schema_version")
    if schema_version != 1:
        raise RulePackError(f"unsupported rule-pack schema_version: {schema_version}")

    planner_raw = _required_mapping(raw, "planner")
    reviewer_raw = _required_mapping(raw, "reviewer")

    return RulePack(
        schema_version=schema_version,
        name=_required_str(raw, "name"),
        description=_required_str(raw, "description"),
        planner=PlannerRules(steps=_parse_planner_steps(planner_raw)),
        reviewer=ReviewerRules(
            require_proposed_actions=_required_bool(
                reviewer_raw, "require_proposed_actions"
            ),
            blocked_terms=tuple(
                term.lower()
                for term in _required_str_list(reviewer_raw, "blocked_terms")
            ),
            blocked_finding_template=_required_template(
                reviewer_raw,
                "blocked_finding_template",
                allowed_tokens={"action"},
                required_token="{action}",
            ),
            approval_summary=_required_str(reviewer_raw, "approval_summary"),
            blocked_summary_template=_required_template(
                reviewer_raw,
                "blocked_summary_template",
                allowed_tokens={"count"},
                required_token="{count}",
            ),
        ),
    )


def _parse_planner_steps(raw: dict[str, Any]) -> tuple[PlannerStepRule, ...]:
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RulePackError("planner.steps must be a non-empty list")

    parsed: list[PlannerStepRule] = []
    for index, item in enumerate(steps, start=1):
        if not isinstance(item, dict):
            raise RulePackError(f"planner.steps[{index}] must be a mapping")
        parsed.append(
            PlannerStepRule(
                title=_required_str(item, "title"),
                detail_template=_required_template(
                    item, "detail_template", allowed_tokens={"goal"}
                ),
            )
        )
    return tuple(parsed)


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise RulePackError(f"{key} must be a mapping")
    return value


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RulePackError(f"{key} must be a non-empty string")
    return value.strip()


def _required_template(
    raw: dict[str, Any],
    key: str,
    *,
    allowed_tokens: set[str],
    required_token: str | None = None,
) -> str:
    value = _required_str(raw, key)
    if required_token is not None and required_token not in value:
        raise RulePackError(f"{key} must include {required_token}")
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


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise RulePackError(f"{key} must be an integer")
    return value


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise RulePackError(f"{key} must be a boolean")
    return value


def _required_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list) or not value:
        raise RulePackError(f"{key} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise RulePackError(f"{key} must contain only non-empty strings")
    return [item.strip() for item in value]
