from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.of01.cli import main
from tests.of01.support import DisposableAuthority
from tests.of01.test_readers_stream import _register_run_envelope


class TestCLI(unittest.TestCase):
    def test_status_json_output(self) -> None:
        auth = DisposableAuthority()
        try:
            writer = auth.open_writer()
            writer.submit(_register_run_envelope(auth.authority_id))
            writer.close()
            exit_code = main(
                [
                    "--db-path",
                    str(auth.db_path),
                    "--authority-id",
                    auth.authority_id,
                    "--json",
                    "status",
                ]
            )
            self.assertEqual(exit_code, 0)
        finally:
            auth.close()

    def test_metadata_command_parses(self) -> None:
        auth = DisposableAuthority()
        try:
            exit_code = main(
                [
                    "--db-path",
                    str(auth.db_path),
                    "--authority-id",
                    auth.authority_id,
                    "--json",
                    "metadata",
                ]
            )
            self.assertEqual(exit_code, 0)
        finally:
            auth.close()


if __name__ == "__main__":
    unittest.main()
