"""Final Main Screener closure — CFTC residuals on the participant service.

* The release calendar is extended from the official CFTC schedule page (cached, never blocking); a failed
  fetch keeps the vendored official tables and says so.
* A known CFTC market with no report in the 35-day window shows its last public report date from one
  cached grouped query per report family — never an unbounded scan, never per root.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_screener_s12 as s12  # noqa: E402
import test_screener_s15 as s15  # noqa: E402
from market_platform_foundation.cftc.release_schedule import SCHEDULE_URL  # noqa: E402

PAGE = (ROOT / "tests" / "fixtures" / "cftc" / "release_schedule_page_20260929.html").read_bytes()


class ScheduleRequester(s12.HouseRequester):
    def __init__(self, page=PAGE, status=200):
        super().__init__()
        self.page, self.status = page, status
        self.schedule_calls = 0

    def __call__(self, url, body, headers, timeout):
        if url == SCHEDULE_URL:
            self.schedule_calls += 1
            return self.status, self.page
        return super().__call__(url, body, headers, timeout)


def service(requester=None, last_report=s12.cot_last_report, env=s12.SEC_ENV):
    svc = s15.futures_service()
    svc._env = env.get
    if requester is not None:
        svc._http._requester = requester
    calls = []

    def counted(dataset, codes):
        calls.append((dataset, tuple(codes)))
        return last_report(dataset, codes)

    svc._cot_last_report = counted
    svc.last_report_calls = calls
    return svc


class ReleaseScheduleOnServiceTests(unittest.TestCase):
    def test_official_page_extends_the_calendar(self):
        requester = ScheduleRequester()
        svc = service(requester)
        view = svc.positioning_view(universe="FUTURES")
        schedule = view["release_schedule"]
        self.assertEqual((schedule["state"], schedule["official_years"]), ("CURRENT", [2026]))
        self.assertEqual(schedule["sources"], {"2026": "CFTC_RELEASE_SCHEDULE_PAGE"})
        svc.positioning_view(universe="FUTURES")
        svc.instrument(universe="FUTURES", instrument_id="FUT:ESZ6", lens="institutional")
        self.assertEqual(requester.schedule_calls, 1)            # cached for its TTL, shared by view and panel
        es = next(row for row in view["groups"][0]["rows"] if row["root"] == "ES")
        self.assertEqual(es["publication_basis"], "CFTC_OFFICIAL_SCHEDULE")

    def test_a_failed_page_keeps_the_vendored_official_table(self):
        view = service(ScheduleRequester(status=503)).positioning_view(universe="FUTURES")
        schedule = view["release_schedule"]
        self.assertEqual((schedule["state"], schedule["official_years"]), ("SOURCE_ERROR", [2026]))
        self.assertEqual(schedule["sources"], {"2026": "VENDORED_OFFICIAL_SNAPSHOT"})
        self.assertEqual(view["state"], "PUBLICATION_CURRENT")

    def test_an_unparseable_page_fails_closed(self):
        view = service(ScheduleRequester(page=b"<html>maintenance</html>")).positioning_view(universe="FUTURES")
        self.assertEqual((view["release_schedule"]["state"], view["release_schedule"]["sources"]),
                         ("SOURCE_ERROR", {"2026": "VENDORED_OFFICIAL_SNAPSHOT"}))

    def test_no_request_with_live_gates_off(self):
        requester = ScheduleRequester()
        svc = service(requester, env={})
        view = svc.positioning_view(universe="FUTURES")
        self.assertEqual(view["release_schedule"]["state"], "VENDORED_ONLY")
        self.assertEqual((requester.schedule_calls, svc.last_report_calls), (0, []))


class LastReportTests(unittest.TestCase):
    def test_known_market_without_recent_report_shows_its_last_report(self):
        svc = service()
        view = svc.positioning_view(universe="FUTURES")
        self.assertEqual(view["coverage"]["mapped_without_report"], ["ZO"])
        self.assertEqual(view["coverage"]["recent_window_days"], 35)
        detail = view["coverage"]["mapped_without_report_detail"]
        self.assertEqual([item["root"] for item in detail], ["ZO"])
        last = detail[0]["last_report"]
        self.assertEqual((last["state"], last["report_date"], last["cftc_contract_market_code"]),
                         ("LAST_REPORT_FOUND", "2026-07-14", "004603"))
        self.assertEqual((last["publication_time"], last["publication_basis"]),
                         ("2026-07-17T19:30:00Z", "CFTC_OFFICIAL_SCHEDULE"))
        panel = s15.panel(svc, "FUT:ZOZ6")["sections"]["futures_positioning"]
        self.assertEqual((panel["state"], panel["reason"]), ("NO_DISCLOSURES", "KNOWN_MARKET_NOT_IN_RECENT_RELEASES"))
        self.assertEqual(panel["last_report"]["report_date"], "2026-07-14")
        self.assertNotIn("report", panel)                         # no positions are shown for an old report
        # One grouped query for the Disaggregated family, shared by the view and the panel.
        self.assertEqual(len(svc.last_report_calls), 1)
        self.assertIn("004603", svc.last_report_calls[0][1])

    def test_mapped_roots_with_recent_reports_need_no_lookup(self):
        svc = service()
        s15.panel(svc, "FUT:ESZ6")
        s15.panel(svc, "FUT:VXMV6")
        self.assertEqual(svc.last_report_calls, [])

    def test_market_with_no_rows_at_all_is_not_invented(self):
        svc = service(last_report=lambda dataset, codes: [])
        last = svc.positioning_view(universe="FUTURES")["coverage"]["mapped_without_report_detail"][0]["last_report"]
        self.assertEqual((last["state"], last["reason"], last["report_date"]),
                         ("NO_REPORT_FOUND", "NO_ROWS_FOR_MARKET_CODE", None))

    def test_a_report_not_yet_public_is_withheld(self):
        svc = service(last_report=lambda dataset, codes: [{"cftc_contract_market_code": "004603",
                                                           "last_report": "2026-09-29T00:00:00.000"}])
        last = svc.positioning_view(universe="FUTURES")["coverage"]["mapped_without_report_detail"][0]["last_report"]
        self.assertEqual((last["state"], last["reason"], last["report_date"]), ("NO_REPORT_FOUND", "NOT_YET_PUBLIC", None))

    def test_lookup_failure_is_a_source_error_not_absence(self):
        def failing(dataset, codes):
            raise OSError("CFTC_HTTP_503")

        svc = service(last_report=failing)
        panel = s15.panel(svc, "FUT:ZOZ6")["sections"]["futures_positioning"]
        self.assertEqual(panel["state"], "NO_DISCLOSURES")
        self.assertEqual((panel["last_report"]["state"], panel["last_report"]["report_date"]), ("SOURCE_ERROR", None))


if __name__ == "__main__":
    unittest.main()
