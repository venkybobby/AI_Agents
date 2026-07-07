INSERT OR REPLACE INTO runtime_thresholds (key, value, version, active) VALUES
    ('auto_pay', 0.30, '2026.1', 1),
    ('siu_escalation', 0.75, '2026.1', 1),
    ('auto_deny', 0.95, '2026.1', 1);

INSERT OR REPLACE INTO oig_exclusions (provider_npi, reason) VALUES
    ('9990000000', 'Seeded OIG LEIE exclusion fixture');

INSERT OR REPLACE INTO ncci_ptp_edits (code_a, code_b, modifier_allowed) VALUES
    ('97110', '97530', '59');

INSERT OR REPLACE INTO em_requirements (cpt_code, min_time_minutes, mdm_level) VALUES
    ('99214', 30, 'moderate'),
    ('99215', 40, 'high');
