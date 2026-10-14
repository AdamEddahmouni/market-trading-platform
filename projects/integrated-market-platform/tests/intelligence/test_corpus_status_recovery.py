"""Status-file failure recovery, with no providers or non-disposable writes."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.ui_api import paper_forecast_corpus as corpus


class OfflineRuntime:
    observation_ingress_router = None

    def attach_observation_ingress(self, router):
        self.observation_ingress_router = router

    def subscribe(self, *, instrument_id, capabilities, consumer_id):
        return [dict(accepted=False, reason="OFFLINE_TEST") for _ in capabilities]


class GridStop:
    """Run real recorder ticks on distinct grid points without wall-clock waits."""

    def __init__(self, clock, ticks=4):
        self.clock = clock
        self.ticks = ticks
        self.cycles = 0

    def wait(self, seconds):
        self.cycles += 1
        self.clock["now"] += 30_000_000_000
        return self.cycles > self.ticks


class CorpusStatusRecoveryTests(unittest.TestCase):
    def service(self, directory):
        clock = {"now": 1_700_000_010_000_000_000}
        runtime = OfflineRuntime()
        service = corpus.PaperForecastCorpusService(
            directory=Path(directory), symbols=["AAPL"], runtime_getter=lambda: runtime,
            clock=lambda: clock["now"],
        )
        service.recorder.session_open = lambda _at: True
        return service, clock

    @unittest.skipUnless(os.name == "nt", "Windows reader sharing regression")
    def test_real_windows_reader_lock_can_release_between_bounded_retries(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            destination = directory / "status.json"
            destination.write_text('{"at":"previous-success"}', encoding="utf-8")
            # Permit concurrent read/write but deny delete sharing: Windows atomic replacement fails.
            handle = kernel.CreateFileW(str(destination), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value, ctypes.get_last_error())

            def release_reader(_delay):
                nonlocal handle
                if handle is not None:
                    self.assertTrue(kernel.CloseHandle(handle))
                    handle = None

            try:
                service, _clock = self.service(directory)
                with patch.object(corpus.time, "sleep", side_effect=release_reader):
                    status = service.write_status()
                self.assertIsNone(handle, "a failed first replacement must reach the bounded retry")
                self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), status)
                self.assertEqual(service.last_status_written_at, status["at"])
            finally:
                if handle is not None:
                    kernel.CloseHandle(handle)

    def test_denial_after_success_retains_the_last_successful_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _clock = self.service(tmp)
            first = service.write_status()
            original = (Path(tmp) / "status.json").read_bytes()
            with patch.object(corpus.os, "replace", side_effect=PermissionError(5, "status locked")), \
                    patch.object(corpus.time, "sleep"), self.assertLogs(corpus.__name__, level="WARNING"):
                failed = service.write_status()
            self.assertIsNone(failed)
            self.assertEqual(service.last_status_written_at, first["at"])
            self.assertEqual((Path(tmp) / "status.json").read_bytes(), original)
            self.assertIn("PermissionError", service.status_write_error)

    def test_transient_reader_lock_retries_atomic_replace_and_preserves_raw_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw = directory / "feature-corpus-2023-11-14.jsonl"
            original = b'{"kind":"original-evidence"}\n'
            raw.write_bytes(original)
            service, _clock = self.service(directory)
            service.state = "RUNNING"
            replace = os.replace
            attempts = []

            def locked_twice(source, destination):
                attempts.append(destination)
                if len(attempts) <= 2:
                    raise PermissionError(5, "status reader denies replacement")
                return replace(source, destination)

            with patch.object(corpus.os, "replace", side_effect=locked_twice), patch.object(corpus.time, "sleep"):
                status = service.write_status()

            persisted = json.loads((directory / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status, persisted)
            self.assertEqual(service.last_status_written_at, persisted["at"])
            self.assertIsNone(service.status_write_error)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(raw.read_bytes(), original)

    def test_persistent_status_denial_keeps_real_recording_and_never_advances_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            stale = b'{"state":"RUNNING","at":"previous-success"}'
            (directory / "status.json").write_bytes(stale)
            raw = directory / "feature-corpus-2023-11-14.jsonl"
            original = b'{"kind":"original-evidence"}\n'
            raw.write_bytes(original)
            service, clock = self.service(directory)
            stop = GridStop(clock)
            service._stop = stop
            attempts = []

            def denied(source, destination):
                attempts.append(destination)
                raise PermissionError(5, "status reader denies replacement")

            with patch.object(corpus.os, "replace", side_effect=denied), patch.object(corpus.time, "sleep"), \
                    patch.object(corpus.time, "monotonic", side_effect=lambda: 100 + stop.cycles), \
                    self.assertLogs(corpus.__name__, level="WARNING") as warnings:
                service.run()

            self.assertEqual(service.state, "RUNNING")
            self.assertEqual(service.recorder.status["decisions"], 4)
            self.assertEqual(len(attempts), 3, "one bounded batch, not retries on every recording tick")
            self.assertIsNone(service.last_status_written_at)
            self.assertIn("PermissionError", service.status_write_error)
            self.assertIn("PermissionError", "\n".join(warnings.output))
            self.assertEqual((directory / "status.json").read_bytes(), stale)
            self.assertTrue(raw.read_bytes().startswith(original))
            rows = raw.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 5)
            self.assertTrue(all(json.loads(row)["reason"] == "NO_REFERENCE_QUOTE" for row in rows[1:]))

    def test_next_status_interval_recovers_after_denial_without_losing_recorder_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            service, clock = self.service(directory)
            stop = GridStop(clock, ticks=2)
            service._stop = stop
            replace = os.replace
            attempts = []

            def denied_first_batch(source, destination):
                attempts.append(destination)
                if len(attempts) <= 3:
                    raise PermissionError(5, "temporary persistent lock")
                return replace(source, destination)

            with patch.object(corpus.os, "replace", side_effect=denied_first_batch), patch.object(corpus.time, "sleep"), \
                    patch.object(corpus.time, "monotonic", side_effect=lambda: 100 + stop.cycles * 10), \
                    self.assertLogs(corpus.__name__, level="WARNING"):
                service.run()

            persisted = json.loads((directory / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["recorder"]["decisions"], 2)
            self.assertEqual(service.last_status_written_at, persisted["at"])
            self.assertIsNone(service.status_write_error)
            self.assertEqual(len(attempts), 4)
            self.assertEqual(len(next(directory.glob("*.jsonl")).read_text(encoding="utf-8").splitlines()), 2)

    def test_failed_service_cannot_crash_again_while_reporting_status_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _clock = self.service(tmp)
            service.runtime_getter = lambda: (_ for _ in ()).throw(ValueError("runtime attach failed"))
            with patch.object(corpus.os, "replace", side_effect=PermissionError(5, "status locked")), \
                    patch.object(corpus.time, "sleep"), self.assertLogs(corpus.__name__, level="WARNING"):
                service.run()
            self.assertEqual(service.state, "FAILED")
            self.assertEqual(service.error, "ValueError:runtime attach failed")
            self.assertIn("PermissionError", service.status_write_error)
            self.assertIsNone(service.last_status_written_at)

    def test_status_directory_failure_does_not_abort_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, clock = self.service(tmp)
            stop = GridStop(clock, ticks=2)
            service._stop = stop
            # A real filesystem failure confined to the status path.
            # The recorder retains its original disposable directory.
            service.directory = Path(tmp) / "blocked-status-directory"
            service.directory.write_bytes(b"existing file must survive")

            with patch.object(corpus.time, "monotonic", side_effect=lambda: 100 + stop.cycles), \
                    self.assertLogs(corpus.__name__, level="WARNING"):
                service.run()
            self.assertEqual(service.recorder.status["decisions"], 2)
            self.assertIn("FileExistsError", service.status_write_error)
            self.assertIsNone(service.last_status_written_at)
            self.assertEqual(service.directory.read_bytes(), b"existing file must survive")


if __name__ == "__main__":
    unittest.main()
