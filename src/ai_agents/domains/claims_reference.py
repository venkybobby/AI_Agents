"""SQLite-backed claims reference/config repository."""

from __future__ import annotations

import itertools
import sqlite3
from pathlib import Path
from typing import Any

from .claims_models import ClaimsDomainError


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


def initialize_reference_db(
    db_path: str | Path,
    schema_path: str | Path,
    seed_path: str | Path,
) -> None:
    """Initialize a SQLite reference DB from schema and seed SQL files."""

    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    with sqlite3.connect(db) as conn:
        conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
        conn.executescript(Path(seed_path).read_text(encoding="utf-8"))
