from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.ui_api.operator_config import (
    build_config_payload,
    write_provider_values,
)


class OperatorConfigurationTests(unittest.TestCase):
    def test_provider_values_are_allowlisted_and_preserve_unrelated_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.env"
            path.write_text("OTHER_SETTING=keep\nFINVIZ_API_KEY=old\n", encoding="utf-8")

            write_provider_values("finviz", {"FINVIZ_API_KEY": "new-secret"}, path=path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "OTHER_SETTING=keep\nFINVIZ_API_KEY=new-secret\n",
            )
            with self.assertRaises(ValueError):
                write_provider_values("finviz", {"NOT_ALLOWED": "value"}, path=path)

    def test_config_payload_masks_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.env"
            path.write_text("FINVIZ_API_KEY=secret-value\n", encoding="utf-8")

            payload = build_config_payload(path=path)

            self.assertFalse(payload["secrets_included"])
            self.assertTrue(payload["providers"][0]["fields"][0]["configured"])
            self.assertNotIn("secret-value", str(payload))

    def test_config_payload_reads_repository_env_without_returning_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            private = Path(tmp) / "providers.env"
            local = Path(tmp) / ".env"
            local.write_text("ANTHROPIC_API_KEY=secret-value\n", encoding="utf-8")

            payload = build_config_payload(path=private, environment_path=local)

            anthropic = next(row for row in payload["providers"] if row["provider"] == "anthropic")
            key = next(field for field in anthropic["fields"] if field["key"] == "ANTHROPIC_API_KEY")
            self.assertTrue(key["configured"])
            self.assertNotIn("secret-value", str(payload))


if __name__ == "__main__":
    unittest.main()
