"""S16 Fixed Income coverage: N-PORT fund-held catalog, Treasury market data, observed analytics, BONDS query.

Every N-PORT data set here is synthetic, written in the SEC Form N-PORT data-set
layout (SUBMISSION / FUND_REPORTED_INFO / FUND_REPORTED_HOLDING / IDENTIFIERS /
DEBT_SECURITY TSVs). Treasury terms and curves are the S9 official excerpts.
Feed payloads are shaped like the published APIs. No test touches the network.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.fixed_income import analytics  # noqa: E402
from market_platform_foundation.fixed_income import nport_catalog as nc  # noqa: E402
from market_platform_foundation.fixed_income.finra_fixed_income import load_market_breadth  # noqa: E402
from market_platform_foundation.fixed_income.identifiers import (  # noqa: E402
    cusip_valid, isin_check_digit, isin_from_cusip, isin_valid,
)
from market_platform_foundation.fixed_income.nyfed import (  # noqa: E402
    OperationPrice, load_reference_rates, load_soma, parse_operations,
)
from market_platform_foundation.fixed_income.observed import observed_measures  # noqa: E402
from market_platform_foundation.fixed_income.openfigi import OpenFigi  # noqa: E402
from market_platform_foundation.fixed_income.treasury_market import (  # noqa: E402
    TreasuryMarketData, fetch_market_data, latest_prices, load_buyback_prices, load_frn_index, load_tips_index,
)
from market_platform_foundation.fixed_income.treasury_rates import (  # noqa: E402
    NOMINAL, CurvePoint, CurvePublication, interpolate_par,
)
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.sec_edgar.thirteen_f_index import SourceIntegrityError  # noqa: E402
from market_platform_foundation.ui_api.screener_bonds import BondScreener  # noqa: E402
from market_platform_foundation.ui_api.screener_bonds_fund import FundHeldRow  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import validate_filters  # noqa: E402
from market_platform_foundation.ui_api.screener_query import field_capabilities, parse_query  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import BONDS, UNIVERSES, US_ETFS  # noqa: E402
from market_platform_foundation.xa01.enums import InstrumentKind, XaAssetClass  # noqa: E402
from market_platform_foundation.xa01.identity import bond_identity_key, derive_canonical_id  # noqa: E402
from tests.platform.test_screener_s9 import TODAY, Clock, fixture_catalog, fixture_rates  # noqa: E402


def cusip(body: str) -> str:
    """A CUSIP with its computed check digit (modulus 10, double-add-double)."""

    total = 0
    for index, char in enumerate(body):
        value = int(char) if char.isdigit() else ord(char) - 55
        if index % 2:
            value *= 2
        total += value // 10 + value % 10
    code = body + str((10 - total % 10) % 10)
    assert cusip_valid(code), code
    return code


CORP, MUNI, AGENCY, MBS = cusip("594918BW"), cusip("13063DAB"), cusip("3133EPXY"), cusip("3140XABC")
FLOATER, AMBIGUOUS, MATURED, NON_USD = cusip("12345ABC"), cusip("88160RAB"), cusip("00206RAB"), cusip("45950KCZ")
TBA, UST = cusip("01F05262"), "912828YK0"
CORP_ISIN = isin_from_cusip(CORP)

SUB = "ACCESSION_NUMBER\tFILING_DATE\tSUB_TYPE\tREPORT_DATE"
INFO = "ACCESSION_NUMBER\tSERIES_ID"
HOLD = ("ACCESSION_NUMBER\tHOLDING_ID\tISSUER_NAME\tISSUER_LEI\tISSUER_TITLE\tISSUER_CUSIP\tBALANCE\tUNIT\tCURRENCY_CODE\t"
        "CURRENCY_VALUE\tASSET_CAT\tISSUER_TYPE\tINVESTMENT_COUNTRY")
IDENT = "HOLDING_ID\tIDENTIFIER_ISIN"
DEBT = ("HOLDING_ID\tMATURITY_DATE\tCOUPON_TYPE\tANNUALIZED_RATE\tIS_DEFAULT\tIS_ANY_PORTION_INTEREST_PAID\t"
        "IS_CONVTIBLE_MANDATORY\tIS_CONVTIBLE_CONTINGENT")
LEI = "INR2EJN1ERAN0W5ZP974"


def tsv(header: str, rows: list[tuple]) -> str:
    return header + "\n" + "".join("\t".join(str(value) for value in row) + "\n" for row in rows)


def holding(acc, hid, name, title, code, balance, value, asset="DBT", issuer_type="CORP", currency="USD", country="US",
            lei=LEI, unit="PA"):
    return (acc, hid, name, lei, title, code, balance, unit, currency, value, asset, issuer_type, country)


def debt(hid, maturity, coupon_type="Fixed", rate="", default="N", pik="N", mandatory="N", contingent="N"):
    return (hid, maturity, coupon_type, rate, default, pik, mandatory, contingent)


def nport_zip(*, drop: str | None = None, bad_column: bool = False) -> bytes:
    submissions = [("F1", "29-MAY-2026", "NPORT-P", "31-MAR-2026"), ("F2", "28-MAY-2026", "NPORT-P", "31-MAR-2026"),
                   ("F3", "15-JUN-2026", "NPORT-P/A", "31-MAR-2026"), ("F4", "25-JUN-2026", "NPORT-P", "30-APR-2026")]
    info = [("F1", "S000000001"), ("F2", "S000000002"), ("F3", "S000000002"), ("F4", "S000000003")]
    holdings = [
        holding("F1", "H1", "Microsoft Corp", "MICROSOFT CORP 3.5% 02/06/2030", CORP, 1_000_000, 980_000),
        holding("F2", "H2", "Microsoft Corp", "MICROSOFT CORP", CORP, 1_000_000, 500_000),  # superseded by F3
        holding("F3", "H3", "Microsoft Corp", "MICROSOFT CORP", CORP, 2_000_000, 1_990_000),
        holding("F4", "H4", "Microsoft Corp", "MICROSOFT CORP", CORP, 500_000, 495_000),
        holding("F1", "H5", "State of California", "CALIFORNIA ST 5.00% 2035", MUNI, 250_000, 260_000, issuer_type="MUN", lei="N/A"),
        holding("F1", "H6", "Federal Farm Credit Banks", "FFCB 4.25 2031", AGENCY, 300_000, 301_000, issuer_type="USGSE"),
        holding("F3", "H7", "Fannie Mae Pool", "FNMA POOL MA5000", MBS, 400_000, 396_000, asset="ABS-MBS", issuer_type="USGSE"),
        holding("F1", "H8", "Acme Floating Co", "ACME FRN 2029", FLOATER, 100_000, 100_500),
        holding("F1", "H9", "Fannie Mae TBA", "UMBS 30YR", TBA, 5_000_000, 4_900_000, asset="ABS-MBS", issuer_type="USGSE"),
        holding("F1", "H10", "U.S. Treasury", "UST 2.25 2027", UST, 1_000_000, 990_000, issuer_type="UST"),
        holding("F1", "H11", "Private placement", "PP NOTE", "999999999", 100, 100),
        holding("F1", "H12", "Euro Issuer", "EUR NOTE", NON_USD, 100_000, 99_000, currency="EUR", country="DE"),
        holding("F1", "H13", "Tesla Inc", "TESLA NOTE", AMBIGUOUS, 100_000, 97_000),
        holding("F1", "H14", "AT&T Inc", "AT&T 1.7 2026", MATURED, 100_000, 99_900),
        holding("F1", "H15", "Republic of Chile", "CHILE 3.1 2041", cusip("168863DV"), 100_000, 80_000, issuer_type="NUSS",
                country="CL"),
        holding("F1", "H16", "Apple Inc", "APPLE COMMON", "037833100", 10, 2_300, asset="EC"),  # equity: never a bond row
    ]
    identifiers = [("H1", CORP_ISIN), ("H3", CORP_ISIN)]
    debts = [
        debt("H1", "06-FEB-2030", rate="3.5"), debt("H2", "06-FEB-2030", rate="9.99"), debt("H3", "06-FEB-2030", rate="3.5"),
        debt("H4", "06-FEB-2030", rate="0.035"),  # fraction-encoded; another filing corroborates 3.5
        debt("H5", "01-AUG-2035", rate="0.05"),  # single filer; the title states 5.00%
        debt("H6", "15-MAR-2031", rate="4.25"), debt("H7", "01-JUN-2054", rate="5.5"),
        debt("H8", "15-MAY-2029", coupon_type="Floating", rate="6.1"), debt("H9", "01-OCT-2056", rate="5.5"),
        debt("H10", "15-NOV-2027", rate="2.25"), debt("H11", "01-JAN-2030", rate="4"), debt("H12", "01-JAN-2030", rate="2"),
        debt("H13", "01-JAN-2031", rate="0.07"),  # single filer, no title percentage: ambiguous
        debt("H14", "01-JUN-2026", rate="1.7"), debt("H15", "27-JAN-2041", rate="3.1"),
    ]
    tables = {"SUBMISSION.tsv": tsv(SUB, submissions), "FUND_REPORTED_INFO.tsv": tsv(INFO, info),
              "FUND_REPORTED_HOLDING.tsv": tsv(HOLD.replace("ASSET_CAT", "ASSET_KIND") if bad_column else HOLD, holdings),
              "IDENTIFIERS.tsv": tsv(IDENT, identifiers), "DEBT_SECURITY.tsv": tsv(DEBT, debts)}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in tables.items():
            if name != drop:
                archive.writestr(name, text)
    return buffer.getvalue()


NAME = "2026q2_nport.zip"
URL = nc.IMPORT_URL_BASE + NAME


def listing(*names: str) -> str:
    links = "".join(f'<a href="/files/dera/data/form-n-port-data-sets/{name}">{name}</a>' for name in names)
    return f'<html><body>{links}<a href="https://example.com/2026q3_nport.zip">mirror</a></body></html>'


class WallClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 27, 12, tzinfo=UTC).timestamp()

    def __call__(self) -> float:
        return self.value


def build_root(root: Path, payload: bytes | None = None) -> dict:
    store = nc.NportStore(root, clock=WallClock())
    lifecycle = nc.NportLifecycle(store, fetch_listing=lambda: listing(NAME),
                                  download=lambda url, dest: dest.write_bytes(payload or nport_zip()))
    return lifecycle.refresh()


# ------------------------------------------------------------------ identifiers
class IdentifierTests(unittest.TestCase):
    def test_isin_check_digits_match_published_isins(self):
        self.assertEqual(isin_from_cusip("037833100"), "US0378331005")  # Apple
        self.assertEqual(isin_from_cusip("912828YK0"), "US912828YK04")  # a Treasury note
        self.assertTrue(isin_valid("US0378331005"))
        self.assertFalse(isin_valid("US0378331006"))
        self.assertEqual(isin_check_digit("US037833100"), 5)

    def test_invalid_or_private_cusips_never_yield_an_isin(self):
        self.assertIsNone(isin_from_cusip("037833101"))  # bad check digit
        self.assertIsNone(isin_from_cusip("999999999"))
        self.assertIsNone(isin_from_cusip("12345*AB1"))
        self.assertIsNone(isin_from_cusip("037833100", "U1"))


# ------------------------------------------------------------------ reconciliation
class ReconcileTests(unittest.TestCase):
    def test_categories_from_asset_and_issuer_type(self):
        self.assertEqual(nc.line_category("DBT", "CORP")[0], "Corporate")
        self.assertEqual(nc.line_category("DBT", "USGSE")[:2], ("Agency", "Agency debt (GSE)"))
        self.assertEqual(nc.line_category("DBT", "MUN")[0], "Municipal")
        self.assertEqual(nc.line_category("ABS-MBS", "USGA")[:2], ("Securitized", "Agency MBS"))
        self.assertEqual(nc.line_category("ABS-MBS", "CORP")[:2], ("Securitized", "Non-agency MBS"))
        self.assertEqual(nc.line_category("ABS-CBDO", "CORP")[1], "CDO / CLO")
        self.assertEqual(nc.line_category("DBT", "UST")[2], "TREASURY_FROM_TREASURY_CATALOG")
        self.assertEqual(nc.line_category("DBT", "NUSS")[2], "EXCLUDED_ISSUER_TYPE")
        self.assertEqual(nc.line_category("LON", "CORP")[2], "EXCLUDED_ASSET_CATEGORY")

    def test_tba_forwards_are_not_securities(self):
        self.assertTrue(nc.is_tba("01F052626", "UMBS 30YR"))
        self.assertTrue(nc.is_tba("21H050621", "GNMA II"))
        self.assertTrue(nc.is_tba(MBS, "FNMA 5.5 TBA OCT"))
        self.assertFalse(nc.is_tba(MBS, "FNMA POOL MA5000"))

    def test_coupon_fold_needs_corroboration(self):
        self.assertEqual(nc.reconcile_coupon([3.5, 3.5, 0.035]), (3.5, "CONSENSUS"))
        self.assertEqual(nc.reconcile_coupon([0.08], ["GNMA 8.00% 6/30"]), (8.0, "CONSENSUS"))
        self.assertEqual(nc.reconcile_coupon([0.08], ["GNMA POOL"]), (None, "AMBIGUOUS_RATE_ENCODING"))
        self.assertEqual(nc.reconcile_coupon([4.0, 5.0]), (None, "COUPON_CONFLICT"))
        self.assertEqual(nc.reconcile_coupon([4.125, 4.125, 4.125, 4.13]), (4.125, "CONSENSUS"))
        self.assertEqual(nc.reconcile_coupon([]), (None, "NO_FIXED_RATE_REPORTED"))

    def line(self, **overrides) -> nc.Line:
        base = dict(category="Corporate", subtype="Corporate debt", maturity="2030-02-06", coupon_type="Fixed", rate=3.5,
                    in_default=False, pik=False, convertible=False, currency="USD", unit="PA", balance=100.0, value=99.0,
                    report_date="2026-03-31", filing_date="2026-05-29", series="S1", issuer="X", title="X", lei="",
                    isin="", country="US")
        return nc.Line(**{**base, **overrides})

    def test_conflicts_reject_the_cusip(self):
        self.assertEqual(nc.reconcile(CORP, [self.line(currency="EUR")]), (None, "NON_USD"))
        self.assertEqual(nc.reconcile(CORP, [self.line(), self.line(category="Municipal", series="S2")])[1], "CATEGORY_CONFLICT")
        self.assertEqual(nc.reconcile(CORP, [self.line(), self.line(maturity="2031-02-06", series="S2")])[1], "MATURITY_CONFLICT")
        self.assertEqual(nc.reconcile(CORP, [self.line(maturity=None)])[1], "MISSING_MATURITY")

    def test_record_uses_the_latest_report_for_value_and_never_stores_a_floating_rate_as_coupon(self):
        record, _ = nc.reconcile(CORP, [self.line(value=90.0), self.line(report_date="2026-04-30", value=101.0, series="S2")])
        self.assertEqual((record["value_pct_par"], record["fund_count"], record["report_date_max"]), (101.0, 2, "2026-04-30"))
        floating, _ = nc.reconcile(FLOATER, [self.line(coupon_type="Floating", rate=6.1)])
        self.assertEqual((floating["coupon"], floating["coupon_state"], floating["reported_rate"]), (None, "NOT_FIXED", 6.1))
        implausible, _ = nc.reconcile(CORP, [self.line(value=1000.0)])
        self.assertIsNone(implausible["value_pct_par"])  # a unit error is never shown

    def test_isin_reported_else_derived_only_for_us(self):
        record, _ = nc.reconcile(CORP, [self.line(isin=CORP_ISIN)])
        self.assertEqual((record["isin"], record["isin_source"]), (CORP_ISIN, "REPORTED"))
        record, _ = nc.reconcile(CORP, [self.line()])
        self.assertEqual((record["isin"], record["isin_source"]), (CORP_ISIN, "DERIVED"))
        record, _ = nc.reconcile(CORP, [self.line(country="CA")])
        self.assertEqual((record["isin"], record["isin_source"]), (None, None))

    def test_letter_prefixed_identifiers_need_a_reported_isin(self):
        # Fund administrators' internal IDs carry a CUSIP-style check digit; only an embedding ISIN makes one a CINS.
        internal = cusip("ACI0LWJJ")
        self.assertTrue(cusip_valid(internal))
        self.assertEqual(nc.reconcile(internal, [self.line()]), (None, "UNCORROBORATED_IDENTIFIER"))
        self.assertEqual(nc.reconcile(internal, [self.line(isin="US" + CORP + "0")])[1], "UNCORROBORATED_IDENTIFIER")
        cins = cusip("G0000000")
        record, _ = nc.reconcile(cins, [self.line(isin=isin_from_cusip(cins, "US"), country="KY")])
        self.assertEqual((record["isin"], record["isin_source"]), (isin_from_cusip(cins, "US"), "REPORTED"))

    def test_identity_is_the_xa01_bond_id(self):
        record, _ = nc.reconcile(CORP, [self.line()])
        self.assertEqual(record["instrument_id"], derive_canonical_id(
            instrument_kind=InstrumentKind.BOND, asset_class=XaAssetClass.BOND, identity_key=bond_identity_key(security_id=CORP)))


# ------------------------------------------------------------------ build
class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def build(self, payload: bytes | None = None) -> tuple[dict, nc.NportCatalog]:
        source = self.dir / NAME
        source.write_bytes(payload or nport_zip())
        info = nc.build_catalog_db([source], self.dir / "index.sqlite", meta={"generation": "g1"})
        return info, nc.NportCatalog.load(self.dir / "index.sqlite")

    def test_build_reconciles_filters_and_counts_every_exclusion(self):
        info, catalog = self.build()
        by_cusip = {record.cusip: record for record in catalog.records}
        self.assertEqual(set(by_cusip), {CORP, MUNI, AGENCY, MBS, FLOATER, AMBIGUOUS, MATURED})
        self.assertEqual(info["by_category"], {"Corporate": 4, "Agency": 1, "Municipal": 1, "Securitized": 1})
        self.assertEqual(info["superseded_filings"], 1)
        for reason in ("TBA_FORWARD_LINES", "TREASURY_FROM_TREASURY_CATALOG_LINES", "INVALID_CUSIP_LINES",
                       "EXCLUDED_ISSUER_TYPE_LINES", "NON_USD"):
            self.assertEqual(info["rejections"][reason], 1, reason)
        self.assertFalse(list(self.dir.glob("*.staging")))  # staging never survives a build
        self.assertNotIn("037833100", by_cusip)  # an equity line is never a bond

    def test_amendment_supersedes_and_fraction_rate_folds(self):
        _, catalog = self.build()
        corp = next(record for record in catalog.records if record.cusip == CORP)
        self.assertEqual((corp.coupon, corp.coupon_state), (3.5, "CONSENSUS"))  # F2's 9.99 was superseded
        self.assertEqual((corp.fund_count, corp.par_held), (3, 3_500_000.0))
        self.assertEqual((corp.value_pct_par, corp.report_date_max, corp.filing_date_max), (99.0, "2026-04-30", "2026-06-25"))
        self.assertEqual((corp.isin, corp.isin_source, corp.issuer_lei), (CORP_ISIN, "REPORTED", LEI))
        muni = next(record for record in catalog.records if record.cusip == MUNI)
        self.assertEqual((muni.coupon, muni.isin_source, muni.issuer_lei), (5.0, "DERIVED", None))
        ambiguous = next(record for record in catalog.records if record.cusip == AMBIGUOUS)
        self.assertEqual((ambiguous.coupon, ambiguous.coupon_state), (None, "AMBIGUOUS_RATE_ENCODING"))
        mbs = next(record for record in catalog.records if record.cusip == MBS)
        self.assertEqual((mbs.category, mbs.subtype), ("Securitized", "Agency MBS"))

    def test_build_is_deterministic(self):
        first, _ = self.build()
        again = self.dir / "again.sqlite"
        second = nc.build_catalog_db([self.dir / NAME], again, meta={"generation": "g1"})
        for key in ("build_s",):
            first.pop(key), second.pop(key)
        self.assertEqual(first, second)
        import sqlite3
        from contextlib import closing

        def rows(path: Path) -> list[tuple]:
            with closing(sqlite3.connect(path)) as db:
                return db.execute("SELECT * FROM securities ORDER BY cusip").fetchall()

        self.assertEqual(rows(self.dir / "index.sqlite"), rows(again))

    def test_archive_integrity_fails_closed(self):
        for payload, code in ((nport_zip(drop="DEBT_SECURITY.tsv"), "NPORT_SOURCE_TABLE_MISSING"),
                              (nport_zip(bad_column=True), "NPORT_SOURCE_COLUMNS_MISSING"), (b"not a zip", "NPORT_SOURCE_CORRUPT")):
            path = self.dir / "x_nport.zip"
            path.write_bytes(payload)
            with self.assertRaises(SourceIntegrityError) as caught:
                nc.verify_nport_archive(path)
            self.assertIn(code, str(caught.exception))

    def test_iter_records_drops_matured(self):
        _, catalog = self.build()
        self.assertNotIn(MATURED, {record.cusip for record in nc.iter_records(catalog, TODAY)})
        self.assertIn(MATURED, {record.cusip for record in nc.iter_records(catalog, date(2026, 5, 1))})


# ------------------------------------------------------------------ lifecycle
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "nport"

    def test_listing_admits_sec_quarter_links_only(self):
        refs = nc.parse_listing(listing("2026q1_nport.zip", NAME) + '<a href="/files/readme.pdf">x</a>')
        self.assertEqual([ref.name for ref in refs], ["2026q1_nport.zip", NAME])
        self.assertEqual((refs[-1].coverage_start, refs[-1].coverage_end), ("2026-04-01", "2026-06-30"))
        self.assertTrue(all(ref.url.startswith("https://www.sec.gov/") for ref in refs))
        self.assertIsNone(nc.dataset_from_name("2026q5_nport.zip", URL))

    def test_refresh_publishes_a_manifested_generation_and_the_screener_loads_it(self):
        result = build_root(self.root)
        self.assertEqual(result["outcome"], "PUBLISHED", result)
        manifest = result["manifest"]
        self.assertEqual(manifest["schema_version"], nc.MANIFEST_SCHEMA)
        self.assertEqual(manifest["index_schema"], nc.SCHEMA)
        self.assertEqual(manifest["securities"], 7)
        self.assertEqual(manifest["by_category"]["Municipal"], 1)
        state = nc.status(self.root)
        self.assertEqual(state["source_dataset_count"], 1)
        catalog, status = nc.ManagedCatalog(self.root).current()
        self.assertEqual(len(catalog.records), 7)
        self.assertEqual(catalog.meta["generation"], result["generation"])
        self.assertNotIn("load_problem", status)

    def test_empty_root_is_not_built(self):
        catalog, status = nc.ManagedCatalog(self.root).current()
        self.assertIsNone(catalog)
        self.assertEqual(status["load_problem"], "NPORT_CATALOG_NOT_BUILT")

    def test_a_corrupt_download_publishes_nothing(self):
        result = build_root(self.root, payload=b"not a zip")
        self.assertEqual(result["outcome"], "FAILED")
        self.assertIsNone(nc.NportStore(self.root).current_generation())

    def test_a_missing_category_fails_validation(self):
        payload = nport_zip()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            tables = {name: archive.read(name).decode() for name in archive.namelist()}
        tables["FUND_REPORTED_HOLDING.tsv"] = "\n".join(line for line in tables["FUND_REPORTED_HOLDING.tsv"].splitlines()
                                                         if "\tMUN\t" not in line) + "\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, text in tables.items():
                archive.writestr(name, text)
        result = build_root(self.root, payload=buffer.getvalue())
        self.assertEqual((result["outcome"], result["error"]), ("FAILED", "NPORT_CATEGORY_MISSING"))


# ------------------------------------------------------------------ Treasury market data & NY Fed
def getter(routes: dict[str, object]):
    calls: list[str] = []

    def get(url: str, timeout: float) -> bytes:
        calls.append(url)
        for fragment, payload in routes.items():
            if fragment in url:
                if isinstance(payload, Exception):
                    raise payload
                return json.dumps(payload).encode()
        raise AssertionError(f"unexpected URL {url}")

    get.calls = calls  # type: ignore[attr-defined]
    return get


TIPS_ROWS = {"data": [{"cusip": "912810US5", "index_date": "2026-09-27", "index_ratio": "1.01234", "ref_cpi": "321.5"},
                      {"cusip": "912810US5", "index_date": "2026-09-26", "index_ratio": "1.01200", "ref_cpi": "321.4"},
                      {"cusip": "BAD", "index_date": "2026-09-27", "index_ratio": "1.0"}]}
FRN_ROWS = {"data": [{"cusip": "91282CRD5", "record_date": "2026-09-26", "spread": "0.1", "daily_index": "3.9",
                      "daily_int_accrual_rate": "4.0", "daily_accrued_int_per100": "0.011", "accr_int_per100_pmt_period": "0.66",
                      "start_of_accrual_period": "2026-07-31", "end_of_accrual_period": "2026-10-30"}]}
BUYBACK_OPS = {"data": [{"operation_date": "2026-09-24", "operation_start_time_est": "10:30", "settlement_date": "2026-09-25",
                         "operation_type": "Liquidity Support", "security_type": "Nominal Coupons"}]}
BUYBACK_DETAILS = {"data": [
    {"cusip_nbr": "91282CRF0", "operation_date": "2026-09-24", "operation_start_time_est": "10:30",
     "weighted_avg_accepted_price": "99.5", "par_amt_accepted": "250000000"},
    {"cusip_nbr": "912810UX4", "operation_date": "2026-09-24", "operation_start_time_est": "10:30",
     "weighted_avg_accepted_price": "null", "par_amt_accepted": "0"},  # offered, none accepted: no price
    {"cusip_nbr": "912810UW6", "operation_date": "2026-09-24", "operation_start_time_est": "11:30",
     "weighted_avg_accepted_price": "101", "par_amt_accepted": "5"}]}  # no matching operation: no settlement
FED_OPS = {"treasury": {"auctions": [
    {"operationDirection": "P", "auctionStatus": "Results", "operationDate": "2026-09-24", "settlementDate": "2026-09-25",
     "operationType": "Outright Bill Purchase", "closeTime": "10:00",
     # Bill purchases are accepted on a discount-rate basis (the live feed's "price" is e.g. 3.932 = 3.932%).
     "details": [{"cusip": "912797WA1", "weightedAvgAccptPrice": "3.932", "parAmountAccepted": "1000"},
                 {"cusip": "912797VN4", "weightedAvgAccptPrice": "NA", "parAmountAccepted": "0"},
                 {"cusip": "912797VP9", "weightedAvgAccptPrice": "99.1", "parAmountAccepted": "5"}]},
    {"operationDirection": "P", "auctionStatus": "Results", "operationDate": "2026-09-23", "settlementDate": "2026-09-24",
     "operationType": "Outright Coupon Purchase", "closeTime": "11:00",
     "details": [{"cusip": "91282CRF0", "weightedAvgAccptPrice": "99.25", "parAmountAccepted": "10"}]},
    {"operationDirection": "S", "auctionStatus": "Results", "operationDate": "2026-09-24",
     "details": [{"cusip": "91282CRF0", "weightedAvgAccptPrice": "99", "parAmountAccepted": "1"}]},
    {"operationDirection": "P", "auctionStatus": "Announcement", "operationDate": "2026-09-30", "details": []}]}}


class TreasuryMarketTests(unittest.TestCase):
    def test_tips_and_frn_indexes_keep_the_latest_row_per_cusip(self):
        tips = load_tips_index(getter({"tips_cpi": TIPS_ROWS}), TODAY)
        self.assertEqual(list(tips), ["912810US5"])
        self.assertEqual((tips["912810US5"].index_ratio, tips["912810US5"].index_date), (1.01234, date(2026, 9, 27)))
        frn = load_frn_index(getter({"frn_daily": FRN_ROWS}), TODAY)["91282CRD5"]
        self.assertEqual((frn.daily_index, frn.accrual_rate, frn.accrual_end), (3.9, 4.0, date(2026, 10, 30)))

    def test_buyback_prices_need_an_accepted_amount_and_a_settlement(self):
        prices = load_buyback_prices(getter({"buybacks_operations": BUYBACK_OPS, "buybacks_security": BUYBACK_DETAILS}), TODAY)
        self.assertEqual([(item.cusip, item.price, item.settlement_date) for item in prices],
                         [("91282CRF0", 99.5, date(2026, 9, 25))])

    def test_fed_operations_keep_purchase_results_only(self):
        prices = parse_operations(FED_OPS)
        self.assertEqual([(item.cusip, item.kind, item.price, item.quote_basis) for item in prices],
                         [("912797WA1", "FED_BILL_PURCHASE", 3.932, "DISCOUNT_RATE"),
                          ("91282CRF0", "FED_COUPON_PURCHASE", 99.25, "PRICE_PER_100")])

    def test_latest_observation_wins(self):
        old = OperationPrice("X" * 9, 99.0, "TREASURY_BUYBACK", "S", date(2026, 9, 1), None, 1.0, "B")
        new = OperationPrice("X" * 9, 98.0, "TREASURY_BUYBACK", "S", date(2026, 9, 2), None, 1.0, "B")
        self.assertEqual(latest_prices([new, old])["X" * 9].price, 98.0)

    def test_one_failing_feed_never_hides_the_others(self):
        from market_platform_foundation.fixed_income.http import FixedIncomeSourceError

        get = getter({"tips_cpi": TIPS_ROWS, "frn_daily": FixedIncomeSourceError("HTTP_503"),
                      "buybacks_operations": BUYBACK_OPS, "buybacks_security": BUYBACK_DETAILS})
        data = fetch_market_data(today=TODAY, fetched_at="t", get=get, operations_loader=lambda **_: parse_operations(FED_OPS))
        self.assertEqual(data.errors, {"FRN_INDEX": "HTTP_503"})
        self.assertEqual(set(data.prices), {"91282CRF0", "912797WA1"})
        self.assertEqual(data.counts["tips"], 1)

    def test_ny_fed_rates_and_soma(self):
        rates = load_reference_rates(get=getter({"rates/all": {"refRates": [
            {"type": "SOFR", "effectiveDate": "2026-09-25", "percentRate": 4.31, "volumeInBillions": 2400},
            {"type": "EFFR", "effectiveDate": "2026-09-25", "percentRate": 4.33, "targetRateFrom": 4.25, "targetRateTo": 4.5},
            {"type": "XYZ", "effectiveDate": "2026-09-25", "percentRate": 1}]}}))
        self.assertEqual([item["id"] for item in rates["items"]], ["SOFR", "EFFR"])
        self.assertEqual(rates["items"][1]["target_to"], 4.5)
        soma = load_soma(get=getter({
            "asofdates": {"soma": {"asOfDates": ["2026-09-23"]}},
            "soma/tsy": {"soma": {"holdings": [{"cusip": "91282CRF0", "securityType": "NotesBonds", "parValue": "5e9",
                                                "percentOutstanding": "0.06"}]}},
            "soma/agency": {"soma": {"holdings": [{"cusip": MBS, "securityType": "MBS", "parValue": "2e6"}]}}}))
        self.assertEqual(soma.for_cusip("91282CRF0").percent_outstanding, 6.0)
        self.assertEqual(soma.counts, {"NotesBonds": 1, "MBS": 1})


# ------------------------------------------------------------------ observed analytics
class ObservedAnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = fixture_catalog(TODAY, "t")
        cls.rates = fixture_rates(TODAY, "t")
        cls.securities = {security.cusip: security for security in cls.catalog.securities}

    def observe(self, code: str, price: float, kind: str = "TREASURY_BUYBACK", day: date = date(2026, 9, 24),
                basis: str = "PRICE_PER_100") -> dict:
        return observed_measures(self.securities[code], OperationPrice(code, price, kind, "S", day, date(2026, 9, 25), 1.0, "B",
                                                                       quote_basis=basis), self.rates)

    def test_note_yield_round_trips_and_spread_uses_the_same_day_curve(self):
        result = self.observe("91282CRF0", 99.5)
        security = self.securities["91282CRF0"]
        back = analytics.price_from_yield(result["yield"], security.coupon_pct, security.payments_per_year, date(2026, 9, 25),
                                          security.maturity_date, dated_date=security.dated_date)
        self.assertAlmostEqual(back, 99.5, places=4)
        self.assertEqual((result["state"], result["yield_basis"], result["operation_date"]), ("DATED_OBSERVATION", "YTM", "2026-09-24"))
        benchmark = result["benchmark"]
        self.assertEqual((benchmark["curve"], benchmark["publication_date"]), ("NOMINAL_PAR", "2026-09-24"))
        self.assertAlmostEqual(benchmark["spread_bp"], round((result["yield"] - benchmark["value"]) * 100, 1), places=6)
        self.assertGreater(result["dv01"], 0)

    def test_tips_price_is_real_and_benchmarks_the_real_curve(self):
        result = self.observe("912810US5", 80.0)
        self.assertEqual((result["price_basis"], result["yield_basis"], result["benchmark"]["curve"]),
                         ("REAL_PER_100_UNADJUSTED", "REAL_YTM", "REAL_PAR"))

    def test_bill_rates_and_frn_refusal(self):
        bill = self.observe("912797WA1", 96.5, "FED_BILL_PURCHASE")
        self.assertEqual(bill["yield_basis"], "INVESTMENT_RATE")
        days = (self.securities["912797WA1"].maturity_date - date(2026, 9, 25)).days
        self.assertAlmostEqual(analytics.bill_price_from_investment_rate(bill["yield"], days, date(2026, 9, 25)), 96.5, places=4)
        self.assertAlmostEqual(bill["discount_rate"], (100 - 96.5) / 100 * 360 / days * 100, places=4)
        frn = self.observe("91282CRD5", 100.0)
        self.assertEqual((frn["yield"], frn["reason"]), (None, "FRN_FLOATING_COUPON"))

    def test_fed_bill_discount_rate_quote_becomes_a_price_only_against_maturity(self):
        days = (self.securities["912797WA1"].maturity_date - date(2026, 9, 25)).days
        bill = self.observe("912797WA1", 3.9, "FED_BILL_PURCHASE", basis="DISCOUNT_RATE")
        self.assertAlmostEqual(bill["price"], 100 * (1 - 0.039 * days / 360), places=5)
        self.assertEqual((bill["quoted_discount_rate"], bill["price_basis"]), (3.9, "PER_100_PAR_FROM_DISCOUNT_RATE"))
        self.assertAlmostEqual(bill["discount_rate"], 3.9, places=4)
        self.assertGreater(bill["yield"], 3.9)  # the investment rate exceeds the discount rate
        self.assertLess(abs(bill["benchmark"]["spread_bp"]), 100)  # a rate read as a price would be off by thousands of bp
        wrong = self.observe("91282CRF0", 3.9, "FED_BILL_PURCHASE", basis="DISCOUNT_RATE")
        self.assertEqual((wrong["price"], wrong["yield"], wrong["reason"]), (None, None, "QUOTE_BASIS_MISMATCH"))

    def test_no_curve_on_the_operation_date_means_no_spread(self):
        result = self.observe("91282CRF0", 99.5, day=date(2026, 9, 23))
        self.assertEqual(result["benchmark"], {"state": "UNAVAILABLE", "reason": "NO_CURVE_ON_OPERATION_DATE"})

    def test_interpolation_never_extrapolates(self):
        curve = CurvePublication(NOMINAL, date(2026, 9, 24), (CurvePoint("2Y", 2.0, 4.0), CurvePoint("10Y", 10.0, 5.0)))
        self.assertEqual(interpolate_par(6.0, curve)["value"], 4.5)
        self.assertEqual(interpolate_par(1.0, curve)["reason"], "OUTSIDE_CURVE_RANGE")
        self.assertEqual(interpolate_par(11.0, curve)["reason"], "OUTSIDE_CURVE_RANGE")


# ------------------------------------------------------------------ OpenFIGI & FINRA breadth gating
class GatingTests(unittest.TestCase):
    def test_openfigi_is_off_without_the_flag_and_cached_and_rate_limited_with_it(self):
        posts: list[object] = []

        def post(url, payload, timeout, headers):
            posts.append(payload)
            return [{"data": [{"figi": "BBG000000001", "name": "MICROSOFT CORP", "securityType2": "Corp"}]}]

        self.assertEqual(OpenFigi(env={}, post=post).lookup(CORP)["state"], "NOT_CONFIGURED")
        self.assertEqual(posts, [])
        figi = OpenFigi(env={"IMP_OPENFIGI_LIVE": "1"}, post=post, clock=lambda: 0.0)
        self.assertEqual(figi.lookup(CORP)["items"][0]["figi"], "BBG000000001")
        figi.lookup(CORP)
        self.assertEqual(len(posts), 1)  # cached
        results = [figi.lookup(cusip(f"0000{index:04d}")) for index in range(25)]
        self.assertEqual(results[-1]["reason"], "OPENFIGI_RATE_LIMITED")
        self.assertEqual(len(posts), 20)

    def test_finra_breadth_is_not_configured_without_credentials_and_per_dataset_with_them(self):
        self.assertEqual(load_market_breadth(today=TODAY, env={})["state"], "NOT_CONFIGURED")

        class Response:
            def __init__(self, records):
                self.records = records

        class Transport:
            def post(self, path, body):
                if "agency" in path:
                    raise RuntimeError("FINRA_HTTP_429")
                return Response([{"tradeReportDate": "2026-09-25", "productCategory": "All Securities", "totalTrades": 7000},
                                 {"tradeReportDate": "2026-09-24", "productCategory": "All Securities", "totalTrades": 6900}])

        breadth = load_market_breadth(today=TODAY, env={}, transport_factory=Transport)
        self.assertEqual(breadth["state"], "PARTIAL")
        corporate = breadth["categories"]["CORPORATE"]
        self.assertEqual((corporate["trade_date"], len(corporate["rows"])), ("2026-09-25", 1))
        agency = breadth["categories"]["AGENCY"]
        self.assertEqual((agency["state"], agency["reason"]), ("UNAVAILABLE", "FINRA_HTTP_429"))


# ------------------------------------------------------------------ BONDS universe with fund-held rows
class FundRowScreenerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name) / "nport"
        assert build_root(cls.root)["outcome"] == "PUBLISHED"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        prices = {"91282CRF0": OperationPrice("91282CRF0", 99.5, "TREASURY_BUYBACK", "US_TREASURY_FISCAL_DATA_BUYBACKS",
                                              date(2026, 9, 24), date(2026, 9, 25), 2.5e8, "Buyback")}
        self.market_calls = 0

        def market(today, fetched_at):
            self.market_calls += 1
            return TreasuryMarketData({}, {}, prices, {}, fetched_at)

        self.figi_posts: list[object] = []
        self.svc = BondScreener(
            env={"IMP_TREASURY_LIVE": "1"}, catalog_loader=fixture_catalog, rates_loader=fixture_rates,
            fred_loader=lambda **_: {"state": "NOT_CONFIGURED", "reason": "FRED_API_KEY_MISSING", "items": []},
            finra_loader=lambda **_: {"state": "NOT_CONFIGURED", "reason": "X", "trade_date": None, "rows": []},
            breadth_loader=lambda **_: {"state": "NOT_CONFIGURED", "reason": "X", "categories": {}},
            market_loader=market, nyfed_rates_loader=lambda: {"state": "UNAVAILABLE", "reason": "TEST", "items": []},
            soma_loader=lambda: None, nport=nc.ManagedCatalog(self.root),
            openfigi=OpenFigi(env={}, post=lambda *args: self.figi_posts.append(args)),
            clock=Clock(), today=lambda: TODAY, now=lambda: "2026-09-27T20:00:00Z")

    def read(self, **kwargs) -> dict:
        return self.svc.read(parse_query(universe=BONDS, limit=500, **kwargs))

    def ids(self, **kwargs) -> dict[str, dict]:
        return {row["cusip"]: row for row in self.read(**kwargs)["rows"]}

    def test_categories_live_inside_the_one_bonds_universe(self):
        self.assertEqual(list(UNIVERSES), ["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"])
        payload = self.read()
        self.assertEqual(payload["unfiltered_count"], 8 + 6)  # 8 Treasuries + 6 unmatured fund-held
        self.assertEqual(payload["coverage"]["TREASURY"], {"state": "CURRENT", "count": 8})
        self.assertEqual(payload["coverage"]["CORPORATE"], {"state": "FUND_HELD_REFERENCE", "count": 3})
        self.assertEqual(payload["coverage"]["MUNICIPAL"], {"state": "FUND_HELD_REFERENCE", "count": 1})
        self.assertEqual(payload["coverage_sources"]["MUNICIPAL"]["as_of"], "2026-04-30")
        self.assertEqual({row["category"] for row in payload["rows"]}, {"Treasury", "Corporate", "Agency", "Municipal", "Securitized"})
        self.assertIn("SEC_FORM_NPORT", {item["provider"] for item in payload["provider_health"]})
        assert_no_secrets_in_payload(payload)

    def test_canonical_filters_sort_search_and_paging_span_categories(self):
        rule = lambda field, op, value: [{"id": "1", "field": field, "operator": op, "value": value}]  # noqa: E731
        self.assertEqual(set(self.ids(filters=rule("category", "eq", "Municipal"))), {MUNI})
        self.assertEqual(set(self.ids(filters=rule("fund_count", "gte", 3))), {CORP})  # Treasuries have no fund holdings
        # One filter spans categories: the Treasury FRN and the fund-held floater.
        self.assertEqual(set(self.ids(filters=rule("coupon_type", "eq", "Floating"))), {FLOATER, "91282CRD5"})
        self.assertEqual(set(self.ids(filters=rule("isin", "eq", CORP_ISIN))), {CORP})
        self.assertEqual(set(self.ids(search="microsoft")), {CORP})
        self.assertEqual(set(self.ids(search="agency mbs")), {MBS})
        coupons = [row["fields"]["coupon"]["value"] for row in self.read(sort="coupon", descending=True)["rows"]]
        present = [value for value in coupons if value is not None]
        self.assertEqual(present, sorted(present, reverse=True))
        self.assertEqual(coupons[len(present):], [None] * (len(coupons) - len(present)))
        first = self.svc.read(parse_query(universe=BONDS, sort="maturity", descending=False, limit=5))
        second = self.svc.read(parse_query(universe=BONDS, sort="maturity", descending=False, limit=5, offset=5,
                                           result_set=first["result_set_id"]))
        together = [row["cusip"] for row in first["rows"] + second["rows"]]
        self.assertEqual(together, [row["cusip"] for row in self.read(sort="maturity", descending=False)["rows"]][:10])

    def test_fund_rows_carry_labeled_stale_values_and_never_a_price(self):
        row = self.ids()[CORP]
        fields = row["fields"]
        self.assertEqual(fields["coupon"]["state"], "FUND_REPORTED_REFERENCE")
        self.assertEqual((fields["fund_value_pct"]["value"], fields["fund_value_pct"]["state"]), (99.0, "FUND_REPORTED_STALE"))
        self.assertEqual(fields["fund_value_pct"]["as_of"], "2026-04-30")
        self.assertIsNone(fields["observed_price"]["value"])
        self.assertEqual(row["instrument"]["tradability"], "REFERENCE_ONLY")
        self.assertEqual((row["isin"], row["isin_source"]), (CORP_ISIN, "REPORTED"))
        self.assertEqual(row["reference_tenor"], "3Y")  # the curve point, not this bond's yield
        self.assertEqual(self.ids()[FLOATER]["reference_reason"], "FLOATING_RATE_NO_MATURITY_MATCH")

    def test_observed_prices_attach_to_visible_treasury_rows_only_and_never_filter(self):
        row = self.ids()["91282CRF0"]
        self.assertEqual(row["fields"]["observed_price"]["state"], "DATED_OBSERVATION")
        self.assertEqual((row["observed_date"], row["fields"]["observed_yield"]["state"]), ("2026-09-24", "DERIVED"))
        self.assertIsNotNone(row["fields"]["benchmark_spread"]["value"])
        for field in ("observed_price", "observed_yield", "benchmark_spread"):
            self.assertEqual(field_capabilities(BONDS)[field]["filterable"], False)
            with self.assertRaises(ValueError):
                validate_filters([{"id": "1", "field": field, "operator": "gt", "value": 1}], universe=BONDS)
        self.read()
        self.read(search="ms")
        self.assertEqual(self.market_calls, 1)  # one cached bundle, never per row

    def test_fund_preview_and_curve_say_what_is_missing(self):
        instrument_id = self.ids()[MUNI]["instrument"]["instrument_id"]
        preview = self.svc.preview(instrument_id, [])
        self.assertEqual(preview["instrument"]["category"], "Municipal")
        sections = {section["id"]: {item["id"]: item for item in section["items"]} for section in preview["sections"]}
        self.assertEqual(set(sections), {"identity", "terms", "market", "holdings", "analytics", "ratings", "rates"})
        self.assertEqual(sections["market"]["price"]["class"], "UNAVAILABLE")
        self.assertIn("MSRB", sections["market"]["latest_trade"]["note"])
        self.assertEqual(sections["market"]["fund_value"]["class"], "STALE")
        self.assertEqual(sections["ratings"]["rating"]["class"], "UNAVAILABLE")
        self.assertEqual((sections["identity"]["isin"]["class"], sections["identity"]["figi"]["class"]), ("DERIVED", "UNAVAILABLE"))
        self.assertEqual(self.figi_posts, [])  # OpenFIGI off: no request
        sources = {item["id"]: item for item in preview["sources"]}
        self.assertEqual(sources["NPORT_CATALOG"]["as_of"], "2026-04-30")
        self.assertEqual((sources["NRSRO_RATINGS"]["state"], sources["MSRB_EMMA"]["state"]), ("TERMS_REQUIRED", "TERMS_REQUIRED"))
        curve = self.svc.rates_curve(instrument_id)
        self.assertEqual((curve["selected"]["category"], curve["selected"]["spread"]["state"]), ("Municipal", "UNAVAILABLE"))
        assert_no_secrets_in_payload(preview)

    def test_treasury_preview_shows_the_dated_observation_and_spread(self):
        instrument_id = self.ids()["91282CRF0"]["instrument"]["instrument_id"]
        sections = {section["id"]: {item["id"]: item for item in section["items"]}
                    for section in self.svc.preview(instrument_id, [])["sections"]}
        self.assertEqual((sections["market"]["observed_price"]["value"], sections["market"]["observed_price"]["as_of"]),
                         (99.5, "2026-09-24"))
        self.assertEqual(sections["market"]["price"]["class"], "UNAVAILABLE")  # still no current price
        self.assertEqual(sections["rates"]["spread"]["class"], "DERIVED")
        self.assertEqual(sections["identity"]["isin"]["value"], isin_from_cusip("91282CRF0"))
        spread = self.svc.rates_curve(instrument_id)["selected"]["spread"]
        self.assertEqual((spread["state"], spread["operation_date"], spread["curve_date"]), ("DERIVED", "2026-09-24", "2026-09-24"))

    def test_identity_is_unique_and_bonds_are_never_etfs(self):
        rows = self.read()["rows"]
        ids = [row["instrument"]["instrument_id"] for row in rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["instrument"]["asset_class"] in ("BOND", "SOVEREIGN_DEBT") for row in rows))
        self.assertFalse(any("ETF" in (row["security_type"] or "").upper() for row in rows))
        self.assertNotIn("category", {entry for entry in field_capabilities(US_ETFS) if field_capabilities(US_ETFS)[entry]["filterable"]})

    def test_fund_row_view_answers_the_canonical_access_paths(self):
        catalog, _ = nc.ManagedCatalog(self.root).current()
        record = next(record for record in catalog.records if record.cusip == CORP)
        view = FundHeldRow(record, TODAY)
        full = view.to_dict()
        for name in ("symbol", "category", "coupon_type", "isin", "maturity", "frn", "in_default"):
            self.assertEqual(view.get(name), full[name], name)
        for name, envelope in full["fields"].items():
            self.assertEqual(view["fields"][name]["value"], envelope["value"], name)
        self.assertEqual(view["instrument"]["instrument_id"], full["instrument"]["instrument_id"])


if __name__ == "__main__":
    unittest.main()
