"""Focused tests for the immutable StrategyMatch contract."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    StrategyConditionResult,
    StrategyMatch,
    StrategyMatchDisposition,
    strategy_match_canonical_bytes,
    strategy_match_identity_hash,
    strategy_match_to_dict,
)
from market_platform_foundation.intelligence.quality.models import AvailabilityState  # noqa: E402
from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from market_platform_foundation.intelligence.persistence.codec import encode_document  # noqa: E402


DECISION_NS = 1_700_000_000_000_000_000


def _match(
    disposition: StrategyMatchDisposition,
    *,
    match_id: str | None = None,
    rejection_reasons: tuple[str, ...] = (),
    abstention_reasons: tuple[str, ...] = (),
    unavailability_reasons: tuple[str, ...] = (),
) -> StrategyMatch:
    return StrategyMatch(
        match_id=match_id or f"match-{disposition.value.lower()}",
        strategy_id="momentum-5m",
        strategy_identity_hash="STRATEGY-HASH-1",
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=("NVDA", "AAPL")),
        decision_time_ns=DECISION_NS,
        disposition=disposition,
        capability_state=AvailabilityState.AVAILABLE,
        quality=QualitySummary(state=QualityState.GOOD),
        source_snapshot_ref=ContractReference(kind="snapshot", id="snap-1"),
        source_evidence_refs=(ContractReference(kind="evidence", id="ev-1"),),
        source_signal_refs=(ContractReference(kind="signal", id="sig-1"),),
        condition_results=(
            StrategyConditionResult(
                condition_id="trend",
                matched=disposition == StrategyMatchDisposition.MATCHED,
                observed_value=0.8,
                expected_value=0.5,
                reason="trend threshold",
            ),
        ),
        rejection_reasons=rejection_reasons,
        abstention_reasons=abstention_reasons,
        unavailability_reasons=unavailability_reasons,
        regime="RISK_ON",
        context={"session": "REGULAR", "nested": {"venue": "XNYS"}},
        source_forecast_refs=(ContractReference(kind="forecast", id="fc-1"),),
        valid_from_ns=DECISION_NS - 60_000_000_000,
        expires_at_ns=DECISION_NS + 60_000_000_000,
        lineage_refs=(ContractReference(kind="run", id="run-1"),),
        correlation_id="corr-1",
    )


class StrategyMatchContractTests(unittest.TestCase):
    def test_match_is_immutable_and_round_trips_canonically(self) -> None:
        record = _match(StrategyMatchDisposition.MATCHED)

        with self.assertRaises(AttributeError):
            record.disposition = StrategyMatchDisposition.REJECTED  # type: ignore[misc]
        with self.assertRaises(TypeError):
            record.context["session"] = "CLOSED"  # type: ignore[index]

        payload = strategy_match_to_dict(record)
        self.assertEqual(payload["match_identity_hash"], record.match_identity_hash)
        restored = StrategyMatch.from_dict(payload)
        self.assertEqual(restored, record)
        self.assertEqual(record.matched_conditions, ("trend",))
        self.assertEqual(record.failed_conditions, ())
        self.assertEqual(record.quality_state, QualityState.GOOD)
        self.assertTrue(record.is_valid_at(DECISION_NS))
        self.assertTrue(record.is_expired(DECISION_NS + 60_000_000_000))

    def test_identity_is_deterministic_and_excludes_record_id(self) -> None:
        left = _match(StrategyMatchDisposition.MATCHED)
        right = replace(
            left,
            match_id="another-caller-supplied-id",
            source_signal_refs=tuple(reversed(left.source_signal_refs)),
        )

        self.assertEqual(strategy_match_identity_hash(left), strategy_match_identity_hash(right))
        self.assertEqual(strategy_match_canonical_bytes(left), strategy_match_canonical_bytes(left))
        self.assertEqual(left.match_identity_hash, right.match_identity_hash)

        generated = StrategyMatch.create(
            strategy_id=left.strategy_id,
            strategy_identity_hash=left.strategy_identity_hash,
            scope=left.scope,
            decision_time_ns=left.decision_time_ns,
            disposition=left.disposition,
            capability_state=left.capability_state,
            quality=left.quality,
            condition_results=left.condition_results,
        )
        self.assertEqual(generated.match_id, f"SM-{generated.match_identity_hash}")

    def test_non_selection_dispositions_require_their_reasons(self) -> None:
        for disposition, field_name in (
            (StrategyMatchDisposition.REJECTED, "rejection_reasons"),
            (StrategyMatchDisposition.ABSTAINED, "abstention_reasons"),
            (StrategyMatchDisposition.UNAVAILABLE, "unavailability_reasons"),
        ):
            with self.subTest(disposition=disposition):
                with self.assertRaises(ValueError):
                    _match(disposition)
                record = _match(disposition, **{field_name: ("reason",)})
                self.assertEqual(record.disposition, disposition)

    def test_expiry_is_explicit_and_invalid_windows_are_rejected(self) -> None:
        expired = replace(
            _match(StrategyMatchDisposition.EXPIRED),
            expires_at_ns=DECISION_NS - 1,
        )
        self.assertEqual(expired.disposition, StrategyMatchDisposition.EXPIRED)

        with self.assertRaises(ValueError):
            replace(_match(StrategyMatchDisposition.MATCHED), expires_at_ns=DECISION_NS - 1)

    def test_codec_and_repository_persist_all_dispositions_immutably(self) -> None:
        repo = InMemoryIntelligenceRepository()
        records = (
            _match(StrategyMatchDisposition.MATCHED),
            _match(
                StrategyMatchDisposition.REJECTED,
                rejection_reasons=("FAILED_TREND",),
            ),
            _match(
                StrategyMatchDisposition.ABSTAINED,
                abstention_reasons=("INSUFFICIENT_CONTEXT",),
            ),
            _match(
                StrategyMatchDisposition.UNAVAILABLE,
                unavailability_reasons=("DEPTH_UNSUPPORTED",),
            ),
            replace(
                _match(StrategyMatchDisposition.EXPIRED),
                match_id="match-expired",
                expires_at_ns=DECISION_NS + 60_000_000_000,
            ),
        )
        for record in records:
            document = encode_document(record)
            self.assertEqual(document["_id"], record.match_id)
            self.assertEqual(repo.put_strategy_match(record), RepositoryPutResult.INSERTED)
            self.assertEqual(repo.put_strategy_match(record), RepositoryPutResult.ALREADY_PRESENT)
            self.assertEqual(repo.get_strategy_match(record.match_id), record)

        with self.assertRaises(RepositoryConflictError):
            repo.put_strategy_match(
                replace(records[0], context={"session": "different"})
            )


if __name__ == "__main__":
    unittest.main()
