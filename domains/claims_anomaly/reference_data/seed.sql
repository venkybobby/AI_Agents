INSERT OR REPLACE INTO runtime_thresholds (key, value, version, active) VALUES
    ('auto_pay', 0.30, '2026.1', 1),
    ('siu_escalation', 0.75, '2026.1', 1),
    ('auto_deny', 0.95, '2026.1', 1);

INSERT OR REPLACE INTO oig_exclusions (id_type, provider_id, reason) VALUES
    ('NPI', '9990000000', 'Seeded OIG LEIE exclusion fixture'),
    ('EIN', '99-9999999', 'Seeded OIG LEIE exclusion fixture'),
    ('SSN', '999-99-9999', 'Seeded OIG LEIE exclusion fixture');

INSERT OR REPLACE INTO ncci_ptp_edits (
    code_a,
    code_b,
    modifier_indicator,
    edit_type,
    effective_date,
    deletion_date,
    rationale,
    source_file,
    import_version
) VALUES
    ('97110', '97530', '1', 'practitioner', '20260701', NULL, 'Seed PTP edit fixture', 'seed.sql', 'demo'),
    ('11111', '22222', '0', 'practitioner', '20260701', NULL, 'Seed CCMI 0 fixture', 'seed.sql', 'demo');

INSERT OR REPLACE INTO ncci_bypass_modifiers (modifier, category) VALUES
    ('59', 'distinct_procedural_service'),
    ('XE', 'separate_encounter'),
    ('XP', 'separate_practitioner'),
    ('XS', 'separate_structure'),
    ('XU', 'unusual_non_overlapping_service'),
    ('25', 'em_significant_separately_identifiable'),
    ('27', 'multiple_outpatient_em'),
    ('58', 'staged_related_procedure'),
    ('78', 'return_to_or_related_procedure'),
    ('79', 'unrelated_procedure'),
    ('LT', 'left_side'),
    ('RT', 'right_side'),
    ('E1', 'anatomic_modifier'),
    ('E2', 'anatomic_modifier'),
    ('E3', 'anatomic_modifier'),
    ('E4', 'anatomic_modifier'),
    ('FA', 'anatomic_modifier'),
    ('F1', 'anatomic_modifier'),
    ('F2', 'anatomic_modifier'),
    ('F3', 'anatomic_modifier'),
    ('F4', 'anatomic_modifier'),
    ('F5', 'anatomic_modifier'),
    ('F6', 'anatomic_modifier'),
    ('F7', 'anatomic_modifier'),
    ('F8', 'anatomic_modifier'),
    ('F9', 'anatomic_modifier'),
    ('TA', 'anatomic_modifier'),
    ('T1', 'anatomic_modifier'),
    ('T2', 'anatomic_modifier'),
    ('T3', 'anatomic_modifier'),
    ('T4', 'anatomic_modifier'),
    ('T5', 'anatomic_modifier'),
    ('T6', 'anatomic_modifier'),
    ('T7', 'anatomic_modifier'),
    ('T8', 'anatomic_modifier'),
    ('T9', 'anatomic_modifier'),
    ('LC', 'coronary_anatomic_modifier'),
    ('LD', 'coronary_anatomic_modifier'),
    ('RC', 'coronary_anatomic_modifier'),
    ('LM', 'coronary_anatomic_modifier'),
    ('RI', 'coronary_anatomic_modifier');

INSERT OR REPLACE INTO em_requirements (cpt_code, min_time_minutes, max_time_minutes, mdm_level) VALUES
    ('99202', 15, 29, 'straightforward'),
    ('99203', 30, 44, 'low'),
    ('99204', 45, 59, 'moderate'),
    ('99205', 60, 74, 'high'),
    ('99212', 10, 19, 'straightforward'),
    ('99213', 20, 29, 'low'),
    ('99214', 30, 39, 'moderate'),
    ('99215', 40, 54, 'high');
