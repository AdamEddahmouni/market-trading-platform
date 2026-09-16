"""Item 7 capture → PRODUCTION forecast binding (SOFTWARE/CONTROLLED fixtures only)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    CaptureLedgerCandidate,
    CaptureProvenance,
    materialize_opend_capture_jsonl,
)
from market_platform_foundation.intelligence.contracts import EventV1  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.production.item7_capture_forecast_binding import (  # noqa: E402
    REFUSAL_LEDGER_POLICY_UNSUPPORTED,
    REFUSAL_NO_LAWFUL_PRODUCTION_FORECAST,
    REFUSAL_NO_PRODUCTION_FORECAST_SOURCE,
    lookup_production_forecast_for_candidate,
    load_binding_eligible_production_contributors,
)
from market_platform_foundation.intelligence.production.emitter import emit_production_forecast  # noqa: E402
from market_platform_foundation.strategy.path_a_production_emit import (  # noqa: E402
    persist_path_a_production_contributor,
)
from tests.intelligence.outcome_fixtures import baseline_control_forecast  # noqa: E402
from tests.intelligence.test_item7_production_readiness import (  # noqa: E402
    Item7ProductionReadinessTests,
)
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
    _quote_line,
    _write_jsonl,
)
from tests.intelligence.test_path_a_production_emit import (  # noqa: E402
    PATH_A_HORIZON,
    PATH_A_TARGET,
    QUALITY,
    T,
    _emit_signals,
    _emit_snapshot,
    _fitted_model,
)
from tests.intelligence.test_persistence_fixtures import SOURCE  # noqa: E402

HORIZON = PATH_A_HORIZON.duration_ns


def _aapl_quote_line(**kwargs: object) -> dict:
    row = _quote_line(**kwargs)
    row["instrument_id"] = "AAPL"
    row["provider_symbol"] = "US.AAPL"
    return row


def _seed_forecast_ledger_prerequisites(repo: InMemoryIntelligenceRepository) -> None:
    repo.put_snapshot(_emit_snapshot())
    repo.put_event(
        EventV1(
            event_id="anchor-aapl-trade",
            schema_version="1",
            event_type="TRADE",
            event_time_ns=T,
            available_time_ns=T,
            payload={"price": 190.1, "quantity": 10},
            quality=QUALITY,
            source=SOURCE,
            instrument_id="AAPL",
            received_time_ns=T,
        )
    )


class Item7CaptureForecastBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._readiness = Item7ProductionReadinessTests()
        self._readiness.setUp()
        self.contributors = self._readiness.contributors
        self.model = self._readiness.model

    def tearDown(self) -> None:
        self._readiness.tearDown()

    def _persist_lawful_contributor(self, *, decision_time_ns: int = T) -> str:
        emitted = emit_production_forecast(
            snapshot=_emit_snapshot(),
            signals=_emit_signals(),
            model=self.model,
            target=PATH_A_TARGET,
            horizon=PATH_A_HORIZON,
            mode="paper",
            as_of_time_ns=decision_time_ns,
        )
        assert emitted.forecast is not None
        persist_path_a_production_contributor(
            emitted.forecast,
            destination=self.contributors,
            mode="paper",
        )
        return str(emitted.forecast.forecast_id)

    def test_refuses_when_no_production_forecast_source(self) -> None:
        candidate = CaptureLedgerCandidate(
            candidate_id="OCLC-test",
            event_id="evt-1",
            instrument_id="AAPL",
            decision_time_ns=T,
            horizon_ns=HORIZON,
            provenance=CaptureProvenance(
                capture_path="/tmp/capture.jsonl",
                line_index=0,
                schema_version="1",
                provider="test",
                provider_symbol="US.AAPL",
                capability="QUOTE",
                sequence=1,
                clocks={"event_time_ns": T},
                lifecycle="CAPTURED",
            ),
        )
        resolved = lookup_production_forecast_for_candidate(candidate, contributors=())
        self.assertEqual(resolved.refusal_reasons, (REFUSAL_NO_PRODUCTION_FORECAST_SOURCE,))

    def test_auto_bind_links_lawful_contributor_fail_closed_on_ledger(self) -> None:
        forecast_id = self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_aapl_quote_line()])
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                auto_bind_production_forecasts=True,
                use_production_ingress=False,
            )
            self.assertEqual(result.ledger_registered, 0)
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].forecast_id, forecast_id)
            self.assertIn(REFUSAL_LEDGER_POLICY_UNSUPPORTED, result.refusal_reasons)
            self.assertIsNotNone(repo.get_forecast(forecast_id))

    def test_auto_bind_refuses_without_contributor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                auto_bind_production_forecasts=True,
            )
            self.assertEqual(result.ledger_registered, 0)
            self.assertIn(
                REFUSAL_NO_PRODUCTION_FORECAST_SOURCE,
                result.refusal_reasons,
            )

    def test_control_forecast_not_eligible_for_binding_pool(self) -> None:
        repo = InMemoryIntelligenceRepository()
        baseline_control_forecast(repo)
        pool = load_binding_eligible_production_contributors(repository=repo)
        self.assertEqual(pool, ())

    def test_instrument_mismatch_refuses_binding(self) -> None:
        self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                auto_bind_production_forecasts=True,
            )
            self.assertEqual(result.ledger_registered, 0)
            self.assertIn(
                REFUSAL_NO_LAWFUL_PRODUCTION_FORECAST,
                result.refusal_reasons,
            )

    def test_receipt_never_claims_item7_complete(self) -> None:
        from market_platform_foundation.intelligence.production.item7_capture_forecast_binding import (
            BINDING_ARTIFACT_KIND,
        )

        self._persist_lawful_contributor()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_aapl_quote_line()])
            repo = InMemoryIntelligenceRepository()
            _seed_forecast_ledger_prerequisites(repo)
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                contributor_path=self.contributors,
                auto_bind_production_forecasts=True,
            )
            blob = json.dumps(
                {
                    "artifact_kind": BINDING_ARTIFACT_KIND,
                    "ledger_registered": result.ledger_registered,
                }
            )
            self.assertNotIn("ITEM7_COMPLETE", blob.upper())


if __name__ == "__main__":
    unittest.main()
