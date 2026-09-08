from ai_business_radar_api.services.taxonomy import normalize_alias


def test_alias_normalization_is_bounded() -> None:
    assert normalize_alias("  Dental Practices! ") == "dental practices"
    assert normalize_alias("E-commerce") == "e-commerce"


def test_buyer_and_ambiguous_terms_are_not_over_normalized() -> None:
    assert normalize_alias("Dental patients") == "dental patients"
    assert normalize_alias("Shopify") == "shopify"
    assert normalize_alias("Front desk") == "front desk"
