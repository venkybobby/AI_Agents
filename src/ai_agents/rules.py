"""Rule-pack loading public API."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from .rule_models import (
    PlannerRules,
    PlannerStepRule,
    ReviewerRules,
    RulePack,
    RulePackError,
)
from .rule_validation import parse_rule_pack

__all__ = [
    "PlannerRules",
    "PlannerStepRule",
    "ReviewerRules",
    "RulePack",
    "RulePackError",
    "default_rule_pack_path",
    "load_rule_pack",
]


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

    return parse_rule_pack(raw)
