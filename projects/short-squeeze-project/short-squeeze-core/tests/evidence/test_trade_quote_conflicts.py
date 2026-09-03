from datetime import datetime
from decimal import Decimal

from squeeze_core.adapters.trades_quotes import normalize_trade_quote_record
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence

from tests.adapters.trades_quotes.test_models_and_parsing import record_values
from tests.adapters.trades_quotes.test_quote_normalizer import quote_values
from tests.adapters.trades_quotes.test_trade_normalizer import context


AS_OF = datetime.fromisoformat("2026-01-15T14:31:00+00:00")


def _obs(raw):
    return normalize_trade_quote_record(raw, context()).observations[0]


def _bundle(*observations):
    return build_point_in_time_evidence(
        "TESTA",
        observations,
        PointInTimeEvidencePolicy(
            as_of=AS_OF, include_trades_domain=True, include_quotes_domain=True
        ),
    )


def test_compatible_cross_provider_trade_price_disagreement_is_preserved():
    left = _obs(record_values(provider="A", provider_record_id="a", price="10.25"))
    right = _obs(record_values(provider="B", provider_record_id="b", price="10.26"))
    bundle = _bundle(left, right)
    conflicts = [item for item in bundle.conflicts if item.semantic_field == "trade_price"]
    assert len(conflicts) == 1
    assert set(conflicts[0].values) == {Decimal("10.25"), Decimal("10.26")}
    assert len(bundle.observations) == 2


def test_incompatible_trade_venue_scope_or_units_are_not_directly_compared():
    base = _obs(record_values(provider="A", provider_record_id="a", price="10.25"))
    different_venue = _obs(record_values(provider="B", provider_record_id="b", venue="XOTHER", price="10.26"))
    different_unit = _obs(record_values(provider="C", provider_record_id="c", size_unit="UNITS", price="10.27"))
    bundle = _bundle(base, different_venue, different_unit)
    assert not [item for item in bundle.conflicts if item.semantic_field.startswith("trade_")]


def test_compatible_quote_side_disagreement_is_preserved_without_winner():
    left = _obs(quote_values(provider="A", provider_record_id="a", ask_price="10.26"))
    right = _obs(quote_values(provider="B", provider_record_id="b", ask_price="10.27"))
    bundle = _bundle(left, right)
    conflicts = [item for item in bundle.conflicts if item.semantic_field == "quote_ask_price"]
    assert len(conflicts) == 1
    assert conflicts[0].status == "UNRESOLVED"
    dumped = bundle.model_dump(mode="json")
    assert "winner" not in dumped
    assert "average" not in dumped


def test_explicit_revision_pair_is_relationship_not_value_conflict():
    original = _obs(record_values(provider_record_id="original", price="10.25"))
    corrected = _obs(
        record_values(
            provider_record_id="corrected",
            price="10.26",
            status="CORRECTED",
            supersedes_provider_record_id="original",
        )
    ).model_copy(update={"parent_observation_ids": (original.observation_id,)})
    bundle = _bundle(original, corrected)
    assert not [item for item in bundle.conflicts if item.semantic_field.startswith("trade_")]
