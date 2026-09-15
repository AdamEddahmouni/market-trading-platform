"""Production ingress path: Moomoo capture JSONL → router → store/audit → replay."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.observation_ingress import (  # noqa: E402
    build_production_observation_ingress_router,
)
from market_platform_foundation.intelligence.observation_ingress.types import (  # noqa: E402
    validate_consumer_kind,
)
from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    materialize_opend_capture_jsonl,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
    _quote_line,
    _write_jsonl,
)


class ProductionIngressPathWiredTests(unittest.TestCase):
    def test_PRODUCTION_INGRESS_DEFAULT_ENFORCED(self) -> None:
        """Default materialize builds canonical production router (no opt-in ingress_router=)."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line(), _quote_line(sequence=2)])
            repo = InMemoryIntelligenceRepository()
            audit: list = []
            evidence: list[dict[str, str]] = []
            detector_seen: set[str] = set()

            def _build_router(repository, **kwargs):
                return build_production_observation_ingress_router(
                    repository,
                    audit_replay_sink=audit,
                    oe_evidence_sink=evidence,
                    detector_seen=detector_seen,
                    **kwargs,
                )

            with patch(
                "market_platform_foundation.intelligence.observation_ingress.production_wire.build_production_observation_ingress_router",
                side_effect=_build_router,
            ) as build_router:
                result = materialize_opend_capture_jsonl(
                    path,
                    repo,
                    as_of_ns=AS_OF,
                    session_start_ns=SESSION_START,
                )
                build_router.assert_called_once()
            self.assertEqual(result.events_persisted, 2)
            self.assertEqual(len(audit), 2)
            self.assertEqual(len(evidence), 2)
            self.assertEqual(len(detector_seen), 2)

    def test_materialize_does_not_double_dispatch_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line()])
            repo = InMemoryIntelligenceRepository()
            with patch.object(
                InMemoryIntelligenceRepository,
                "put_event",
                wraps=repo.put_event,
            ) as put_event:
                materialize_opend_capture_jsonl(
                    path,
                    repo,
                    as_of_ns=AS_OF,
                    session_start_ns=SESSION_START,
                )
                self.assertEqual(put_event.call_count, 1)

    def test_PRODUCTION_INGRESS_PATH_WIRED(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            _write_jsonl(path, [_quote_line(), _quote_line(sequence=2)])
            repo = InMemoryIntelligenceRepository()
            audit: list = []
            evidence: list[dict[str, str]] = []
            detector_seen: set[str] = set()
            router = build_production_observation_ingress_router(
                repo,
                audit_replay_sink=audit,
                oe_evidence_sink=evidence,
                detector_seen=detector_seen,
            )
            first = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                ingress_router=router,
            )
            self.assertEqual(first.events_persisted, 2)
            self.assertEqual(first.funnel.grid_points, 2)
            self.assertEqual(len(audit), 2)
            self.assertEqual(len(evidence), 2)
            self.assertEqual(len(detector_seen), 2)
            self.assertEqual(len(router.enrichment_triggers), 2)
            event_ids = {row["event_id"] for row in evidence}
            self.assertEqual(len(event_ids), 2)
            for event_id in event_ids:
                self.assertIsNotNone(repo.get_event(event_id))

            events_by_id = {row.event_id: row for row in audit}
            replayed = router.replay_from_journal(events_by_id, dispatch_time_ns=AS_OF + 1)
            self.assertEqual(len(replayed), 2)
            self.assertTrue(all(receipt.dispatch_id.startswith("ING-") for receipt in replayed))

            second = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                ingress_router=router,
            )
            self.assertEqual(second.events_persisted, 0)
            self.assertEqual(second.events_idempotent, 2)
            self.assertEqual(router.metrics()["duplicates"], 2)

            self.assertEqual(set(router.consumer_ids), frozenset({
                "ingress.audit_replay",
                "ingress.detector_stub",
                "ingress.enrichment_trigger",
                "ingress.oe_evidence",
                "ingress.store",
            }))
            for forbidden_kind in ("BROKER_ACTION", "EXECUTION", "ORDER_SUBMIT"):
                with self.assertRaises(ValueError):
                    validate_consumer_kind(forbidden_kind)


if __name__ == "__main__":
    unittest.main()
