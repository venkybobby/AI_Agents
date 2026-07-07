-- Claims anomaly reference/config schema for Supabase Postgres.
-- Apply from the Supabase SQL editor or a governed migration pipeline.

create table if not exists public.runtime_thresholds (
    key text primary key,
    value numeric not null,
    version text not null,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.oig_exclusions (
    id_type text not null,
    provider_id text not null,
    reason text not null,
    source_file text,
    import_version text,
    created_at timestamptz not null default now(),
    primary key (id_type, provider_id)
);

create table if not exists public.ncci_ptp_edits (
    code_a text not null,
    code_b text not null,
    modifier_indicator text not null check (modifier_indicator in ('0', '1', '9')),
    edit_type text not null default 'unknown',
    effective_date text,
    deletion_date text,
    rationale text,
    source_file text,
    import_version text,
    created_at timestamptz not null default now(),
    primary key (code_a, code_b, edit_type)
);

create index if not exists idx_ncci_ptp_edits_code_pair
    on public.ncci_ptp_edits (code_a, code_b);

create table if not exists public.ncci_bypass_modifiers (
    modifier text primary key,
    category text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.em_requirements (
    cpt_code text primary key,
    min_time_minutes integer not null,
    max_time_minutes integer not null,
    mdm_level text not null,
    source_version text,
    created_at timestamptz not null default now()
);

create table if not exists public.rule_packs (
    id text not null,
    version text not null,
    name text not null,
    domain text not null,
    status text not null check (status in ('draft', 'active', 'retired')),
    checksum text not null,
    storage_uri text,
    rule_yaml text,
    activated_at timestamptz,
    created_at timestamptz not null default now(),
    primary key (id, version)
);

create unique index if not exists idx_rule_packs_one_active_per_domain
    on public.rule_packs (domain)
    where status = 'active';

create table if not exists public.claim_reviews (
    id uuid primary key default gen_random_uuid(),
    claim_id text,
    source text not null,
    rule_pack_id text not null,
    rule_pack_version text not null,
    route text not null,
    matched_gate text,
    anomaly_score numeric not null,
    execution_plan jsonb not null,
    tool_outputs jsonb not null,
    created_at timestamptz not null default now()
);

alter table public.runtime_thresholds enable row level security;
alter table public.oig_exclusions enable row level security;
alter table public.ncci_ptp_edits enable row level security;
alter table public.ncci_bypass_modifiers enable row level security;
alter table public.em_requirements enable row level security;
alter table public.rule_packs enable row level security;
alter table public.claim_reviews enable row level security;

-- Read policies for authenticated application users.
-- Production write/import jobs should use service-role credentials or dedicated DB roles,
-- never the browser publishable key.
create policy "authenticated read runtime thresholds"
    on public.runtime_thresholds for select
    to authenticated
    using (true);

create policy "authenticated read claims reference"
    on public.oig_exclusions for select
    to authenticated
    using (true);

create policy "authenticated read ncci edits"
    on public.ncci_ptp_edits for select
    to authenticated
    using (true);

create policy "authenticated read ncci modifiers"
    on public.ncci_bypass_modifiers for select
    to authenticated
    using (true);

create policy "authenticated read em requirements"
    on public.em_requirements for select
    to authenticated
    using (true);

create policy "authenticated read active rule packs"
    on public.rule_packs for select
    to authenticated
    using (status = 'active');
