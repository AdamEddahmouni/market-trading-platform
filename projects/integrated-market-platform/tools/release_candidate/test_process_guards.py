"""Offline regression of release apply/backup/migration process guards."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import apply_release
import backup_state


class ProcessGuards(unittest.TestCase):
    def check_modules(self, output, assertion, returncode=0, stderr=''):
        for module, method, target in (
            (apply_release, apply_release.running_from, Path(r'C:\release\projects\app')),
            (backup_state, backup_state.running_near, Path(r'C:\release\state\imp-state.sqlite3')),
        ):
            with self.subTest(module=module.__name__), patch.object(module.os, 'getpid', return_value=123), patch.object(
                module.subprocess, 'run', return_value=SimpleNamespace(stdout=output, returncode=returncode, stderr=stderr)
            ):
                assertion(method, target)

    def assert_refuses(self, method, target):
        with self.assertRaisesRegex(RuntimeError, 'PROCESS_INVENTORY_UNAVAILABLE'):
            method(target)

    def test_excludes_only_the_current_process(self):
        def assertion(method, target):
            self.assertEqual(len(method(target)), 1)
            self.assertIn('serve.py', method(target)[0])
        self.check_modules('123|python C:\\release\\projects\\app\\tool.py\n456|python C:\\release\\projects\\app\\serve.py\n', assertion)

    def test_empty_successful_inventory_is_clear(self):
        self.check_modules('', lambda method, target: self.assertEqual(method(target), []))

    def test_inventory_failure_refuses_migration_or_apply(self):
        self.check_modules('', self.assert_refuses, returncode=1, stderr='Access denied')

    def test_powershell_nonterminating_error_refuses(self):
        self.check_modules('', self.assert_refuses, stderr='Get-CimInstance: Access denied')

    def test_malformed_inventory_refuses(self):
        self.check_modules('not a process row', self.assert_refuses)

    def test_unreadable_command_line_refuses(self):
        self.check_modules('456|\n', self.assert_refuses)

    def test_forward_slash_application_path_is_detected(self):
        self.check_modules('456|python C:/release/projects/app/serve.py\n', lambda method, target: self.assertEqual(len(method(target)), 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
