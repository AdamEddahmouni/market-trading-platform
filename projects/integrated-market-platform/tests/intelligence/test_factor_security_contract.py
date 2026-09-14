"""PIT factor/security identity binding — ticker is not identity."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    QualityState,
    QualitySummary,
    round_trip_contract_dict,
)
from market_platform_foundation.intelligence.factors import (  # noqa: E402
    CharacteristicTransform,
    FactorContractError,
    FactorEvidenceClass,
    FactorFamily,
    FactorSign,
    InvalidDenominatorRule,
    MissingnessRule,
    MultiplicityPolicy,
    Neutralization,
    bind_factor_observation,
    build_construction_spec,
    build_factor_observation,
    build_security_binding,
    security_binding_from_dict,
    security_binding_to_dict,
)
from market_platform_foundation.research.security_identity import (  # noqa: E402
    resolve_us_equity_ticker,
)

AS_OF = 1_700_000_000_000_000_000
SOURCE = AS_OF + 86_400_000_000_000
AVAILABLE = SOURCE + 1_000_000_000


def _quality(state: QualityState = QualityState.GOOD) -> QualitySummary:
    return QualitySummary(state=state)


def _spec():
    return build_construction_spec(
        feature_id="book-to-market",
        feature_version="1.0.0",
        hypothesis_family_id="hyp-value-family",
        family=FactorFamily.VALUE,
        formula="book_equity / market_equity",
        sign=FactorSign.POSITIVE,
        required_source_fields=("book_equity", "market_equity"),
        pit_lag_ns=86_400_000_000_000,
        invalid_denominator_rule=InvalidDenominatorRule.REJECT,
        missingness_rule=MissingnessRule.PROPAGATE,
        winsorization="NONE",
        transform=CharacteristicTransform.RANK,
        neutralization=Neutralization.NONE,
        universe_version="us-common-primary-v1",
        breakpoint_version="nyse-v1",
        portfolio_rule_version="NONE",
        searched_family_size=3,
        multiplicity_policy=MultiplicityPolicy.DECLARED_FDR,
        code_version="code-v1",
    )


def _observation(*, display_symbol: str | None = "AAPL"):
    return build_factor_observation(
        spec=_spec(),
        security_id="SEC-PERMNO-12345",
        issuer_id="ISS-CIK-0001",
        as_of_ns=AS_OF,
        source_observed_at_ns=SOURCE,
        available_time_ns=AVAILABLE,
        raw_input_snapshot_hash="SNAP-1",
        export_hash="EXPORT-1",
        quality=_quality(),
        evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
        value=0.42,
        display_symbol=display_symbol,
    )


class FactorSecurityContractTests(unittest.TestCase):
    def test_binding_round_trip_and_identity(self) -> None:
        binding = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
            share_class_id="SC-A",
            display_symbol="AAPL",
            listing_mic="XNAS",
        )
        cloned = security_binding_from_dict(security_binding_to_dict(binding))
        self.assertEqual(cloned.binding_id, binding.binding_id)
        self.assertTrue(binding.binding_id.startswith("FSEC-"))
        self.assertEqual(
            security_binding_from_dict(round_trip_contract_dict(security_binding_to_dict(binding))).binding_id,
            binding.binding_id,
        )

    def test_display_symbol_and_listing_excluded_from_identity(self) -> None:
        first = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
            display_symbol="AAPL",
            listing_mic="XNAS",
        )
        second = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
            display_symbol="AAPL.O",
            listing_mic="XNYS",
        )
        self.assertEqual(first.binding_id, second.binding_id)

    def test_ticker_shaped_security_id_fail_closed(self) -> None:
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY"):
            build_security_binding(
                security_id="AAPL",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                available_time_ns=AVAILABLE,
                identifier_scheme="PERMNO",
            )

    def test_ticker_scheme_fail_closed(self) -> None:
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TICKER_SCHEME_IS_NOT_SECURITY_IDENTITY"):
            build_security_binding(
                security_id="SEC-PERMNO-12345",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                available_time_ns=AVAILABLE,
                identifier_scheme="TICKER",
            )

    def test_provisional_research_ticker_map_is_not_factor_identity(self) -> None:
        row = resolve_us_equity_ticker("AAPL", venue_id="XNAS")
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY"):
            build_security_binding(
                security_id=row.instrument.instrument_id,
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                available_time_ns=AVAILABLE,
                identifier_scheme="PERMNO",
                display_symbol=row.ticker,
            )
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TICKER_SCHEME_IS_NOT_SECURITY_IDENTITY"):
            build_security_binding(
                security_id="SEC-PERMNO-12345",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                available_time_ns=AVAILABLE,
                identifier_scheme=row.instrument.namespace.upper(),
            )

    def test_current_universe_backfill_forbidden(self) -> None:
        binding = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
        )
        payload = security_binding_to_dict(binding)
        payload["current_universe_backfill_forbidden"] = False
        with self.assertRaisesRegex(FactorContractError, "FACTOR_CURRENT_UNIVERSE_BACKFILL_FORBIDDEN"):
            security_binding_from_dict(payload)

    def test_observation_binds_when_security_clocks_match(self) -> None:
        observation = _observation()
        binding = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
            display_symbol="AAPL",
        )
        joined = bind_factor_observation(observation, binding)
        self.assertIs(joined, observation)

    def test_observation_cannot_use_mapping_before_it_is_knowable(self) -> None:
        observation = _observation()
        binding = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE + 1,
            identifier_scheme="PERMNO",
            display_symbol="AAPL",
        )
        with self.assertRaisesRegex(FactorContractError, "FACTOR_SECURITY_MAPPING_NOT_YET_AVAILABLE"):
            bind_factor_observation(observation, binding)

    def test_issuer_mismatch_fail_closed(self) -> None:
        observation = _observation()
        binding = build_security_binding(
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-9999",
            as_of_ns=AS_OF,
            available_time_ns=AVAILABLE,
            identifier_scheme="PERMNO",
            display_symbol="AAPL",
        )
        with self.assertRaisesRegex(FactorContractError, "FACTOR_ISSUER_BINDING_MISMATCH"):
            bind_factor_observation(observation, binding)


if __name__ == "__main__":
    unittest.main()
