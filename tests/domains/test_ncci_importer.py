import csv
import zipfile
from pathlib import Path

from ai_agents.domains.claims_anomaly import initialize_reference_db
from ai_agents.domains.ncci_importer import import_ncci_ptp_files


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "domains" / "claims_anomaly" / "reference_data" / "schema.sql"
SEED = ROOT / "domains" / "claims_anomaly" / "reference_data" / "seed.sql"


def test_import_ncci_ptp_zip_loads_active_rows_and_skips_deleted(tmp_path):
    db_path = tmp_path / "reference.db"
    initialize_reference_db(db_path, SCHEMA, SEED)
    source_zip = tmp_path / "cms_ncci_ptp.zip"
    source_csv = tmp_path / "ptp.csv"

    with source_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Column 1 Code",
                "Column 2 Code",
                "In Existence Prior to 1996",
                "Effective Date",
                "Deletion Date",
                "Modifier Indicator",
                "PTP Edit Rationale",
            ]
        )
        writer.writerow(["99214", "93000", "0", "20260701", "", "1", "Fixture"])
        writer.writerow(["99215", "93000", "0", "20260701", "20260701", "9", "Deleted"])

    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.write(source_csv, "Practitioner_PTP.csv")

    summary = import_ncci_ptp_files(
        db_path=db_path,
        files=[source_zip],
        edit_type="practitioner",
        import_version="2026Q3-v322r0",
    )

    assert summary.files_seen == 1
    assert summary.rows_seen == 2
    assert summary.rows_imported == 1
    assert summary.rows_skipped == 1
