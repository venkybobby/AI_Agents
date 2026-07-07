# Supabase Setup

This repo uses Supabase as the production target for configurable rules and claims reference data. Local tests still use SQLite fixtures so CI remains deterministic.

## Environment

Do not commit `.env.local`.

Use these values locally:

```text
NEXT_PUBLIC_SUPABASE_URL=https://majvoffjhrfnxbysecdu.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_JCdZOUbJG-X4UNKy-wJnkw_TBbsEoRD
SUPABASE_URL=https://majvoffjhrfnxbysecdu.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_JCdZOUbJG-X4UNKy-wJnkw_TBbsEoRD
```

For server-side import jobs, use a service-role secret or direct database URL stored only in your deployment secret manager:

```text
SUPABASE_DB_URL=postgresql://...
```

The publishable key is acceptable for browser/client reads protected by RLS. It must not be used for privileged imports.

## Apply schema

Open the Supabase SQL editor and apply:

```text
supabase/migrations/001_claims_reference.sql
```

Then optionally seed baseline thresholds/modifier rows:

```text
supabase/seed_claims_reference.sql
```

## Tables

- `runtime_thresholds`
- `oig_exclusions`
- `ncci_ptp_edits`
- `ncci_bypass_modifiers`
- `em_requirements`
- `rule_packs`
- `claim_reviews`

## NCCI production import

Download CMS NCCI PTP ZIP files as described in [NCCI_IMPORT.md](NCCI_IMPORT.md).

For production, import into Supabase using a server-side job with privileged DB credentials. Do not attempt NCCI imports from a browser client.

```powershell
python -m pip install -e ".[postgres]"
$env:SUPABASE_DB_URL = "postgresql://..."

python -m ai_agents.domains.ncci_importer `
  --postgres-url $env:SUPABASE_DB_URL `
  --edit-type practitioner `
  --import-version 2026Q3-v322r0 `
  C:\path\to\Practitioner_PTP_Edits.zip
```

## Next.js client note

If a Next.js UI is added, install:

```powershell
npm install @supabase/supabase-js @supabase/ssr
```

Then place Supabase helpers under the frontend app, not in the Python package. The Python CLI/domain runtime should continue using server-side DB access for imports and adjudication logs.
