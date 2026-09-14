"""PIT quantitative factor experiment contract — reusable interfaces only."""

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
    FactorExpressionClass,
    FactorFamily,
    FactorSign,
    InvalidDenominatorRule,
    LIVE_ELIGIBLE,
    MissingnessRule,
    MultiplicityPolicy,
    Neutralization,
    OPPORTUNITY_ENGINE_RANKING_ELIGIBLE,
    build_construction_spec,
    build_experiment_manifest,
    build_factor_observation,
    construction_spec_from_dict,
    construction_spec_to_dict,
    experiment_manifest_from_dict,
    experiment_manifest_to_dict,
    factor_observation_from_dict,
    factor_observation_to_dict,
)
from market_platform_foundation.intelligence.signals import (  # noqa: E402
    research_signal_from_factor_observation,
)

AS_OF = 1_700_000_000_000_000_000
SOURCE = AS_OF + 86_400_000_000_000
AVAILABLE = SOURCE + 1_000_000_000
FISCAL_END = AS_OF - 2_592_000_000_000_000


def _quality(state: QualityState = QualityState.GOOD) -> QualitySummary:
    return QualitySummary(state=state)


def _spec(**overrides: object):
    kwargs = dict(
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
    kwargs.update(overrides)
    return build_construction_spec(**kwargs)


class QuantFactorContractTests(unittest.TestCase):
    def test_construction_round_trip_and_identity(self) -> None:
        spec = _spec()
        cloned = construction_spec_from_dict(construction_spec_to_dict(spec))
        self.assertEqual(cloned.spec_id, spec.spec_id)
        self.assertTrue(spec.spec_id.startswith("FCSPEC-"))
        self.assertEqual(
            construction_spec_from_dict(round_trip_contract_dict(construction_spec_to_dict(spec))).spec_id,
            spec.spec_id,
        )

    def test_formula_change_is_new_experiment(self) -> None:
        first = _spec()
        second = _spec(formula="book_equity / enterprise_value")
        self.assertNotEqual(first.spec_id, second.spec_id)

    def test_current_universe_backfill_forbidden(self) -> None:
        spec = _spec()
        payload = construction_spec_to_dict(spec)
        payload["current_universe_backfill_forbidden"] = False
        with self.assertRaisesRegex(FactorContractError, "FACTOR_CURRENT_UNIVERSE_BACKFILL_FORBIDDEN"):
            construction_spec_from_dict(payload)

    def test_observation_preserves_required_row_fields(self) -> None:
        spec = _spec()
        row = build_factor_observation(
            spec=spec,
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
            fiscal_period_end_ns=FISCAL_END,
            display_symbol="AAPL",
        )
        body = factor_observation_to_dict(row)
        for key in (
            "security_id",
            "issuer_id",
            "as_of_ns",
            "source_observed_at_ns",
            "feature_id",
            "feature_version",
            "raw_input_snapshot_hash",
            "transform_version",
            "universe_version",
            "breakpoint_version",
            "portfolio_rule_version",
            "hypothesis_family_id",
            "export_hash",
        ):
            self.assertIn(key, body)
        cloned = factor_observation_from_dict(body)
        self.assertEqual(cloned.observation_id, row.observation_id)
        self.assertEqual(cloned.display_symbol, "AAPL")
        self.assertNotEqual(cloned.security_id, cloned.display_symbol)

    def test_ticker_is_not_security_identity(self) -> None:
        spec = _spec()
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TICKER_IS_NOT_SECURITY_IDENTITY"):
            build_factor_observation(
                spec=spec,
                security_id="AAPL",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                source_observed_at_ns=SOURCE,
                available_time_ns=AVAILABLE,
                raw_input_snapshot_hash="SNAP-1",
                export_hash="EXPORT-1",
                quality=_quality(),
                evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
                value=0.1,
                display_symbol="AAPL",
            )

    def test_display_symbol_excluded_from_identity(self) -> None:
        spec = _spec()
        first = build_factor_observation(
            spec=spec,
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
            display_symbol="AAPL",
        )
        second = build_factor_observation(
            spec=spec,
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
            display_symbol="AAPL.O",
        )
        self.assertEqual(first.observation_id, second.observation_id)

    def test_fiscal_period_end_is_not_availability(self) -> None:
        spec = _spec()
        with self.assertRaisesRegex(FactorContractError, "FACTOR_FISCAL_PERIOD_END_IS_NOT_AVAILABILITY"):
            build_factor_observation(
                spec=spec,
                security_id="SEC-PERMNO-12345",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                source_observed_at_ns=AS_OF,
                available_time_ns=AS_OF,
                raw_input_snapshot_hash="SNAP-1",
                export_hash="EXPORT-1",
                quality=_quality(),
                evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
                value=0.1,
                fiscal_period_end_ns=AS_OF,
            )

    def test_missing_value_does_not_fabricate(self) -> None:
        spec = _spec()
        with self.assertRaisesRegex(FactorContractError, "FACTOR_MISSING_VALUE_REQUIRES_NON_GOOD_QUALITY"):
            build_factor_observation(
                spec=spec,
                security_id="SEC-PERMNO-12345",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                source_observed_at_ns=SOURCE,
                available_time_ns=AVAILABLE,
                raw_input_snapshot_hash="SNAP-1",
                export_hash="EXPORT-1",
                quality=_quality(QualityState.GOOD),
                evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
                value=None,
            )
        missing = build_factor_observation(
            spec=spec,
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            source_observed_at_ns=SOURCE,
            available_time_ns=AVAILABLE,
            raw_input_snapshot_hash="SNAP-1",
            export_hash="EXPORT-1",
            quality=_quality(QualityState.UNKNOWN),
            evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
            value=None,
        )
        self.assertIsNone(missing.value)

    def test_promotion_fields_fail_closed(self) -> None:
        spec = _spec()
        with self.assertRaisesRegex(FactorContractError, "FACTOR_PROMOTION_FIELD_FORBIDDEN"):
            build_factor_observation(
                spec=spec,
                security_id="SEC-PERMNO-12345",
                issuer_id="ISS-CIK-0001",
                as_of_ns=AS_OF,
                source_observed_at_ns=SOURCE,
                available_time_ns=AVAILABLE,
                raw_input_snapshot_hash="SNAP-1",
                export_hash="EXPORT-1",
                quality=_quality(),
                evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
                value=0.2,
                metadata={"opportunity_id": "OPP-1"},
            )
        self.assertFalse(OPPORTUNITY_ENGINE_RANKING_ELIGIBLE)
        self.assertFalse(LIVE_ELIGIBLE)

    def test_experiment_rejects_test_overlap(self) -> None:
        spec = _spec()
        with self.assertRaisesRegex(FactorContractError, "FACTOR_TEST_OVERLAPS_VALIDATION"):
            build_experiment_manifest(
                hypothesis_family_id="hyp-value-family",
                construction_spec_ids=(spec.spec_id,),
                searched_family_size=3,
                discovery_start_ns=1,
                discovery_end_ns=10,
                validation_start_ns=10,
                validation_end_ns=20,
                untouched_test_start_ns=15,
                untouched_test_end_ns=30,
            )

    def test_experiment_round_trip(self) -> None:
        spec = _spec()
        manifest = build_experiment_manifest(
            hypothesis_family_id="hyp-value-family",
            construction_spec_ids=(spec.spec_id,),
            searched_family_size=3,
            discovery_start_ns=1,
            discovery_end_ns=10,
            validation_start_ns=10,
            validation_end_ns=20,
            untouched_test_start_ns=20,
            untouched_test_end_ns=30,
        )
        cloned = experiment_manifest_from_dict(experiment_manifest_to_dict(manifest))
        self.assertEqual(cloned.experiment_id, manifest.experiment_id)
        self.assertTrue(manifest.experiment_id.startswith("FEXP-"))

    def test_research_signal_uses_available_time_not_fiscal_end(self) -> None:
        spec = _spec()
        row = build_factor_observation(
            spec=spec,
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            source_observed_at_ns=SOURCE,
            available_time_ns=AVAILABLE,
            raw_input_snapshot_hash="SNAP-1",
            export_hash="EXPORT-1",
            quality=_quality(),
            evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
            expression_class=FactorExpressionClass.CHARACTERISTIC,
            value=0.42,
            fiscal_period_end_ns=FISCAL_END,
        )
        signal = research_signal_from_factor_observation(row)
        self.assertEqual(signal.as_of_time_ns, AVAILABLE)
        self.assertNotEqual(signal.as_of_time_ns, FISCAL_END)
        self.assertEqual(signal.scope.instrument_ids, ("SEC-PERMNO-12345",))
        self.assertEqual(signal.calculation_lineage["opportunity_engine_ranking_eligible"], "false")
        self.assertEqual(signal.metadata["research_characteristic"], "true")

    def test_missing_observation_cannot_become_signal(self) -> None:
        spec = _spec()
        row = build_factor_observation(
            spec=spec,
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            source_observed_at_ns=SOURCE,
            available_time_ns=AVAILABLE,
            raw_input_snapshot_hash="SNAP-1",
            export_hash="EXPORT-1",
            quality=_quality(QualityState.UNKNOWN),
            evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
            value=None,
        )
        with self.assertRaisesRegex(FactorContractError, "FACTOR_SIGNAL_REQUIRES_VALUE"):
            research_signal_from_factor_observation(row)

    def test_research_portfolio_is_not_operator_pnl(self) -> None:
        spec = _spec(portfolio_rule_version="academic-long-short-v1")
        row = build_factor_observation(
            spec=spec,
            security_id="SEC-PERMNO-12345",
            issuer_id="ISS-CIK-0001",
            as_of_ns=AS_OF,
            source_observed_at_ns=SOURCE,
            available_time_ns=AVAILABLE,
            raw_input_snapshot_hash="SNAP-1",
            export_hash="EXPORT-1",
            quality=_quality(),
            evidence_class=FactorEvidenceClass.SOFTWARE_FIXTURE_ONLY,
            expression_class=FactorExpressionClass.RESEARCH_PORTFOLIO,
            value=0.01,
        )
        self.assertEqual(row.expression_class, FactorExpressionClass.RESEARCH_PORTFOLIO)
        self.assertNotIn("operator_pnl", factor_observation_to_dict(row))


if __name__ == "__main__":
    unittest.main()
