# CMS NCCI PTP Import

CMS publishes Medicare National Correct Coding Initiative Procedure-to-Procedure edit files quarterly. The production loader should ingest those CMS ZIP/TXT/CSV files into the claims reference database; the raw CMS downloads should not be committed to this repository.

## Source

CMS page:

https://www.cms.gov/medicare/coding-billing/national-correct-coding-initiative-ncci-edits/medicare-ncci-procedure-procedure-ptp-edits

As of July 7, 2026, the page lists 2026 Quarter 3 Hospital PTP and Practitioner PTP downloads, effective July 1, 2026 and posted June 1, 2026.

## Database target

The importer loads `ncci_ptp_edits`:

```text
code_a
code_b
modifier_indicator
edit_type
effective_date
deletion_date
rationale
source_file
import_version
```

Modifier indicator handling:

- `0`: cannot be bypassed with a modifier.
- `1`: may be bypassed when an appropriate NCCI-associated modifier is present.
- `9`: deleted/not applicable; skipped by the importer.

## Load command

Initialize a reference DB first, then import CMS files:

```powershell
python - <<'PY'
from ai_agents.domains.claims_anomaly import initialize_reference_db
initialize_reference_db(
    ".demo/claims_reference.db",
    "domains/claims_anomaly/reference_data/schema.sql",
    "domains/claims_anomaly/reference_data/seed.sql",
)
PY

python -m ai_agents.domains.ncci_importer `
  --db .demo/claims_reference.db `
  --edit-type practitioner `
  --import-version 2026Q3-v322r0 `
  C:\path\to\Practitioner_PTP_Edits.zip
```

Repeat for every Practitioner and Hospital PTP ZIP from the active CMS quarter, using `--edit-type hospital` for hospital files.

## Supabase/Postgres import

Install the optional Postgres dependency:

```powershell
python -m pip install -e ".[postgres]"
```

Set a privileged server-side connection string. Do not use the publishable browser key for imports.

```powershell
$env:SUPABASE_DB_URL = "postgresql://..."
```

Import to Supabase/Postgres:

```powershell
python -m ai_agents.domains.ncci_importer `
  --postgres-url $env:SUPABASE_DB_URL `
  --edit-type practitioner `
  --import-version 2026Q3-v322r0 `
  C:\path\to\Practitioner_PTP_Edits.zip
```

## Production notes

- Store downloaded CMS file checksums and import metadata.
- Import into staging tables first in production, then promote atomically.
- Keep quarterly versions available for auditability.
- Validate row counts against CMS-posted record counts before activation.
