"""News provider credential setup tests — values stay in private files."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

from tools.news.auth import write_provider_values  # noqa: E402


class NewsAuthTests(unittest.TestCase):
    def test_write_provider_values_updates_private_provider_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.env"
            path.write_text("EXISTING=value\nNEWSAPI_API_KEY=old\n", encoding="utf-8")

            self.assertTrue(
                write_provider_values(
                    {
                        "NEWSAPI_API_KEY": "news-secret",
                        "FINNHUB_API_KEY": "finnhub-secret",
                    },
                    path=path,
                )
            )

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "EXISTING=value\nNEWSAPI_API_KEY=news-secret\nFINNHUB_API_KEY=finnhub-secret\n",
            )


if __name__ == "__main__":
    unittest.main()
