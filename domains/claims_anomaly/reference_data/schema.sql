CREATE TABLE IF NOT EXISTS runtime_thresholds (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS oig_exclusions (
    id_type TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    reason TEXT NOT NULL
    , PRIMARY KEY (id_type, provider_id)
);

CREATE TABLE IF NOT EXISTS ncci_ptp_edits (
    code_a TEXT NOT NULL,
    code_b TEXT NOT NULL,
    modifier_indicator TEXT NOT NULL,
    edit_type TEXT NOT NULL DEFAULT 'unknown',
    effective_date TEXT,
    deletion_date TEXT,
    rationale TEXT,
    source_file TEXT,
    import_version TEXT,
    PRIMARY KEY (code_a, code_b)
);

CREATE INDEX IF NOT EXISTS idx_ncci_ptp_edits_code_pair
    ON ncci_ptp_edits (code_a, code_b);

CREATE TABLE IF NOT EXISTS ncci_bypass_modifiers (
    modifier TEXT PRIMARY KEY,
    category TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS em_requirements (
    cpt_code TEXT PRIMARY KEY,
    min_time_minutes INTEGER NOT NULL,
    max_time_minutes INTEGER NOT NULL,
    mdm_level TEXT NOT NULL
);
