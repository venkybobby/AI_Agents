import csv
from pathlib import Path

import sqlite3

from ai_agents.domains.claims_anomaly import initialize_reference_db
from ai_agents.domains.ncci_importer import (
    extract_ncci_ptp_files_to_csv,
    load_normalized_ncci_csv_to_sqlite,
)


def test_extract_ncci_ptp_files_to_csv_normalizes_rows(tmp_path):
    source = tmp_path / "ptp.csv"
    output = tmp_path / "normalized.csv"

    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Column 1 Code",
                "Column 2 Code",
                "Effective Date",
                "Deletion Date",
                "Modifier Indicator",
                "PTP Edit Rationale",
            ]
        )
        writer.writerow(["99214", "93000", "20260701", "", "1", "Fixture"])
        writer.writerow(["99215", "93000", "20260701", "20260701", "9", "Deleted"])

    summary = extract_ncci_ptp_files_to_csv(
        files=[source],
        output_csv=output,
        edit_type="practitioner",
        import_version="2026Q3-v322r0",
    )

    rows = list(csv.DictReader(output.open(encoding="utf-8")))

    assert summary.rows_seen == 2
    assert summary.rows_imported == 1
    assert rows == [
        {
            "code_a": "99214",
            "code_b": "93000",
            "modifier_indicator": "1",
            "edit_type": "practitioner",
            "effective_date": "20260701",
            "deletion_date": "",
            "rationale": "Fixture",
            "source_file": "ptp.csv",
            "import_version": "2026Q3-v322r0",
        }
    ]


def test_load_normalized_ncci_csv_to_sqlite(tmp_path):
    db_path = tmp_path / "reference.db"
    normalized = tmp_path / "normalized.csv"
    root = Path(__file__).resolve().parents[2]
    initialize_reference_db(
        db_path,
        root / "domains" / "claims_anomaly" / "reference_data" / "schema.sql",
        root / "domains" / "claims_anomaly" / "reference_data" / "seed.sql",
    )
    normalized.write_text(
        "\n".join(
            [
                "code_a,code_b,modifier_indicator,edit_type,effective_date,deletion_date,rationale,source_file,import_version",
                "99214,93000,1,practitioner,20260701,,Fixture,fixture.csv,2026Q3-v322r0",
            ]
        ),
        encoding="utf-8",
    )

    summary = load_normalized_ncci_csv_to_sqlite(
        db_path=db_path,
        csv_files=[normalized],
        batch_size=1,
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "select modifier_indicator from ncci_ptp_edits where code_a = '99214' and code_b = '93000'"
        ).fetchone()

    assert summary.rows_imported == 1
    assert row == ("1",)
