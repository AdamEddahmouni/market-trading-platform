"""Optional OpenD extra is an IMP env command, not a second venv."""

from __future__ import annotations

import unittest

try:
    from tools.imp import build_parser
except ModuleNotFoundError as exc:
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class OpenDExtraEnvCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"imp router is missing: {IMPORT_ERROR}")

    def test_env_install_opend_is_documented_optional_extra(self) -> None:
        args = build_parser().parse_args(["env", "install-opend"])
        self.assertEqual(args.group, "env")
        self.assertEqual(args.env_action, "install-opend")
