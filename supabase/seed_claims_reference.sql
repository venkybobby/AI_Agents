insert into public.runtime_thresholds (key, value, version, active) values
    ('auto_pay', 0.30, '2026.1', true),
    ('siu_escalation', 0.75, '2026.1', true),
    ('auto_deny', 0.95, '2026.1', true)
on conflict (key) do update set
    value = excluded.value,
    version = excluded.version,
    active = excluded.active;

insert into public.ncci_bypass_modifiers (modifier, category) values
    ('59', 'distinct_procedural_service'),
    ('XE', 'separate_encounter'),
    ('XP', 'separate_practitioner'),
    ('XS', 'separate_structure'),
    ('XU', 'unusual_non_overlapping_service'),
    ('24', 'postoperative_unrelated_em'),
    ('25', 'em_significant_separately_identifiable'),
    ('27', 'multiple_outpatient_em'),
    ('57', 'decision_for_surgery'),
    ('58', 'staged_related_procedure'),
    ('78', 'return_to_or_related_procedure'),
    ('79', 'unrelated_procedure'),
    ('91', 'repeat_clinical_diagnostic_lab_test'),
    ('LT', 'left_side'),
    ('RT', 'right_side')
on conflict (modifier) do update set
    category = excluded.category;
