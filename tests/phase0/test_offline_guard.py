import socket
import subprocess
import unittest
import ast
from pathlib import Path

from market_platform_foundation.errors import OfflineBoundaryViolation
from market_platform_foundation.offline_guard import install_guard


class OfflineGuardTests(unittest.TestCase):
    def setUp(self):
        self.log = []
        install_guard(self.log)

    def test_ipv4_ipv6_loopback_and_dns_are_denied(self):
        for action in (
            lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM),
            lambda: socket.getaddrinfo("localhost", 1),
        ):
            with self.assertRaises(OfflineBoundaryViolation):
                action()

    def test_process_spawn_is_denied(self):
        with self.assertRaises(OfflineBoundaryViolation):
            subprocess.Popen(["python", "--version"])

    def test_phase0_tools_import_only_guard_at_module_scope(self):
        for path in sorted(Path("tools/phase0").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            subject_imports = []
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                    "market_platform_foundation"
                ):
                    subject_imports.append(node.module)
            self.assertEqual(
                subject_imports,
                ["market_platform_foundation.offline_guard"],
                path.as_posix(),
            )

    def test_install_is_idempotent_and_logs_sanitized_reason(self):
        install_guard(self.log)
        with self.assertRaises(OfflineBoundaryViolation):
            socket.gethostbyname("localhost")
        self.assertEqual(
            set(self.log[-1]), {"event_category", "reason_code"}
        )
