"""CMS NCCI PTP edit importer CLI and public API.

The importer accepts CMS ZIP/TXT/CSV/XLSX files downloaded from the Medicare
NCCI Procedure-to-Procedure edits page and loads active PTP edits into SQLite
or Supabase/Postgres. Source parsing and database loading live in smaller
modules so this file stays limited to orchestration and CLI concerns.
"""

from __future__ import annotations

import argparse
import json
import os

from .ncci_loaders import (
    extract_ncci_ptp_files_to_csv,
    import_ncci_ptp_files,
    import_ncci_ptp_files_to_postgres,
    load_normalized_ncci_csv_to_sqlite,
)
from .ncci_models import NCCIImportError, NCCIImportSummary, NCCIPTPRow

__all__ = [
    "NCCIImportError",
    "NCCIImportSummary",
    "NCCIPTPRow",
    "extract_ncci_ptp_files_to_csv",
    "import_ncci_ptp_files",
    "import_ncci_ptp_files_to_postgres",
    "load_normalized_ncci_csv_to_sqlite",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    """Run the CMS NCCI importer command line interface."""

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
        choices=["practitioner", "hospital"],
        help="NCCI edit file family being imported.",
    )
    parser.add_argument(
        "--import-version",
        required=False,
        help="CMS version label, for example 2026Q3-v322r0.",
    )
    parser.add_argument(
        "--normalized-csv",
        action="store_true",
        help="Treat input files as normalized CSVs already produced by --extract-csv.",
    )
    parser.add_argument("files", nargs="+", help="CMS ZIP/TXT/CSV/XLSX files to import.")
    args = parser.parse_args(argv)

    if not args.db and not args.postgres_url and not args.extract_csv:
        parser.error(
            "one of --db, --postgres-url, --extract-csv, or SUPABASE_DB_URL is required"
        )
    if not args.normalized_csv and not args.edit_type:
        parser.error("--edit-type is required unless --normalized-csv is used")
    if not args.normalized_csv and not args.import_version:
        parser.error("--import-version is required unless --normalized-csv is used")

    summary = _run_import(args)
    print(json.dumps(summary.to_dict(), indent=2))
    return 0


def _run_import(args: argparse.Namespace) -> NCCIImportSummary:
    if args.normalized_csv and args.db:
        return load_normalized_ncci_csv_to_sqlite(
            db_path=args.db,
            csv_files=args.files,
        )
    if args.normalized_csv:
        raise SystemExit("--normalized-csv currently supports SQLite --db loading")
    if args.extract_csv:
        return extract_ncci_ptp_files_to_csv(
            files=args.files,
            output_csv=args.extract_csv,
            edit_type=args.edit_type,
            import_version=args.import_version,
        )
    if args.postgres_url:
        return import_ncci_ptp_files_to_postgres(
            postgres_url=args.postgres_url,
            files=args.files,
            edit_type=args.edit_type,
            import_version=args.import_version,
        )
    return import_ncci_ptp_files(
        db_path=args.db,
        files=args.files,
        edit_type=args.edit_type,
        import_version=args.import_version,
    )


if __name__ == "__main__":
    raise SystemExit(main())
