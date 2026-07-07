"""CMS NCCI PTP edit file importer.

The importer accepts CMS ZIP/TXT/CSV files downloaded from the Medicare NCCI
Procedure-to-Procedure edits page and loads active PTP edits into the configured
SQLite reference database. It is intentionally streaming and file-format tolerant
because CMS file headers vary slightly across releases.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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


def import_ncci_ptp_files(
    *,
    db_path: str | Path,
    files: Iterable[str | Path],
    edit_type: str,
    import_version: str,
) -> NCCIImportSummary:
    """Import CMS NCCI PTP edit files into SQLite."""

    files_seen = 0
    rows_seen = 0
    rows_imported = 0
    rows_skipped = 0

    with sqlite3.connect(Path(db_path)) as conn:
        for source_path in files:
            path = Path(source_path)
            files_seen += 1
            for source_name, text in _iter_source_text(path):
                for row in _parse_ptp_text(text, source_name):
                    rows_seen += 1
                    if row.modifier_indicator == "9":
                        rows_skipped += 1
                        continue
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO ncci_ptp_edits (
                            code_a,
                            code_b,
                            modifier_indicator,
                            edit_type,
                            effective_date,
                            deletion_date,
                            rationale,
                            source_file,
                            import_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row.code_a,
                            row.code_b,
                            row.modifier_indicator,
                            edit_type,
                            row.effective_date,
                            row.deletion_date,
                            row.rationale,
                            row.source_file,
                            import_version,
                        ),
                    )
                    rows_imported += 1
        conn.commit()

    return NCCIImportSummary(
        files_seen=files_seen,
        rows_seen=rows_seen,
        rows_imported=rows_imported,
        rows_skipped=rows_skipped,
    )


def _iter_source_text(path: Path) -> Iterable[tuple[str, str]]:
    if not path.exists():
        raise NCCIImportError(f"NCCI source file does not exist: {path}")

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.endswith("/"):
                    continue
                if Path(member).suffix.lower() not in {".csv", ".txt"}:
                    continue
                with archive.open(member) as handle:
                    yield member, _decode_bytes(handle.read())
        return

    yield path.name, path.read_text(encoding="utf-8-sig")


def _decode_bytes(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise NCCIImportError("unable to decode NCCI source file")


def _parse_ptp_text(text: str, source_file: str) -> Iterable[NCCIPTPRow]:
    sample = text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",|\t")
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if reader.fieldnames is None:
        raise NCCIImportError(f"NCCI file has no header row: {source_file}")

    normalized_headers = {
        _normalize_header(header): header for header in reader.fieldnames
    }
    for row in reader:
        code_a = _value(row, normalized_headers, "column1code", "column1", "code1")
        code_b = _value(row, normalized_headers, "column2code", "column2", "code2")
        modifier_indicator = _value(
            row,
            normalized_headers,
            "modifierindicator",
            "modindicator",
            "ccmi",
        )
        if not code_a or not code_b or modifier_indicator not in {"0", "1", "9"}:
            continue
        yield NCCIPTPRow(
            code_a=code_a,
            code_b=code_b,
            modifier_indicator=modifier_indicator,
            effective_date=_optional_value(
                row, normalized_headers, "effectivedate", "effective"
            ),
            deletion_date=_optional_value(
                row, normalized_headers, "deletiondate", "deletion"
            ),
            rationale=_optional_value(
                row, normalized_headers, "ptpeditrationale", "rationale"
            ),
            source_file=source_file,
        )


def _value(
    row: dict[str, str],
    headers: dict[str, str],
    *candidates: str,
) -> str:
    value = _optional_value(row, headers, *candidates)
    return "" if value is None else value


def _optional_value(
    row: dict[str, str],
    headers: dict[str, str],
    *candidates: str,
) -> str | None:
    for candidate in candidates:
        header = headers.get(candidate)
        if header is not None:
            value = row.get(header, "").strip()
            return value or None
    return None


def _normalize_header(header: str) -> str:
    return "".join(character.lower() for character in header if character.isalnum())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import CMS NCCI PTP edit files.")
    parser.add_argument("--db", required=True, help="SQLite reference DB path.")
    parser.add_argument(
        "--edit-type",
        required=True,
        choices=["practitioner", "hospital"],
        help="NCCI edit file family being imported.",
    )
    parser.add_argument(
        "--import-version",
        required=True,
        help="CMS version label, for example 2026Q3-v322r0.",
    )
    parser.add_argument("files", nargs="+", help="CMS ZIP/TXT/CSV files to import.")
    args = parser.parse_args(argv)

    summary = import_ncci_ptp_files(
        db_path=args.db,
        files=args.files,
        edit_type=args.edit_type,
        import_version=args.import_version,
    )
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
