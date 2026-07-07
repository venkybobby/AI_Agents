import csv
from pathlib import Path

from ai_agents.domains.ncci_importer import extract_ncci_ptp_files_to_csv


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
