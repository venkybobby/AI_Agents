"""Claims anomaly domain pack.

Business behavior is loaded from YAML and runtime thresholds/reference data are
read from SQLite. Python code provides the execution engine and deterministic
tool adapters; it does not hardcode claim routing policy.
"""

from __future__ import annotations

import re
from typing import Any

from .claims_models import ClaimsDomainError, ClaimsDomainRulePack, ClaimsReviewResult
from .claims_reference import ClaimsReferenceRepository, initialize_reference_db
from .claims_rule_loader import load_claims_rule_pack


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
                "reasoning": "No E/M reference requirement found.",
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
