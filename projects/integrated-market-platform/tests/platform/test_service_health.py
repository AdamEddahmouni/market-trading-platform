from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.platform.control_service import build_control_status, check_update_cached
from tools.platform.local_launcher import PlatformController, ServiceRecord
from tools.platform.service_health import (
    ServiceHealthSnapshot,
    aggregate_platform_health,
    evaluate_service_health,
    process_alive,
)


class ServiceHealthTests(unittest.TestCase):
    def test_process_alive_rejects_invalid_pid(self) -> None:
        self.assertFalse(process_alive(0))
        self.assertFalse(process_alive(-1))

    def test_health_distinguishes_port_bound_from_http_and_process(self) -> None:
        health = evaluate_service_health(
            pid=999999,
            host="127.0.0.1",
            port=8766,
            http_url="http://127.0.0.1:8766/context",
            identity=["run_ui_api.py"],
            command_line=lambda _pid: None,
            identity_matches=lambda _line, _identity: False,
            port_is_open=lambda _host, _port: True,
        )
        self.assertTrue(health.port_bound)
        self.assertFalse(health.process_alive)
        self.assertFalse(health.identity_owned)
        self.assertFalse(health.http_alive)

    def test_aggregate_ready_requires_process_and_http(self) -> None:
        ready = {
            "api": ServiceHealthSnapshot(True, True, True, True),
            "ui": ServiceHealthSnapshot(True, True, True, True),
            "control": ServiceHealthSnapshot(True, None, True, True),
        }
        partial = dict(ready)
        partial["api"] = ServiceHealthSnapshot(False, False, False, False)
        self.assertEqual(aggregate_platform_health(ready), "READY")
        self.assertEqual(aggregate_platform_health(partial), "PARTIAL")

    def test_control_status_includes_health_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / ".local/platform-launcher.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                (
                    '{"version":1,"services":[{"name":"api","pid":999999,'
                    '"identity":["run_ui_api.py","--serve"],"log_path":"api.log"}]}'
                ),
                encoding="utf-8",
            )
            payload = build_control_status(root)
        self.assertEqual(payload["schema_version"], "operator-lifecycle/1.1")
        self.assertEqual(payload["status"], "PARTIAL")
        row = payload["services"][0]
        self.assertIn("health", row)
        self.assertFalse(row["health"]["process_alive"])
        self.assertFalse(row["owned"])

    def test_check_update_cache_avoids_repeated_git_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = {"count": 0}

            def fake_check_update(_root: Path) -> dict[str, str]:
                calls["count"] += 1
                return {"status": "CURRENT", "detail": "fixture"}

            import tools.platform.control_service as control_service

            original = control_service.check_update
            control_service.check_update = fake_check_update  # type: ignore[assignment]
            try:
                control_service._CHECK_UPDATE_CACHE.clear()
                first = check_update_cached(root, ttl_seconds=60.0)
                second = check_update_cached(root, ttl_seconds=60.0)
            finally:
                control_service.check_update = original  # type: ignore[assignment]
                control_service._CHECK_UPDATE_CACHE.clear()
        self.assertEqual(first, second)
        self.assertEqual(calls["count"], 1)

    def test_dead_api_skips_expensive_command_line_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = root / ".local/platform-launcher.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                (
                    '{"version":1,"services":[{"name":"api","pid":999999,'
                    '"identity":["run_ui_api.py"],"log_path":"api.log"}]}'
                ),
                encoding="utf-8",
            )

            class SpySystem:
                def command_line(self, pid: int) -> str | None:
                    raise AssertionError("command_line should not run for dead pid")

                def port_is_open(self, host: str, port: int) -> bool:
                    return False

                def process_alive(self, pid: int) -> bool:
                    return False

            controller = PlatformController(root=root, system=SpySystem())  # type: ignore[arg-type]
            record = controller._read_state()[0]
            self.assertFalse(controller._is_owned(record))


if __name__ == "__main__":
    unittest.main()
