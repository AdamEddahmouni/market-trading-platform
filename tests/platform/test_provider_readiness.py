from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.provider_readiness import collect_readiness, load_env_file


class ProviderReadinessTests(unittest.TestCase):
    def test_load_env_file_reads_values_without_overwriting_explicit_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                'FRED_API_KEY=file-value\nEIA_API_KEY="quoted-value"\n# ignored\n',
                encoding="utf-8",
            )

            values = load_env_file(path)

            self.assertEqual(values["FRED_API_KEY"], "file-value")
            self.assertEqual(values["EIA_API_KEY"], "quoted-value")

    def test_report_marks_existing_credentials_and_missing_sec_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "ANTHROPIC_API_KEY=anthropic-secret\n"
                "FINRA_CLIENT_ID=finra-id\n"
                "FINRA_CLIENT_SECRET=finra-secret\n"
                "FRED_API_KEY=fred-secret\n"
                "EIA_API_KEY=eia-secret\n",
                encoding="utf-8",
            )

            report = collect_readiness({}, repository_root=root)
            checks = {row["provider"]: row for row in report["providers"]}

            self.assertEqual(report["primary_observational_provider"], "moomoo")
            self.assertEqual(checks["anthropic"]["credential_state"], "CONFIGURED")
            self.assertEqual(checks["finra"]["credential_state"], "CONFIGURED")
            self.assertEqual(checks["fred"]["credential_state"], "CONFIGURED")
            self.assertEqual(checks["eia"]["credential_state"], "CONFIGURED")
            self.assertEqual(checks["sec_edgar"]["credential_state"], "MISSING")
            self.assertFalse(report["secrets_included"])
            serialized = json.dumps(report)
            for secret in ("anthropic-secret", "finra-secret", "fred-secret", "eia-secret"):
                self.assertNotIn(secret, serialized)

    def test_report_distinguishes_moomoo_readiness_and_fixture_only_paper_transports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "IMP_LIVE_OBSERVATIONAL": "1",
                "IMP_MOOMOO_LIVE": "1",
                "IMP_TRADIER_PAPER": "1",
                "IMP_BROKER_PAPER_EXECUTION": "1",
                "IMP_TRADIER_TOKEN": "sandbox-token",
                "IMP_MOOMOO_PAPER": "1",
                "IMP_MOOMOO_PAPER_EXECUTION": "1",
                "IMP_MOOMOO_PAPER_KEY": "paper-key",
                "IMP_MOOMOO_PAPER_SECRET": "paper-secret",
            }

            report = collect_readiness(
                env,
                repository_root=root,
                probe_local=lambda host, port: (host, port) == ("127.0.0.1", 11111),
                probe_local_services=True,
            )
            checks = {row["provider"]: row for row in report["providers"]}

            self.assertEqual(checks["moomoo_observational"]["transport_state"], "REACHABLE")
            self.assertEqual(checks["ibkr_observational"]["transport_state"], "UNAVAILABLE")
            self.assertEqual(checks["tradier_paper"]["transport_state"], "FIXTURE_ONLY")
            self.assertEqual(checks["moomoo_paper"]["transport_state"], "FIXTURE_ONLY")
            serialized = json.dumps(report)
            self.assertNotIn("sandbox-token", serialized)
            self.assertNotIn("paper-secret", serialized)

    def test_report_probes_selected_tws_gateway_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = collect_readiness(
                {
                    "IMP_IBKR_LIVE": "1",
                    "IMP_IBKR_TRANSPORT": "tws",
                    "IMP_IBKR_TWS_HOST": "127.0.0.1",
                    "IMP_IBKR_TWS_PORT": "4001",
                },
                repository_root=Path(tmp),
                probe_local=lambda host, port: (host, port) == ("127.0.0.1", 4001),
                probe_local_services=True,
            )
        checks = {row["provider"]: row for row in report["providers"]}
        self.assertEqual(checks["ibkr_observational"]["transport_state"], "REACHABLE")
        self.assertIn("desktop IB Gateway", checks["ibkr_observational"]["next_action"])

    def test_report_reads_news_credentials_from_private_provider_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "IMP_NEWSAPI_LIVE=1\nIMP_FINNHUB_LIVE=true\n",
                encoding="utf-8",
            )
            private = root / ".private"
            private.mkdir()
            (private / "providers.env").write_text(
                "NEWSAPI_API_KEY=news-secret\nFINNHUB_API_KEY=finnhub-secret\n",
                encoding="utf-8",
            )

            report = collect_readiness({}, repository_root=root)

        checks = {row["provider"]: row for row in report["providers"]}
        self.assertEqual(checks["newsapi"]["credential_state"], "CONFIGURED")
        self.assertEqual(checks["newsapi"]["gate_state"], "ENABLED")
        self.assertEqual(checks["finnhub"]["credential_state"], "CONFIGURED")
        self.assertEqual(checks["finnhub"]["gate_state"], "ENABLED")
        serialized = json.dumps(report)
        self.assertNotIn("news-secret", serialized)
        self.assertNotIn("finnhub-secret", serialized)

    def test_private_provider_file_feeds_all_allowlisted_provider_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".private").mkdir()
            (root / ".private" / "providers.env").write_text(
                "IMP_TRADIER_TOKEN=sandbox-secret\n",
                encoding="utf-8",
            )

            report = collect_readiness(
                {
                    "IMP_TRADIER_PAPER": "1",
                    "IMP_BROKER_PAPER_EXECUTION": "1",
                },
                repository_root=root,
            )

        tradier = next(row for row in report["providers"] if row["provider"] == "tradier_paper")
        self.assertEqual(tradier["credential_state"], "CONFIGURED")
        self.assertNotIn("sandbox-secret", json.dumps(report))

    def test_execution_and_moomoo_gates_require_all_authority_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = collect_readiness(
                {
                    "IMP_MOOMOO_LIVE": "1",
                    "IMP_TRADIER_PAPER": "1",
                    "IMP_MOOMOO_PAPER": "1",
                },
                repository_root=Path(tmp),
            )
        checks = {row["provider"]: row for row in report["providers"]}

        self.assertEqual(checks["moomoo_observational"]["gate_state"], "DISABLED")
        self.assertEqual(checks["tradier_paper"]["gate_state"], "DISABLED")
        self.assertEqual(checks["moomoo_paper"]["gate_state"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
