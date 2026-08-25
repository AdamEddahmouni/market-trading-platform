"""BUILD 11 replay/live parity integration tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import evidence_v1_to_dict
from market_platform_foundation.intelligence.replay import ReplayClock
from market_platform_foundation.intelligence.scheduling import InferenceScheduler, StaticResourceProvider
from market_platform_foundation.intelligence.specialists import MicrostructureInferenceExecutor
from tests.intelligence.routing_fixtures import T
from tests.intelligence.specialists_fixtures import order_flow_detection, routed_microstructure_job


def _cpu_resources():
    from market_platform_foundation.intelligence.scheduling import ResourceClass, ResourceSnapshot

    return ResourceSnapshot(
        captured_at_ns=T,
        cpu_slots_total=8,
        cpu_slots_available=8,
        gpu_slots_total=0,
        gpu_slots_available=0,
        vram_bytes_total=0,
        vram_bytes_available=0,
        supported_resource_classes=frozenset({ResourceClass.CPU}),
    )


class SpecialistReplayIntegrationTests(unittest.TestCase):
    def _run_once(self, now_ns: int) -> dict[str, object]:
        _, snap2, sig_prev, sig_curr, detection = order_flow_detection()
        repo, route, job = routed_microstructure_job(
            detection,
            snap2,
            signals=(sig_prev, sig_curr),
            scheduler_time_ns=now_ns,
        )
        executor = MicrostructureInferenceExecutor(repository=repo)
        scheduler = InferenceScheduler(
            executor=executor,
            resource_provider=StaticResourceProvider(_cpu_resources()),
        )
        scheduler.submit_route(route, scheduler_time_ns=now_ns)
        scheduler.schedule_once(now_ns)
        outcome = executor.outcomes[job.job_id]
        return {
            "evidence_id": outcome.evidence[0].evidence_id,
            "content": evidence_v1_to_dict(outcome.evidence[0]),
        }

    def test_live_replay_parity(self) -> None:
        live = self._run_once(T)
        replay = self._run_once(T)
        self.assertEqual(live["evidence_id"], replay["evidence_id"])
        self.assertEqual(live["content"], replay["content"])

    def test_replay_clock_parity(self) -> None:
        clock = ReplayClock(T)
        live = self._run_once(T)
        replay = self._run_once(clock.now_ns())
        self.assertEqual(live, replay)


if __name__ == "__main__":
    unittest.main()
