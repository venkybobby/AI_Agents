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
import os
import sqlite3
import zipfile
from collections.abc import Iterator
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

    rows = _active_rows_from_files(files)
    with sqlite3.connect(Path(db_path)) as conn:
        for row in rows.active:
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
        conn.commit()

    return rows.summary


def import_ncci_ptp_files_to_postgres(
    *,
    postgres_url: str,
    files: Iterable[str | Path],
    edit_type: str,
    import_version: str,
) -> NCCIImportSummary:
    """Import CMS NCCI PTP edit files into Supabase/Postgres."""

    rows = _active_rows_from_files(files)
    try:
        import psycopg
    except ImportError as exc:
        raise NCCIImportError(
            'Postgres import requires: python -m pip install -e ".[postgres]"'
        ) from exc

    with psycopg.connect(postgres_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                insert into public.ncci_ptp_edits (
                    code_a,
                    code_b,
                    modifier_indicator,
                    edit_type,
                    effective_date,
                    deletion_date,
                    rationale,
                    source_file,
                    import_version
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (code_a, code_b, edit_type) do update set
                    modifier_indicator = excluded.modifier_indicator,
                    effective_date = excluded.effective_date,
                    deletion_date = excluded.deletion_date,
                    rationale = excluded.rationale,
                    source_file = excluded.source_file,
                    import_version = excluded.import_version
                """,
                [
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
                    )
                    for row in rows.active
                ],
            )
        conn.commit()

    return rows.summary


def extract_ncci_ptp_files_to_csv(
    *,
    files: Iterable[str | Path],
    output_csv: str | Path,
    edit_type: str,
    import_version: str,
) -> NCCIImportSummary:
    """Extract CMS NCCI PTP source files into a normalized CSV."""

    rows = _active_rows_from_files(files)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "code_a",
                "code_b",
                "modifier_indicator",
                "edit_type",
                "effective_date",
                "deletion_date",
                "rationale",
                "source_file",
                "import_version",
            ]
        )
        for row in rows.active:
            writer.writerow(
                [
                    row.code_a,
                    row.code_b,
                    row.modifier_indicator,
                    edit_type,
                    row.effective_date or "",
                    row.deletion_date or "",
                    row.rationale or "",
                    row.source_file,
                    import_version,
                ]
            )
    return rows.summary


@dataclass(frozen=True)
class _RowsFromFiles:
    active: tuple[NCCIPTPRow, ...]
    summary: NCCIImportSummary


def _active_rows_from_files(files: Iterable[str | Path]) -> _RowsFromFiles:
    files_seen = 0
    rows_seen = 0
    rows_skipped = 0
    active_rows: list[NCCIPTPRow] = []

    for source_path in files:
        path = Path(source_path)
        files_seen += 1
        for source_name, text in _iter_source_text(path):
            for row in _parse_ptp_text(text, source_name):
                rows_seen += 1
                if row.modifier_indicator == "9":
                    rows_skipped += 1
                    continue
                active_rows.append(row)

    return _RowsFromFiles(
        active=tuple(active_rows),
        summary=NCCIImportSummary(
            files_seen=files_seen,
            rows_seen=rows_seen,
            rows_imported=len(active_rows),
            rows_skipped=rows_skipped,
        ),
    )


def _iter_source_text(path: Path) -> Iterable[tuple[str, str]]:
    if not path.exists():
        raise NCCIImportError(f"NCCI source file does not exist: {path}")

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.endswith("/"):
                    continue
                suffix = Path(member).suffix.lower()
                if suffix not in {".csv", ".txt", ".xlsx"}:
                    continue
                if suffix == ".xlsx":
                    with archive.open(member) as handle:
                        yield from _iter_xlsx_rows(handle.read(), member)
                else:
                    with archive.open(member) as handle:
                        yield member, _decode_bytes(handle.read())
        return

    if path.suffix.lower() == ".xlsx":
        yield from _iter_xlsx_rows(path.read_bytes(), path.name)
        return

    yield path.name, path.read_text(encoding="utf-8-sig")


def _iter_xlsx_rows(payload: bytes, source_name: str) -> Iterator[tuple[str, str]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise NCCIImportError(
            'Excel extraction requires: python -m pip install -e ".[excel]"'
        ) from exc

    workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    for sheet in workbook.worksheets:
        rows = sheet.iter_rows(values_only=True)
        try:
            header = next(rows)
        except StopIteration:
            continue
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["" if cell is None else cell for cell in header])
        for row in rows:
            writer.writerow(["" if cell is None else cell for cell in row])
        yield f"{source_name}:{sheet.title}", output.getvalue()


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
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--db", help="SQLite reference DB path.")
    destination.add_argument(
        "--postgres-url",
        default=os.getenv("SUPABASE_DB_URL"),
        help="Supabase/Postgres connection URL. Defaults to SUPABASE_DB_URL.",
    )
    destination.add_argument(
        "--extract-csv",
        help="Write normalized CSV instead of loading a database.",
    )
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

    if not args.db and not args.postgres_url and not args.extract_csv:
        parser.error("one of --db, --postgres-url, --extract-csv, or SUPABASE_DB_URL is required")

    if args.extract_csv:
        summary = extract_ncci_ptp_files_to_csv(
            files=args.files,
            output_csv=args.extract_csv,
            edit_type=args.edit_type,
            import_version=args.import_version,
        )
    elif args.postgres_url:
        summary = import_ncci_ptp_files_to_postgres(
            postgres_url=args.postgres_url,
            files=args.files,
            edit_type=args.edit_type,
            import_version=args.import_version,
        )
    else:
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
