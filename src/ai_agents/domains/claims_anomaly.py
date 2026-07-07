"""Claims anomaly domain pack.

Business behavior is loaded from YAML and runtime thresholds/reference data are
read from SQLite. Python code provides the execution engine and deterministic
tool adapters; it does not hardcode claim routing policy.
"""

from __future__ import annotations

import itertools
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


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


class ClaimsReferenceRepository:
    """SQLite-backed claims reference/config repository."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def threshold(self, key: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_thresholds WHERE key = ? AND active = 1",
                (key,),
            ).fetchone()
        if row is None:
            raise ClaimsDomainError(f"active threshold not found: {key}")
        return float(row["value"])

    def oig_exclusion(self, provider_id: str, id_type: str = "NPI") -> dict[str, Any]:
        normalized_id_type = id_type.upper()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT reason
                FROM oig_exclusions
                WHERE id_type = ? AND provider_id = ?
                """,
                (normalized_id_type, provider_id),
            ).fetchone()
        return {
            "provider_id": provider_id,
            "id_type": normalized_id_type,
            "is_excluded": row is not None,
            "reason": None if row is None else row["reason"],
        }

    def ncci_violation(
        self, cpt_codes: list[str], modifiers: list[str]
    ) -> dict[str, Any]:
        if len(cpt_codes) > 50:
            raise ClaimsDomainError("too many CPT codes requested")

        normalized_modifiers = {modifier.upper() for modifier in modifiers}
        with self._connect() as conn:
            for code_a, code_b in itertools.permutations(cpt_codes, 2):
                pair = conn.execute(
                    """
                    SELECT modifier_indicator
                    FROM ncci_ptp_edits
                    WHERE code_a = ? AND code_b = ?
                    """,
                    (code_a, code_b),
                ).fetchone()
                if pair is None:
                    continue
                modifier_indicator = pair["modifier_indicator"]
                if modifier_indicator == "0":
                    return {
                        "passed": False,
                        "details": f"PTP edit violation for {code_a}/{code_b}; CCMI 0 cannot be bypassed.",
                    }
                if modifier_indicator == "1" and self._has_valid_ncci_modifier(
                    conn, normalized_modifiers
                ):
                    continue
                return {
                    "passed": False,
                    "details": f"PTP edit violation for {code_a}/{code_b}; valid NCCI bypass modifier required.",
                }
        return {"passed": True, "details": None}

    def _has_valid_ncci_modifier(
        self, conn: sqlite3.Connection, modifiers: set[str]
    ) -> bool:
        if not modifiers:
            return False
        placeholders = ",".join("?" for _ in modifiers)
        rows = conn.execute(
            f"""
            SELECT modifier
            FROM ncci_bypass_modifiers
            WHERE modifier IN ({placeholders})
            """,
            tuple(modifiers),
        ).fetchall()
        return bool(rows)

    def em_requirement(self, cpt_code: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT min_time_minutes, max_time_minutes, mdm_level
                FROM em_requirements
                WHERE cpt_code = ?
                """,
                (cpt_code,),
            ).fetchone()
        if row is None:
            return None
        return {
            "cpt_code": cpt_code,
            "min_time_minutes": int(row["min_time_minutes"]),
            "max_time_minutes": int(row["max_time_minutes"]),
            "mdm_level": row["mdm_level"],
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class ClaimsAnomalyDomain:
    """Claims anomaly execution engine."""

    def __init__(
        self, rule_pack: ClaimsDomainRulePack, repository: ClaimsReferenceRepository
    ):
        self.rule_pack = rule_pack
        self.repository = repository

    def review_claim(self, claim_data: dict[str, Any]) -> ClaimsReviewResult:
        execution_plan = self.generate_execution_plan(claim_data)
        tool_outputs: dict[str, Any] = {}

        if "check_oig_exclusion" in execution_plan:
            tool_outputs["oig_exclusion"] = self.repository.oig_exclusion(
                str(claim_data.get("provider_id") or claim_data.get("provider_npi", "")),
                str(claim_data.get("provider_id_type", "NPI")),
            )

        if "run_ncci_ptp_edit_check" in execution_plan:
            tool_outputs["ncci_check"] = self.repository.ncci_violation(
                list(claim_data.get("cpt_codes", [])),
                list(claim_data.get("modifiers", [])),
            )

        if "analyze_medical_necessity" in execution_plan:
            tool_outputs["medical_necessity_check"] = self._medical_necessity(
                claim_data
            )

        anomaly_score = self._score(tool_outputs)
        routing_context = {**tool_outputs, "anomaly_score": anomaly_score}
        route, matched_gate = self._route(routing_context)

        return ClaimsReviewResult(
            rule_pack_id=self.rule_pack.id,
            rule_pack_version=self.rule_pack.version,
            execution_plan=execution_plan,
            tool_outputs=tool_outputs,
            anomaly_score=anomaly_score,
            route=route,
            matched_gate=matched_gate,
        )

    def generate_execution_plan(self, claim_data: dict[str, Any]) -> tuple[str, ...]:
        selected_tools: list[str] = []
        for tool_rule in self.rule_pack.planning_tools:
            if _condition_matches(tool_rule["condition"], claim_data):
                selected_tools.append(tool_rule["name"])
        return tuple(selected_tools)

    def _medical_necessity(self, claim_data: dict[str, Any]) -> dict[str, Any]:
        notes = str(claim_data.get("clinical_notes", "")).lower()
        em_codes = [
            code for code in claim_data.get("cpt_codes", []) if str(code).startswith("99")
        ]
        if not em_codes:
            return {"is_supported": True, "reasoning": "No E/M CPT code present."}

        requirement = self.repository.em_requirement(str(em_codes[0]))
        if requirement is None:
            return {
                "is_supported": False,
                "reasoning": f"No E/M reference requirement found for {em_codes[0]}.",
            }

        has_mdm = requirement["mdm_level"].lower() in notes
        minutes = _extract_minutes(notes)
        has_time = minutes >= requirement["min_time_minutes"]
        return {
            "is_supported": has_mdm or has_time,
            "reasoning": (
                f"Requires {requirement['mdm_level']} MDM or "
                f"{requirement['min_time_minutes']}-{requirement['max_time_minutes']} minutes; found {minutes} minutes."
            ),
        }

    def _score(self, tool_outputs: dict[str, Any]) -> float:
        score = 0.05
        if tool_outputs.get("oig_exclusion", {}).get("is_excluded") is True:
            score = max(score, 1.0)
        if tool_outputs.get("ncci_check", {}).get("passed") is False:
            score = max(score, 0.85)
        if tool_outputs.get("medical_necessity_check", {}).get("is_supported") is False:
            score = max(score, 0.80)
        return score

    def _route(self, context: dict[str, Any]) -> tuple[str, str | None]:
        for gate in self.rule_pack.routing_gates:
            if _gate_matches(gate, context, self.repository):
                return str(gate["route"]), str(gate["id"])
        return self.rule_pack.default_route, None


def load_claims_rule_pack(path: str | Path) -> ClaimsDomainRulePack:
    """Load and validate claims domain rules."""

    rule_path = Path(path).resolve()
    with rule_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ClaimsDomainError("claims rule pack must be a mapping")
    if raw.get("schema_version") != 1:
        raise ClaimsDomainError("claims rule pack schema_version must be 1")

    planning = _required_mapping(raw, "planning")
    routing = _required_mapping(raw, "routing")
    planning_tools = planning.get("tools")
    routing_gates = routing.get("gates")
    if not isinstance(planning_tools, list) or not planning_tools:
        raise ClaimsDomainError("planning.tools must be a non-empty list")
    if not isinstance(routing_gates, list) or not routing_gates:
        raise ClaimsDomainError("routing.gates must be a non-empty list")

    for tool in planning_tools:
        _validate_tool_rule(tool)
    for gate in routing_gates:
        _validate_gate(gate)

    return ClaimsDomainRulePack(
        schema_version=1,
        id=_required_str(raw, "id"),
        version=_required_str(raw, "version"),
        name=_required_str(raw, "name"),
        planning_tools=tuple(planning_tools),
        routing_gates=tuple(routing_gates),
        default_route=_required_str(routing, "default_route"),
    )


def initialize_reference_db(db_path: str | Path, schema_path: str | Path, seed_path: str | Path) -> None:
    """Initialize a SQLite reference DB from schema and seed SQL files."""

    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    with sqlite3.connect(db) as conn:
        conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
        conn.executescript(Path(seed_path).read_text(encoding="utf-8"))


def _condition_matches(condition: dict[str, Any], claim_data: dict[str, Any]) -> bool:
    condition_type = condition.get("type")
    if condition_type == "always":
        return True
    if condition_type == "min_list_length":
        values = claim_data.get(str(condition.get("field")), [])
        return isinstance(values, list) and len(values) >= int(condition.get("min", 0))
    if condition_type == "any_prefix":
        values = claim_data.get(str(condition.get("field")), [])
        prefixes = tuple(condition.get("prefixes", []))
        return isinstance(values, list) and any(
            str(value).startswith(prefixes) for value in values
        )
    raise ClaimsDomainError(f"unsupported planning condition: {condition_type}")


def _gate_matches(
    gate: dict[str, Any],
    context: dict[str, Any],
    repository: ClaimsReferenceRepository,
) -> bool:
    actual = _deep_get(context, str(gate["source"]))
    operator = gate["operator"]
    if operator == "equals":
        return actual == gate.get("value")
    if operator in {"gte_threshold", "lt_threshold"}:
        threshold = repository.threshold(str(gate["threshold_key"]))
        numeric_actual = float(actual or 0.0)
        return numeric_actual >= threshold if operator == "gte_threshold" else numeric_actual < threshold
    raise ClaimsDomainError(f"unsupported routing operator: {operator}")


def _deep_get(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _extract_minutes(notes: str) -> int:
    matches = re.findall(r"(\d+)\s*(?:minutes|mins|min)\b", notes)
    return max((int(match) for match in matches), default=0)


def mask_sensitive_identifiers(value: str) -> str:
    """Mask SSN and EIN values before logging or display."""

    masked = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "XXX-XX-XXXX", value)
    return re.sub(r"\b\d{2}-\d{7}\b", "XX-XXXXXXX", masked)


def _validate_tool_rule(tool: Any) -> None:
    if not isinstance(tool, dict):
        raise ClaimsDomainError("planning tool rule must be a mapping")
    _required_str(tool, "name")
    condition = _required_mapping(tool, "condition")
    _required_str(condition, "type")


def _validate_gate(gate: Any) -> None:
    if not isinstance(gate, dict):
        raise ClaimsDomainError("routing gate must be a mapping")
    _required_str(gate, "id")
    _required_str(gate, "source")
    _required_str(gate, "operator")
    _required_str(gate, "route")


def _required_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ClaimsDomainError(f"{key} must be a mapping")
    return value


def _required_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ClaimsDomainError(f"{key} must be a non-empty string")
    return value.strip()
