"""Automated Senate eFD download (owner decision 2026-09-30) against a fake eFD. No test touches the network.

The fake serves the same shapes the live site served on 2026-09-30: a terms page with a
CSRF token and ``prohibition_agreement``, a redirect to /search/ after agreeing, a
DataTables JSON list, and report pages (the synthetic S14 fixtures).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import senate, senate_efd_sync as efd  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "senate_efd"
AGENT = "Test Operator operator@example.com"
NOW = datetime(2026, 9, 30, 16, 0, tzinfo=UTC)
HOME = ('<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="tok123">'
        '<input type="checkbox" name="prohibition_agreement" value="1"></form>')
ELECTRONIC_ID = "5f3a1c2e-0000-4000-8000-00000000a001"


def listing_row(report_id: str, kind: str = "ptr", filed: str = "01/30/2026") -> list[str]:
    return ["Jane Q", "Example", "Example, Jane (Senator)",
            f'<a href="/search/view/{kind}/{report_id}/" target="_blank">Periodic Transaction Report for {filed}</a>', filed]


class FakeEfd:
    def __init__(self, rows: list[list[str]], *, home: str = HOME, captcha_on: str | None = None,
                 pages: dict[str, str] | None = None, expire_reports: bool = False) -> None:
        self.rows, self.home, self.captcha_on = rows, home, captcha_on
        self.pages = pages or {}
        self.expire_reports = expire_reports
        self.calls: list[tuple[str, str, dict | None, dict]] = []
        self.agreed = False

    def __call__(self, method, url, form, headers):
        self.calls.append((method, url, form, headers))
        path = url.removeprefix(efd.BASE_URL)
        if self.captcha_on and path.startswith(self.captcha_on):
            return 200, url, b"<div class='g-recaptcha'>captcha</div>"
        if path == efd.HOME_PATH and method == "GET":
            return 200, url, self.home.encode()
        if path == efd.HOME_PATH and method == "POST":
            self.agreed = form.get("prohibition_agreement") == "1" and form.get("csrfmiddlewaretoken") == "tok123"
            return 200, efd.BASE_URL + (efd.SEARCH_PATH if self.agreed else efd.HOME_PATH), b"<html>search</html>"
        if not self.agreed:
            return 200, efd.BASE_URL + efd.HOME_PATH, self.home.encode()
        if path == efd.DATA_PATH:
            start, length = int(form["start"]), int(form["length"])
            body = {"draw": 1, "recordsTotal": len(self.rows), "recordsFiltered": len(self.rows),
                    "data": self.rows[start:start + length], "result": "ok"}
            return 200, url, json.dumps(body).encode()
        if path.startswith("/search/view/"):
            if self.expire_reports:
                return 200, efd.BASE_URL + efd.HOME_PATH, self.home.encode()
            report_id = path.rstrip("/").rsplit("/", 1)[-1]
            return 200, url, self.pages.get(report_id, (FIXTURES / "ptr_electronic.html").read_text(encoding="utf-8")).encode()
        return 404, url, b""


def session(fake: FakeEfd) -> efd.EfdSession:
    return efd.EfdSession(user_agent=AGENT, requester=fake, sleep=lambda _s: None, monotonic=lambda: 0.0, min_interval_s=0.0)


def attested(root: Path, *, automated: bool | None = True) -> Path:
    payload = {"accepted_by": "operator", "accepted_at": "2026-09-30T09:00:00-04:00"}
    if automated is not None:
        payload["automated_access"] = automated
    (root / senate.ATTESTATION_FILE).write_text(json.dumps(payload), encoding="utf-8")
    return root


class SyncTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = attested(Path(tmp.name))

    def run_sync(self, fake: FakeEfd, **kwargs):
        return efd.sync(self.root, user_agent=AGENT, session=session(fake), now=lambda: NOW, **kwargs)

    def test_accepts_terms_lists_and_saves_reports_the_import_reads(self):
        fake = FakeEfd([listing_row(ELECTRONIC_ID)])
        summary = self.run_sync(fake)
        self.assertEqual((summary["listed"], summary["saved"], summary["error"]), (1, 1, None))
        self.assertEqual(summary["complete_through"], "2026-09-30")
        agree = fake.calls[1]
        self.assertEqual((agree[0], agree[2]), ("POST", {"csrfmiddlewaretoken": "tok123", "prohibition_agreement": "1"}))
        listing = fake.calls[2][2]
        self.assertEqual((listing["report_types"], listing["submitted_start_date"]), ("[11]", "09/30/2024 00:00:00"))
        self.assertTrue(all(call[3]["User-Agent"] == AGENT for call in fake.calls))
        sidecar = json.loads((self.root / f"ptr-{ELECTRONIC_ID}.html.json").read_text(encoding="utf-8"))
        self.assertEqual(sidecar["source_url"], f"{efd.BASE_URL}/search/view/ptr/{ELECTRONIC_ID}/")
        self.assertEqual((sidecar["retrieved_at"], sidecar["retrieved_by"]), ("2026-09-30T16:00:00Z", "IMP_AUTOMATED_EFD_SYNC"))
        state = senate.scan_import(self.root)
        self.assertEqual((state.state, state.coverage()["parsed"]), ("READY", 1))
        self.assertEqual(state.reports[0].report_id, ELECTRONIC_ID)
        self.assertEqual(state.reports[0].retrieved_basis, "operator_sidecar.retrieved_at")

    def test_second_run_downloads_only_new_reports_from_the_overlap_window(self):
        self.run_sync(FakeEfd([listing_row(ELECTRONIC_ID)]))
        newer = "5f3a1c2e-0000-4000-8000-00000000b002"
        fake = FakeEfd([listing_row(newer), listing_row(ELECTRONIC_ID)])
        summary = self.run_sync(fake)
        self.assertEqual((summary["listed"], summary["already_present"], summary["saved"]), (2, 1, 1))
        self.assertEqual(summary["since"], "2026-09-16")                 # last complete run minus 14 days
        fetched = [call[1] for call in fake.calls if "/search/view/" in call[1]]
        self.assertEqual(fetched, [f"{efd.BASE_URL}/search/view/ptr/{newer}/"])

    def test_pages_through_the_listing_and_keeps_paper_filings_as_links(self):
        rows = [listing_row(f"5f3a1c2e-0000-4000-8000-{index:012d}") for index in range(150)]
        rows.append(listing_row("5f3a1c2e-0000-4000-8000-00000000c003", kind="paper"))
        fake = FakeEfd(rows, pages={"5f3a1c2e-0000-4000-8000-00000000c003":
                                    (FIXTURES / "paper_filing.html").read_text(encoding="utf-8")})
        summary = self.run_sync(fake, max_new=0)
        self.assertEqual(summary["listed"], 151)
        self.assertEqual([call[2]["start"] for call in fake.calls if call[1].endswith(efd.DATA_PATH)], ["0", "100"])
        self.assertIsNone(summary["complete_through"])                  # capped: the next run resumes from the same date

    def test_cap_leaves_the_rest_for_the_next_run(self):
        rows = [listing_row(f"5f3a1c2e-0000-4000-8000-{index:012d}") for index in range(3)]
        first = self.run_sync(FakeEfd(rows), max_new=2)
        self.assertEqual((first["saved"], first["complete_through"]), (2, None))
        second = self.run_sync(FakeEfd(rows), max_new=2)
        self.assertEqual((second["saved"], second["already_present"], second["complete_through"]), (1, 2, "2026-09-30"))

    def test_captcha_or_changed_form_stops_with_a_code_and_saves_nothing(self):
        for fake, code in ((FakeEfd([listing_row(ELECTRONIC_ID)], captcha_on=efd.DATA_PATH), "SENATE_EFD_CAPTCHA"),
                           (FakeEfd([], home="<html>new layout</html>"), "SENATE_EFD_FORM_CHANGED"),
                           (FakeEfd([listing_row(ELECTRONIC_ID)], expire_reports=True), "SENATE_EFD_SESSION_EXPIRED")):
            with self.subTest(code=code):
                summary = self.run_sync(fake)
                self.assertEqual((summary["error"], summary["saved"]), (code, 0))
                self.assertFalse(list(self.root.glob("*.html")))
                self.assertEqual(json.loads((self.root / efd.STATE_FILE).read_text(encoding="utf-8"))["error"], code)

    def test_nothing_is_requested_without_authorization_or_contact(self):
        fake = FakeEfd([listing_row(ELECTRONIC_ID)])
        attested(self.root, automated=None)
        with self.assertRaisesRegex(efd.SenateSyncError, "AUTOMATED_ACCESS_NOT_AUTHORIZED"):
            efd.sync(self.root, user_agent=AGENT, session=session(fake))
        (self.root / senate.ATTESTATION_FILE).unlink()
        with self.assertRaisesRegex(efd.SenateSyncError, "OPERATOR_ATTESTATION_MISSING"):
            efd.sync(self.root, user_agent=AGENT, session=session(fake))
        attested(self.root)
        with self.assertRaisesRegex(efd.SenateSyncError, "SEC_USER_AGENT_NOT_SET"):
            efd.sync(self.root, user_agent="python-urllib", session=session(fake))
        with self.assertRaisesRegex(efd.SenateSyncError, "SENATE_EFD_IMPORT_DIR_MISSING"):
            efd.sync(self.root / "missing", user_agent=AGENT, session=session(fake))
        self.assertEqual(fake.calls, [])

    def test_requests_are_throttled(self):
        waits: list[float] = []
        clock = iter(float(value) * 0.25 for value in range(100))
        fake = FakeEfd([listing_row(ELECTRONIC_ID)])
        efd.sync(self.root, user_agent=AGENT, now=lambda: NOW,
                 session=efd.EfdSession(user_agent=AGENT, requester=fake, sleep=waits.append, monotonic=lambda: next(clock)))
        self.assertEqual(len(fake.calls), 4)                             # home, agree, list, one report
        self.assertEqual(len(waits), 3)
        self.assertTrue(all(0 < wait <= efd.MIN_INTERVAL_S for wait in waits))


if __name__ == "__main__":
    unittest.main()
