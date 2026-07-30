"""Database and CSV loaders for normalized CMS NCCI rows."""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from .ncci_models import NCCIImportError, NCCIImportSummary, NCCIPTPRow
from .ncci_sources import active_rows_from_files

SQLITE_INSERT = """
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
"""


def import_ncci_ptp_files(
    *,
    db_path: str | Path,
    files: Iterable[str | Path],
    edit_type: str,
    import_version: str,
) -> NCCIImportSummary:
    """Import CMS NCCI PTP edit files into SQLite."""

    rows = active_rows_from_files(files)
    with sqlite3.connect(Path(db_path)) as conn:
        conn.executemany(
            SQLITE_INSERT,
            [sqlite_row(row, edit_type, import_version) for row in rows.active],
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

    rows = active_rows_from_files(files)
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
                [sqlite_row(row, edit_type, import_version) for row in rows.active],
            )
        conn.commit()
    return rows.summary


def load_normalized_ncci_csv_to_sqlite(
    *,
    db_path: str | Path,
    csv_files: Iterable[str | Path],
    batch_size: int = 10_000,
) -> NCCIImportSummary:
    """Load already-normalized NCCI CSV files into SQLite in batches."""

    files_seen = 0
    rows_seen = 0
    rows_imported = 0
    rows_skipped = 0
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db) as conn:
        conn.execute("pragma journal_mode = wal")
        conn.execute("pragma synchronous = normal")
        conn.execute("pragma temp_store = memory")
        for csv_file in csv_files:
            files_seen += 1
            batch: list[tuple[str, str, str, str, str | None, str | None, str | None, str | None, str | None]] = []
            with Path(csv_file).open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    rows_seen += 1
                    normalized = normalized_csv_row(row)
                    if normalized is None:
                        rows_skipped += 1
                        continue
                    batch.append(normalized)
                    if len(batch) >= batch_size:
                        rows_imported += insert_sqlite_batch(conn, batch)
                        batch.clear()
                if batch:
                    rows_imported += insert_sqlite_batch(conn, batch)
        conn.commit()

    return NCCIImportSummary(
        files_seen=files_seen,
        rows_seen=rows_seen,
        rows_imported=rows_imported,
        rows_skipped=rows_skipped,
    )


def extract_ncci_ptp_files_to_csv(
    *,
    files: Iterable[str | Path],
    output_csv: str | Path,
    edit_type: str,
    import_version: str,
) -> NCCIImportSummary:
    """Extract CMS NCCI PTP source files into a normalized CSV."""

    rows = active_rows_from_files(files)
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


def sqlite_row(
    row: NCCIPTPRow,
    edit_type: str,
    import_version: str,
) -> tuple[str, str, str, str, str | None, str | None, str | None, str, str]:
    """Map a normalized PTP row to the SQLite/Postgres insert tuple."""

    return (
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


def normalized_csv_row(
    row: dict[str, str],
) -> tuple[str, str, str, str, str | None, str | None, str | None, str | None, str | None] | None:
    """Map a normalized CSV row to a DB insert tuple, or skip invalid CCMI rows."""

    modifier_indicator = row.get("modifier_indicator", "").strip()
    if modifier_indicator not in {"0", "1"}:
        return None
    return (
        row.get("code_a", "").strip(),
        row.get("code_b", "").strip(),
        modifier_indicator,
        row.get("edit_type", "").strip(),
        blank_to_none(row.get("effective_date")),
        blank_to_none(row.get("deletion_date")),
        blank_to_none(row.get("rationale")),
        blank_to_none(row.get("source_file")),
        blank_to_none(row.get("import_version")),
    )


def insert_sqlite_batch(
    conn: sqlite3.Connection,
    batch: list[tuple[str, str, str, str, str | None, str | None, str | None, str | None, str | None]],
) -> int:
    """Insert one normalized SQLite batch."""

    conn.executemany(SQLITE_INSERT, batch)
    return len(batch)


def blank_to_none(value: str | None) -> str | None:
    """Convert empty CSV values to NULL."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
