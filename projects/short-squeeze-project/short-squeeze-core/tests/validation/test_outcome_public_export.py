from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation.public_export import assert_export_is_clean
from squeeze_core.validation.outcome_public_export import build_public_biya_outcome_export

from .test_outcome_case import original_case, outcomes
from squeeze_core.validation.outcome_case import build_biya_outcome_amendment_case


def test_public_outcome_export_is_whitelisted_and_explains_methodology_boundary():
    case = original_case()
    amendment = build_biya_outcome_amendment_case(case, outcomes("8"))
    public = build_public_biya_outcome_export(case, amendment)
    rendered = canonical_json_bytes(public)
    assert_export_is_clean(rendered)
    assert public.conclusion == "OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED"
    assert len(public.boundaries) == 2
    assert "cannot reconstruct or validate" in public.methodology_boundary
    text = rendered.decode().lower()
    for forbidden in ("profit", "p&l", "buy", "sell", "recommendation", "account_id"):
        assert forbidden not in text
