"""Persistent demo work buckets for processed claims."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / ".demo" / "claims_work_buckets.json"


BUCKET_BY_ROUTE: dict[str, dict[str, Any]] = {
    "AUTO_PAY": {
        "bucket": "auto_pay_complete",
        "label": "Auto Pay Complete",
        "default_owner": "Claims Ops",
        "sla_hours": 0,
    },
    "DENY": {
        "bucket": "coding_denial_review",
        "label": "Coding Denial Review",
        "default_owner": "Coding Review",
        "sla_hours": 24,
    },
    "DENY_AND_REPORT": {
        "bucket": "compliance_reporting",
        "label": "Compliance Reporting",
        "default_owner": "Compliance Analyst",
        "sla_hours": 4,
    },
    "PEND_MDR": {
        "bucket": "medical_director_review",
        "label": "Medical Director Review",
        "default_owner": "Medical Director",
        "sla_hours": 24,
    },
    "PEND_MR": {
        "bucket": "medical_review",
        "label": "Medical Review",
        "default_owner": "Medical Reviewer",
        "sla_hours": 24,
    },
    "ESCALATE_SIU": {
        "bucket": "siu_investigation",
        "label": "SIU Investigation",
        "default_owner": "SIU Investigator",
        "sla_hours": 4,
    },
    "MANUAL_REVIEW": {
        "bucket": "manual_review",
        "label": "Manual Review",
        "default_owner": "Claims Reviewer",
        "sla_hours": 24,
    },
}

ASSIGNABLE_USERS: dict[str, list[str]] = {
    "auto_pay_complete": ["Claims Ops", "Taylor Kim"],
    "coding_denial_review": ["Coding Review", "Sam Patel"],
    "compliance_reporting": ["Compliance Analyst", "Jordan Lee"],
    "medical_director_review": ["Medical Director", "Dr. Morgan"],
    "medical_review": ["Medical Reviewer", "Alex Rivera"],
    "siu_investigation": ["SIU Investigator", "Fraud Analyst"],
    "manual_review": ["Claims Reviewer", "Taylor Kim", "Sam Patel"],
}


@dataclass(frozen=True)
class WorkBucketStore:
    """JSON-backed demo work bucket store."""

    path: Path

    @classmethod
    def from_env(cls) -> "WorkBucketStore":
        return cls(Path(os.getenv("CLAIMS_WORK_BUCKETS_PATH", str(DEFAULT_STORE))))

    def create_item(
        self,
        *,
        claim_id: str,
        route: str,
        matched_gate: str | None,
        anomaly_score: float,
        source: str,
        parsed_claim: dict[str, Any],
        tool_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        bucket_config = bucket_for_route(route)
        created_at = datetime.now(UTC).isoformat()
        item = {
            "id": str(uuid.uuid4()),
            "claim_id": claim_id,
            "route": route,
            "matched_gate": matched_gate,
            "anomaly_score": anomaly_score,
            "bucket": bucket_config["bucket"],
            "bucket_label": bucket_config["label"],
            "assignee": bucket_config["default_owner"],
            "status": "complete" if route == "AUTO_PAY" else "open",
            "source": source,
            "sla_hours": bucket_config["sla_hours"],
            "created_at": created_at,
            "updated_at": created_at,
            "parsed_claim": parsed_claim,
            "tool_outputs": tool_outputs,
        }
        payload = self._read()
        payload["items"].append(item)
        self._write(payload)
        return item

    def list_buckets(self) -> dict[str, Any]:
        payload = self._read()
        items = payload["items"]
        buckets: list[dict[str, Any]] = []
        for route, config in BUCKET_BY_ROUTE.items():
            bucket_items = [
                item for item in items if item.get("bucket") == config["bucket"]
            ]
            buckets.append(
                {
                    "route": route,
                    "bucket": config["bucket"],
                    "label": config["label"],
                    "default_owner": config["default_owner"],
                    "assignable_users": ASSIGNABLE_USERS.get(config["bucket"], []),
                    "open_count": sum(
                        1 for item in bucket_items if item.get("status") == "open"
                    ),
                    "total_count": len(bucket_items),
                    "items": bucket_items,
                }
            )
        return {"buckets": buckets}

    def assign_item(
        self,
        *,
        item_id: str,
        assignee: str,
        status: str = "open",
    ) -> dict[str, Any]:
        payload = self._read()
        for item in payload["items"]:
            if item["id"] == item_id:
                item["assignee"] = assignee
                item["status"] = status
                item["updated_at"] = datetime.now(UTC).isoformat()
                self._write(payload)
                return item
        raise KeyError(item_id)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": []}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            return {"items": []}
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)


def bucket_for_route(route: str) -> dict[str, Any]:
    """Return bucket config for a route."""

    return BUCKET_BY_ROUTE.get(route, BUCKET_BY_ROUTE["MANUAL_REVIEW"])
