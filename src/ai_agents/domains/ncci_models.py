"""Shared models for CMS NCCI imports."""

from __future__ import annotations

from dataclasses import dataclass


class NCCIImportError(RuntimeError):
    """Raised when NCCI files cannot be imported."""


@dataclass(frozen=True)
class NCCIImportSummary:
    """Summary of imported NCCI rows."""

    files_seen: int
    rows_seen: int
    rows_imported: int
    rows_skipped: int

    def to_dict(self) -> dict[str, int]:
        return {
            "files_seen": self.files_seen,
            "rows_seen": self.rows_seen,
            "rows_imported": self.rows_imported,
            "rows_skipped": self.rows_skipped,
        }


@dataclass(frozen=True)
class NCCIPTPRow:
    """Normalized NCCI PTP edit row."""

    code_a: str
    code_b: str
    modifier_indicator: str
    effective_date: str | None
    deletion_date: str | None
    rationale: str | None
    source_file: str


@dataclass(frozen=True)
class RowsFromFiles:
    """Parsed active rows and summary metadata for source files."""

    active: tuple[NCCIPTPRow, ...]
    summary: NCCIImportSummary
