from ai_agents.domains.claims_anomaly import mask_sensitive_identifiers


def test_mask_sensitive_identifiers_masks_ssn_and_ein():
    masked = mask_sensitive_identifiers(
        "SSN 123-45-6789 and EIN 12-3456789 should not appear."
    )

    assert "123-45-6789" not in masked
    assert "12-3456789" not in masked
    assert "XXX-XX-XXXX" in masked
    assert "XX-XXXXXXX" in masked
