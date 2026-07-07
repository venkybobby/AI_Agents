CREATE TABLE IF NOT EXISTS runtime_thresholds (
    key TEXT PRIMARY KEY,
    value REAL NOT NULL,
    version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS oig_exclusions (
    provider_npi TEXT PRIMARY KEY,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ncci_ptp_edits (
    code_a TEXT NOT NULL,
    code_b TEXT NOT NULL,
    modifier_allowed TEXT,
    PRIMARY KEY (code_a, code_b)
);

CREATE TABLE IF NOT EXISTS em_requirements (
    cpt_code TEXT PRIMARY KEY,
    min_time_minutes INTEGER NOT NULL,
    mdm_level TEXT NOT NULL
);
