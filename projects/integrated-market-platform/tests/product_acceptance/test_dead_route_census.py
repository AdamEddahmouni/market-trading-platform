"""G15 BL-0803 — dead-route census verifier."""

from __future__ import annotations

import unittest
from pathlib import Path

from tools.e2e.dead_route_census import build_census, write_census_report

ROOT = Path(__file__).resolve().parents[2]


class DeadRouteCensusTests(unittest.TestCase):
    def test_census_covers_legacy_paper_routes(self) -> None:
        rows = build_census(ROOT)
        routes = {row.route for row in rows}
        self.assertIn("/paper/account", routes)
        self.assertIn("/paper/positions", routes)
        self.assertIn("/capabilities", routes)

    def test_capabilities_classified_archive_first_when_no_frontend_caller(self) -> None:
        rows = {row.route: row for row in build_census(ROOT)}
        capabilities = rows["/capabilities"]
        if capabilities.frontend_callers == 0:
            self.assertIn("ARCHIVE_FIRST", capabilities.disposition)

    def test_census_report_writes_artifact(self) -> None:
        output = ROOT / ".local" / "e2e" / "dead-route-census.json"
        payload = write_census_report(output, ROOT)
        self.assertEqual(payload["report_type"], "g15_dead_route_census")
        self.assertTrue(output.is_file())
