-- Bulk-load normalized NCCI PTP CSV into Supabase/Postgres.
--
-- Recommended flow:
-- 1. Run the Python extractor:
--    python -m ai_agents.domains.ncci_importer `
--      --extract-csv .demo/ncci_ptp_2026q3_practitioner.csv `
--      --edit-type practitioner `
--      --import-version 2026Q3-v322r0 `
--      C:\path\to\CMS_NCCI_Practitioner_PTP.zip
--
-- 2. Upload/import the CSV into public.ncci_ptp_edits_stage with Supabase
--    dashboard CSV import, psql \copy, or a server-side job.
--
-- 3. Run the promotion SQL below.

create table if not exists public.ncci_ptp_edits_stage (
    code_a text not null,
    code_b text not null,
    modifier_indicator text not null,
    edit_type text not null,
    effective_date text,
    deletion_date text,
    rationale text,
    source_file text,
    import_version text
);

-- If using psql:
-- \copy public.ncci_ptp_edits_stage (
--   code_a,
--   code_b,
--   modifier_indicator,
--   edit_type,
--   effective_date,
--   deletion_date,
--   rationale,
--   source_file,
--   import_version
-- ) from 'C:/path/to/ncci_ptp_2026q3_practitioner.csv' with (format csv, header true)

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
)
select
    code_a,
    code_b,
    modifier_indicator,
    edit_type,
    nullif(effective_date, ''),
    nullif(deletion_date, ''),
    nullif(rationale, ''),
    nullif(source_file, ''),
    nullif(import_version, '')
from public.ncci_ptp_edits_stage
where modifier_indicator in ('0', '1')
on conflict (code_a, code_b, edit_type) do update set
    modifier_indicator = excluded.modifier_indicator,
    effective_date = excluded.effective_date,
    deletion_date = excluded.deletion_date,
    rationale = excluded.rationale,
    source_file = excluded.source_file,
    import_version = excluded.import_version;

-- Optional after verifying counts:
-- truncate table public.ncci_ptp_edits_stage;
