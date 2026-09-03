"""FinViz screener for quiet stocks near 0% move and Path A universe merge.

Purpose
-------
HTML-scrape (or optional Elite CSV) Finviz screener tables, parse rows, and apply
local filters for Path A discovery: small-cap "quiet" names plus optional mid/large
catalyst movers.

Pipeline role
-------------
``screen_path_a_universe_with_stats`` feeds ``main.refresh_watchlist_and_social``.
Also used by ``catalyst_scanner.enrich_with_finviz_movers`` and Path B via
``fetch_finviz_rows``.

Key outputs
-----------
Candidate dicts: ``{ticker, company_name, current_price, percent_change, volume,
relative_volume, universe_tier, source}`` plus scrape health stats.

Handoff notes
-------------
**Reusable (equity/futures):** Scraper session, pagination, percent/volume parsers,
filter-code builder — swap Finviz filter strings for futures screeners or internal
universe APIs.

**Options-only coupling:** ``require_optionable`` / ``sh_opt_option`` filters;
``build_quiet_filter_codes`` cap bands tuned for optionable small-caps.

**Not required for futures:** Elite export path; HTML scraper pattern is sufficient
for handoff prototypes.
"""

from __future__ import annotations

import csv
import io
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

_PROXY_ENV_CLEARED = False
_SCRAPER_SESSION: Optional[requests.Session] = None

DEFAULT_ELITE_BASE_URL = "https://elite.finviz.com/export.ashx"
DEFAULT_ELITE_FILTERS = "ind_stocksonly,cap_smallunder,sh_relvol_o1.5,sh_curvol_o100"
DEFAULT_TOKEN_ENV = "FINVIZ_AUTH_TOKEN"
DEFAULT_SCREENER_URL = "https://finviz.com/screener.ashx"
PAGE_SIZE = 20
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/csv,application/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def disable_proxy_env_if_present() -> None:
    """
    Remove proxy environment variables for this Python process.

    Inputs:
    - None.

    Output:
    - None.

    Why this exists:
    - Some local environments set global proxy variables that block
      FinViz requests with tunnel/proxy errors.
    """
    global _PROXY_ENV_CLEARED
    if _PROXY_ENV_CLEARED:
        return

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
    _PROXY_ENV_CLEARED = True


def parse_percent(value: Any) -> float:
    """
    Convert a percent-like value into a float percentage number.

    Inputs:
    - value: any value that may look like '0.45%' or -0.12.

    Output:
    - A float like 0.45 or -0.12. Returns 0.0 if parsing fails.

    Why this exists:
    - FinViz data can arrive as text. We need consistent numeric values
      so we can compare each stock to our screening thresholds.
    """
    if value is None:
        return 0.0
    text = str(value).strip().replace("%", "").replace("+", "")
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def parse_number_with_suffix(value: Any) -> float:
    """
    Convert strings like '1.2M' or '800K' into a plain float number.

    Inputs:
    - value: any value that may include K/M/B/T suffixes.

    Output:
    - A numeric float representation. Returns 0.0 if parsing fails.

    Why this exists:
    - FinViz reports volume and market cap with letter suffixes, and
      we need real numbers to apply our filters.
    """
    if value is None:
        return 0.0

    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "N/A", "nan"}:
        return 0.0

    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
    suffix = text[-1].upper()

    try:
        if suffix in multipliers:
            return float(text[:-1]) * multipliers[suffix]
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def resolve_finviz_token(screener_cfg: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve Finviz Elite auth token from env or inline settings."""
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path, override=True)

    cfg = screener_cfg or {}
    elite_cfg = cfg.get("elite", {}) if isinstance(cfg.get("elite"), dict) else {}
    env_name = str(elite_cfg.get("auth_token_env", DEFAULT_TOKEN_ENV))
    token = os.environ.get(env_name)
    if token:
        return token.strip()
    inline = elite_cfg.get("auth_token")
    if inline:
        return str(inline).strip()
    return None


DEFAULT_OPTIONS_BASE_URL = "https://elite.finviz.com/export/options"


def probe_finviz_elite_auth(
    screener_cfg: Optional[Dict[str, Any]] = None,
    options_probe_ticker: str = "AAPL",
) -> Dict[str, Any]:
    """Quick auth probe for Finviz Elite screener + options export endpoints."""
    token = resolve_finviz_token(screener_cfg)
    prefix = f"{token[:8]}..." if token else "missing"
    if not token:
        return {
            "token_prefix": prefix,
            "screener_ok": False,
            "options_ok": False,
            "ok": False,
            "message": "FINVIZ_AUTH_TOKEN missing from .env",
        }

    cfg = screener_cfg or {}
    elite_cfg = cfg.get("elite", {}) if isinstance(cfg.get("elite"), dict) else {}
    timeout = float(elite_cfg.get("request_timeout_seconds", 10))

    def _probe(url: str, params: Dict[str, str]) -> bool:
        try:
            disable_proxy_env_if_present()
            response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
            if response.status_code in (401, 403):
                return False
            return response.status_code == 200 and (
                "text/csv" in response.headers.get("content-type", "") or "," in response.text[:200]
            )
        except requests.RequestException:
            return False

    screener_ok = _probe(
        str(elite_cfg.get("base_url", DEFAULT_ELITE_BASE_URL)),
        {"v": str(elite_cfg.get("view", "111")), "f": str(elite_cfg.get("filters", DEFAULT_ELITE_FILTERS)), "auth": token},
    )
    options_ok = _probe(
        str(elite_cfg.get("options_base_url", DEFAULT_OPTIONS_BASE_URL)),
        {"t": options_probe_ticker.upper().strip(), "auth": token},
    )
    ok = screener_ok and options_ok
    if ok:
        message = "Finviz Elite auth OK (screener + options)"
    elif not screener_ok and not options_ok:
        message = "Finviz token rejected on screener AND options — update .env and restart main.py"
    elif not screener_ok:
        message = "Finviz token rejected on screener export — update .env and restart main.py"
    else:
        message = "Finviz token rejected on options export — options confirmation will be no_data"
    return {
        "token_prefix": prefix,
        "screener_ok": screener_ok,
        "options_ok": options_ok,
        "ok": ok,
        "message": message,
    }


def build_elite_export_url(
    token: str,
    screener_cfg: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build authenticated Finviz Elite screener CSV export URL.

    Inputs:
    - token: Finviz Elite auth token.
    - screener_cfg: optional screener settings block.

    Output:
    - Fully qualified export URL with auth query parameter.
    """
    cfg = screener_cfg or {}
    elite_cfg = cfg.get("elite", {}) if isinstance(cfg.get("elite"), dict) else {}
    configured_url = str(elite_cfg.get("export_url", "")).strip()

    if configured_url:
        parsed = urlparse(configured_url)
        path = parsed.path.replace("screener.ashx", "export.ashx")
        query = parse_qs(parsed.query)
        query["auth"] = [token]
        new_query = urlencode({k: v[-1] for k, v in query.items()})
        return urlunparse((parsed.scheme or "https", parsed.netloc or "elite.finviz.com", path, parsed.params, new_query, parsed.fragment))

    view = str(elite_cfg.get("view", "111"))
    sort = str(elite_cfg.get("sort", ""))
    filters = str(elite_cfg.get("filters", DEFAULT_ELITE_FILTERS))
    base_url = str(elite_cfg.get("base_url", DEFAULT_ELITE_BASE_URL))
    query = urlencode({"v": view, "f": filters, "auth": token})
    if sort:
        query = urlencode({"v": view, "s": sort, "f": filters, "auth": token})
    return f"{base_url}?{query}"


def _normalize_csv_field(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _pick_field(row: Dict[str, Any], aliases: List[str]) -> Any:
    normalized = {_normalize_csv_field(k): v for k, v in row.items()}
    for alias in aliases:
        value = normalized.get(_normalize_csv_field(alias))
        if value is not None and str(value).strip() not in {"", "-", "N/A"}:
            return value
    return None


def parse_elite_csv_rows(csv_text: str) -> List[Dict[str, Any]]:
    """Parse Finviz Elite screener CSV into overview-compatible row dicts."""
    if not csv_text or not csv_text.strip():
        return []

    reader = csv.DictReader(io.StringIO(csv_text))
    rows: List[Dict[str, Any]] = []
    for raw in reader:
        rows.append(
            {
                "Ticker": str(_pick_field(raw, ["Ticker"]) or "").strip().upper(),
                "Company": str(_pick_field(raw, ["Company"]) or "").strip(),
                "Price": _pick_field(raw, ["Price"]),
                "Change": _pick_field(raw, ["Change"]),
                "Volume": _pick_field(raw, ["Volume", "Current Volume"]),
                "Average Volume": _pick_field(raw, ["Average Volume", "Avg Volume", "Avg Vol"]),
                "Market Cap.": _pick_field(raw, ["Market Cap", "Market Cap."]),
            }
        )
    return rows


def fetch_finviz_rows_elite(
    screener_cfg: Optional[Dict[str, Any]] = None,
    max_rows: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Download screener rows via Finviz Elite CSV export API.

    Inputs:
    - screener_cfg: screener settings block with elite config.
    - max_rows: optional cap on number of returned rows.

    Output:
    - A list of row dictionaries. Returns an empty list on errors.
    """
    token = resolve_finviz_token(screener_cfg)
    if not token:
        return []

    cfg = screener_cfg or {}
    elite_cfg = cfg.get("elite", {}) if isinstance(cfg.get("elite"), dict) else {}
    timeout = float(elite_cfg.get("request_timeout_seconds", 10))

    try:
        disable_proxy_env_if_present()
        url = build_elite_export_url(token=token, screener_cfg=screener_cfg)
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        rows = parse_elite_csv_rows(response.text)
        if max_rows is not None and max_rows > 0:
            rows = rows[:max_rows]
        return rows
    except Exception as error:
        print(f"[finviz_screener] Elite API fetch failed: {error}")
        return []


def build_finviz_server_filters(
    price_change_min: float,
    price_change_max: float,
    market_cap_max_billion: Optional[float],
    *,
    market_cap_min_billion: float = 0.0,
    require_optionable: bool = False,
) -> Dict[str, str]:
    """Build best-effort FinViz human-readable filter dictionary (legacy)."""
    filters: Dict[str, str] = {}
    _ = (price_change_min, price_change_max)
    cap_max = float(market_cap_max_billion) if market_cap_max_billion is not None else None
    if cap_max is not None and cap_max <= 2:
        filters["Market Cap."] = "-Small (under $2bln)"
    elif cap_max is not None and cap_max <= 10:
        filters["Market Cap."] = "-Mid (under $10bln)"
    elif float(market_cap_min_billion or 0.0) >= 2:
        filters["Market Cap."] = "+Mid (over $2bln)"
    filters["Relative Volume"] = "Over 1.5"
    filters["Current Volume"] = "Over 100K"
    if require_optionable:
        filters["Optionable"] = "Optionable"
    return filters


def build_quiet_filter_codes(
    market_cap_max_billion: Optional[float] = 2.0,
    *,
    market_cap_min_billion: float = 0.0,
    require_optionable: bool = False,
) -> str:
    """Build Finviz URL filter codes for Path A quiet / catalyst scans."""
    parts = ["ind_stocksonly", "sh_relvol_o1.5", "sh_curvol_o100"]
    cap_max = float(market_cap_max_billion) if market_cap_max_billion is not None else None
    if cap_max is not None and cap_max <= 2:
        parts.append("cap_smallunder")
    elif cap_max is not None and cap_max <= 10:
        parts.append("cap_midunder")
    elif float(market_cap_min_billion or 0.0) >= 2:
        # Mid + large: Finviz "Mid over $2bln" includes large/mega.
        parts.append("cap_midover")
    if require_optionable:
        parts.append("sh_opt_option")
    return ",".join(parts)


def get_scraper_session() -> requests.Session:
    """Reuse one HTTP session for Finviz HTML scrapes."""
    global _SCRAPER_SESSION
    if _SCRAPER_SESSION is None:
        disable_proxy_env_if_present()
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        _SCRAPER_SESSION = session
    return _SCRAPER_SESSION


def filters_dict_to_codes(server_filters: Optional[Dict[str, str]]) -> str:
    """Map human-readable filter dict to Finviz URL codes when possible."""
    if not server_filters:
        return "ind_stocksonly,sh_relvol_o1.5,sh_curvol_o100"
    codes: List[str] = ["ind_stocksonly"]
    market_cap = str(server_filters.get("Market Cap.", server_filters.get("Market Cap", "")))
    cap_l = market_cap.lower()
    if "under $2" in cap_l or ("small" in cap_l and "over" not in cap_l):
        codes.append("cap_smallunder")
    elif "under $10" in cap_l:
        codes.append("cap_midunder")
    elif "over $2" in cap_l or ("mid" in cap_l and "over" in cap_l):
        codes.append("cap_midover")
    elif "mid" in cap_l:
        codes.append("cap_midunder")
    if "Relative Volume" in server_filters:
        codes.append("sh_relvol_o1.5")
    if "Current Volume" in server_filters:
        codes.append("sh_curvol_o100")
    if "Option/Short" in server_filters or "Optionable" in server_filters:
        codes.append("sh_opt_option")
    price = str(server_filters.get("Price", ""))
    if "Over $10" in price or "o10" in price.lower():
        codes.append("sh_price_o10")
    avg_vol = str(server_filters.get("Average Volume", server_filters.get("Avg Volume", "")))
    if "Over 1M" in avg_vol or "o1000" in avg_vol.lower():
        codes.append("sh_avgvol_o1000")
    return ",".join(dict.fromkeys(codes))


def _ticker_from_href(href: str) -> str:
    """Extract Finviz quote symbol from stock?t=AAPL or quote.ashx?t=AAPL links."""
    if not href:
        return ""
    try:
        query = parse_qs(urlparse(href).query)
        ticker = str((query.get("t") or [""])[0]).strip().upper()
        return ticker if ticker.isalnum() else ""
    except Exception:
        return ""


def _extract_ticker_from_cell(td: Any) -> str:
    """
    Read ticker from Finviz HTML cell without concatenating the first-letter icon.

    Finviz ticker cells currently render two anchors whose texts concatenate,
    e.g. 'P' + 'PYPL' => 'PPYPL'. Prefer the ``t=`` query param on the link.
    """
    if td is None:
        return ""
    # Prefer longer ticker from href params (skip single-letter icon link text).
    candidates: List[str] = []
    for anchor in td.find_all("a"):
        from_href = _ticker_from_href(str(anchor.get("href") or ""))
        if from_href:
            candidates.append(from_href)
        text = str(anchor.get_text(strip=True) or "").upper()
        if text.isalnum() and 1 < len(text) <= 6:
            candidates.append(text)
    if candidates:
        # Longest unique symbol is the real ticker (PYPL over P).
        candidates.sort(key=len, reverse=True)
        return candidates[0]

    raw = str(td.get_text(strip=True) or "").upper()
    # Fallback: undo doubled first-letter icon concat (PPYPL -> PYPL).
    if len(raw) >= 3 and raw[0] == raw[1] and raw[1:].isalnum():
        return raw[1:]
    return raw if raw.isalnum() else ""


def parse_screener_html(html: str) -> Tuple[List[Dict[str, Any]], int]:
    """
    Parse Finviz screener HTML table into overview-compatible row dicts.

    Returns (rows, total_pages). total_pages is 1 when pagination is unknown.
    """
    if not html or not html.strip():
        return [], 0
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="screener_table")
    if table is None:
        # Older Finviz markup sometimes uses id-based tables.
        table = soup.find("table", attrs={"id": "screener-table"})
    if table is None:
        return [], 0

    header_row = table.find("tr")
    if header_row is None:
        return [], 0
    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    # Drop leading empty / checkbox column when present.
    if headers and headers[0] in {"", "No."}:
        headers = headers[1:]

    rows: List[Dict[str, Any]] = []
    for tr in table.find_all("tr")[1:]:
        td_nodes = list(tr.find_all("td"))
        if not td_nodes:
            continue
        first_text = td_nodes[0].get_text(strip=True)
        if first_text in {"", "No."} or first_text.isdigit():
            td_nodes = td_nodes[1:]
        cells = [td.get_text(strip=True) for td in td_nodes]
        if len(cells) < len(headers):
            continue
        raw = {headers[i]: cells[i] for i in range(len(headers))}

        ticker_header_idx = next((i for i, h in enumerate(headers) if h.lower() == "ticker"), None)
        if ticker_header_idx is not None and ticker_header_idx < len(td_nodes):
            ticker = _extract_ticker_from_cell(td_nodes[ticker_header_idx])
        else:
            ticker = str(_pick_field(raw, ["Ticker"]) or "").strip().upper()
            if len(ticker) >= 3 and ticker[0] == ticker[1] and ticker[1:].isalnum():
                ticker = ticker[1:]

        rows.append(
            {
                "Ticker": ticker,
                "Company": str(_pick_field(raw, ["Company"]) or "").strip(),
                "Price": _pick_field(raw, ["Price"]),
                "Change": _pick_field(raw, ["Change"]),
                "Volume": _pick_field(raw, ["Volume", "Current Volume"]),
                "Average Volume": _pick_field(raw, ["Average Volume", "Avg Volume", "Avg Vol"]),
                "Rel Volume": _pick_field(raw, ["Rel Volume", "Relative Volume"]),
                "Market Cap.": _pick_field(raw, ["Market Cap", "Market Cap."]),
            }
        )

    page_count = 1
    page_select = soup.find(id="pageSelect")
    if page_select is not None:
        options = page_select.find_all("option")
        if options:
            page_count = len(options)
    return rows, page_count


def _fetch_screener_page(
    filter_codes: str,
    start_row: int,
    timeout: float,
    retries: int = 2,
    sort: str = "-relativevolume",
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch one Finviz screener page (start_row is 1-based Finviz `r` param)."""
    session = get_scraper_session()
    params = {"v": "111", "f": filter_codes, "o": sort}
    if start_row > 1:
        params["r"] = str(start_row)
    last_error: Optional[Exception] = None
    for attempt in range(max(1, retries + 1)):
        try:
            response = session.get(DEFAULT_SCREENER_URL, params=params, timeout=timeout)
            if response.status_code == 429:
                # Rate limited — back off and retry once or twice.
                time.sleep(1.5 * (attempt + 1))
                last_error = requests.HTTPError(f"429 Too Many Requests for {response.url}")
                continue
            response.raise_for_status()
            return parse_screener_html(response.text)
        except requests.RequestException as error:
            last_error = error
            time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    return [], 0


def fetch_finviz_rows_scraper(
    server_filters: Optional[Dict[str, str]] = None,
    max_rows: Optional[int] = None,
    screener_cfg: Optional[Dict[str, Any]] = None,
    filter_codes: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fast token-free Finviz HTML scrape (no inter-page sleep)."""
    rows, _meta = fetch_finviz_rows_scraper_with_meta(
        server_filters=server_filters,
        max_rows=max_rows,
        screener_cfg=screener_cfg,
        filter_codes=filter_codes,
    )
    return rows


def fetch_finviz_rows_scraper_with_meta(
    server_filters: Optional[Dict[str, str]] = None,
    max_rows: Optional[int] = None,
    screener_cfg: Optional[Dict[str, Any]] = None,
    filter_codes: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fast token-free Finviz HTML scrape with scrape_ok / error metadata.
    """
    cfg = screener_cfg or {}
    scraper_cfg = cfg.get("scraper", {}) if isinstance(cfg.get("scraper"), dict) else {}
    timeout = float(scraper_cfg.get("request_timeout_seconds", 8))
    page_sleep = float(scraper_cfg.get("page_sleep_seconds", 0.15))
    max_pages = max(1, int(scraper_cfg.get("max_pages", 15)))
    max_workers = max(1, int(scraper_cfg.get("max_workers", 1)))
    sort = str(scraper_cfg.get("sort", "-relativevolume")).strip() or "-relativevolume"
    codes = filter_codes or filters_dict_to_codes(server_filters)
    row_cap = max_rows if max_rows is not None and max_rows > 0 else 300

    started = time.perf_counter()
    meta: Dict[str, Any] = {
        "provider": "scraper",
        "scrape_ok": True,
        "scrape_error": None,
        "elapsed_sec": 0.0,
        "raw": 0,
    }
    try:
        disable_proxy_env_if_present()
        first_rows, total_pages = _fetch_screener_page(codes, 1, timeout, sort=sort)
        if not first_rows:
            elapsed = time.perf_counter() - started
            meta["elapsed_sec"] = round(elapsed, 3)
            meta["raw"] = 0
            print(f"[finviz_screener] scraper returned 0 rows in {elapsed:.2f}s (provider=scraper)")
            return [], meta

        pages_needed = min(max_pages, max(1, (row_cap + PAGE_SIZE - 1) // PAGE_SIZE))
        if total_pages > 0:
            pages_needed = min(pages_needed, total_pages)

        all_rows = list(first_rows)
        if len(all_rows) < PAGE_SIZE or pages_needed <= 1:
            result = all_rows[:row_cap]
            elapsed = time.perf_counter() - started
            meta["elapsed_sec"] = round(elapsed, 3)
            meta["raw"] = len(result)
            print(
                f"[finviz_screener] scraper returned {len(result)} rows in {elapsed:.2f}s "
                f"(provider=scraper, pages=1/{total_pages or 1}, sort={sort})"
            )
            return result, meta

        starts = [1 + i * PAGE_SIZE for i in range(1, pages_needed)]
        page_results: Dict[int, List[Dict[str, Any]]] = {}

        def _load(start: int) -> Tuple[int, List[Dict[str, Any]]]:
            if page_sleep > 0:
                time.sleep(page_sleep)
            rows, _ = _fetch_screener_page(codes, start, timeout, sort=sort)
            return start, rows

        with ThreadPoolExecutor(max_workers=min(max_workers, len(starts))) as pool:
            futures = [pool.submit(_load, start) for start in starts]
            for future in as_completed(futures):
                start, rows = future.result()
                page_results[start] = rows

        for start in starts:
            page_rows = page_results.get(start, [])
            if not page_rows:
                break
            all_rows.extend(page_rows)
            if len(page_rows) < PAGE_SIZE or len(all_rows) >= row_cap:
                break

        result = all_rows[:row_cap]
        elapsed = time.perf_counter() - started
        pages_got = 1 + sum(1 for s in starts if page_results.get(s))
        meta["elapsed_sec"] = round(elapsed, 3)
        meta["raw"] = len(result)
        print(
            f"[finviz_screener] scraper returned {len(result)} rows in {elapsed:.2f}s "
            f"(provider=scraper, pages={pages_got}/{total_pages or pages_got}, sort={sort})"
        )
        return result, meta
    except Exception as error:
        import traceback

        elapsed = time.perf_counter() - started
        summary = f"{type(error).__name__}: {error}"
        tb = traceback.format_exc(limit=3)
        meta["elapsed_sec"] = round(elapsed, 3)
        meta["scrape_ok"] = False
        meta["scrape_error"] = summary
        meta["raw"] = 0
        print(f"[finviz_screener] Scraper fetch failed after {elapsed:.2f}s: {error}")
        print(f"[path_a][finviz] scrape failed: {summary}\n{tb}")
        return [], meta


def fetch_finviz_rows(
    server_filters: Optional[Dict[str, str]] = None,
    max_rows: Optional[int] = None,
    screener_cfg: Optional[Dict[str, Any]] = None,
    filter_codes: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Download screener rows. Default provider is scraper (token-free).

    Finviz Elite is not used by default (too unreliable). Only provider
    ``elite`` forces the Elite CSV API; everything else uses HTML scrape.
    """
    rows, _meta = fetch_finviz_rows_with_meta(
        server_filters=server_filters,
        max_rows=max_rows,
        screener_cfg=screener_cfg,
        filter_codes=filter_codes,
    )
    return rows


def fetch_finviz_rows_with_meta(
    server_filters: Optional[Dict[str, str]] = None,
    max_rows: Optional[int] = None,
    screener_cfg: Optional[Dict[str, Any]] = None,
    filter_codes: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Like fetch_finviz_rows but also returns scrape metadata."""
    cfg = screener_cfg or {}
    provider = str(cfg.get("provider", "scraper")).lower().strip()

    if provider == "elite":
        rows = fetch_finviz_rows_elite(screener_cfg=cfg, max_rows=max_rows)
        if rows:
            print(f"[finviz_screener] Elite API returned {len(rows)} rows")
            return rows, {
                "provider": "elite",
                "scrape_ok": True,
                "scrape_error": None,
                "raw": len(rows),
                "elapsed_sec": None,
            }
        print("[finviz_screener] Elite API unavailable — falling back to scraper")

    return fetch_finviz_rows_scraper_with_meta(
        server_filters=server_filters,
        max_rows=max_rows,
        screener_cfg=cfg,
        filter_codes=filter_codes,
    )


def screen_quiet_stocks(
    price_change_min: float = -0.5,
    price_change_max: float = 0.5,
    volume_multiplier: float = 1.5,
    market_cap_max_billion: Optional[float] = 2.0,
    max_rows: int = 200,
    screener_cfg: Optional[Dict[str, Any]] = None,
    *,
    market_cap_min_billion: float = 0.0,
    require_optionable: bool = False,
    universe_label: str = "quiet-cap",
) -> List[Dict[str, Any]]:
    """Find stocks near 0% move with unusual volume (optionally mid/large)."""
    filtered, _stats = screen_quiet_stocks_with_stats(
        price_change_min=price_change_min,
        price_change_max=price_change_max,
        volume_multiplier=volume_multiplier,
        market_cap_max_billion=market_cap_max_billion,
        max_rows=max_rows,
        screener_cfg=screener_cfg,
        market_cap_min_billion=market_cap_min_billion,
        require_optionable=require_optionable,
        universe_label=universe_label,
    )
    return filtered


def _row_to_candidate(
    row: Dict[str, Any],
    *,
    price_change_min: float,
    price_change_max: float,
    volume_multiplier: float,
    market_cap_min: float,
    market_cap_max: Optional[float],
    universe_tier: str,
) -> Optional[Dict[str, Any]]:
    """Apply local Path A filters to one Finviz row; return candidate or None."""
    ticker = str(row.get("Ticker", "")).strip().upper()
    company_name = str(row.get("Company", "")).strip()
    current_price = parse_number_with_suffix(row.get("Price"))
    percent_change = parse_percent(row.get("Change"))
    current_volume = parse_number_with_suffix(row.get("Volume", row.get("Current Volume")))
    average_volume = parse_number_with_suffix(
        row.get("Average Volume", row.get("Avg Volume", row.get("Avg Vol")))
    )
    rel_volume_col = parse_number_with_suffix(row.get("Rel Volume", row.get("Relative Volume")))
    market_cap = parse_number_with_suffix(row.get("Market Cap.", row.get("Market Cap")))

    if not ticker:
        return None
    if percent_change < price_change_min or percent_change > price_change_max:
        return None
    if average_volume > 0 and current_volume < (average_volume * volume_multiplier):
        return None
    if market_cap <= 0:
        return None
    if market_cap < market_cap_min:
        return None
    if market_cap_max is not None and market_cap > market_cap_max:
        return None

    if average_volume > 0:
        relative_volume = round(current_volume / average_volume, 2)
    elif rel_volume_col > 0:
        relative_volume = round(rel_volume_col, 2)
    else:
        relative_volume = None

    return {
        "ticker": ticker,
        "company_name": company_name,
        "current_price": round(current_price, 4),
        "percent_change": round(percent_change, 4),
        "volume": int(current_volume),
        "average_volume": int(average_volume) if average_volume > 0 else None,
        "relative_volume": relative_volume,
        "market_cap": int(market_cap) if market_cap > 0 else None,
        "market_cap_billion": round(market_cap / 1_000_000_000, 3) if market_cap > 0 else None,
        "universe_tier": universe_tier,
        "source": "news",
    }


def screen_quiet_stocks_with_stats(
    price_change_min: float = -0.5,
    price_change_max: float = 0.5,
    volume_multiplier: float = 1.5,
    market_cap_max_billion: Optional[float] = 2.0,
    max_rows: int = 200,
    screener_cfg: Optional[Dict[str, Any]] = None,
    *,
    market_cap_min_billion: float = 0.0,
    require_optionable: bool = False,
    universe_label: str = "quiet-cap",
    universe_tier: str = "small_quiet",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Quiet-cap screen with Finviz observability stats for Path A health.
    """
    filter_codes = build_quiet_filter_codes(
        market_cap_max_billion=market_cap_max_billion,
        market_cap_min_billion=market_cap_min_billion,
        require_optionable=require_optionable,
    )
    rows, fetch_meta = fetch_finviz_rows_with_meta(
        server_filters=build_finviz_server_filters(
            price_change_min=price_change_min,
            price_change_max=price_change_max,
            market_cap_max_billion=market_cap_max_billion,
            market_cap_min_billion=market_cap_min_billion,
            require_optionable=require_optionable,
        ),
        max_rows=max_rows,
        screener_cfg=screener_cfg,
        filter_codes=filter_codes,
    )
    filtered: List[Dict[str, Any]] = []
    market_cap_min = float(market_cap_min_billion or 0.0) * 1_000_000_000
    market_cap_max = (
        float(market_cap_max_billion) * 1_000_000_000
        if market_cap_max_billion is not None
        else None
    )

    for row in rows:
        candidate = _row_to_candidate(
            row,
            price_change_min=price_change_min,
            price_change_max=price_change_max,
            volume_multiplier=volume_multiplier,
            market_cap_min=market_cap_min,
            market_cap_max=market_cap_max,
            universe_tier=universe_tier,
        )
        if candidate:
            filtered.append(candidate)

    cap_label = (
        f"cap≤{market_cap_max_billion}B"
        if market_cap_max_billion is not None
        else f"cap≥{market_cap_min_billion}B"
    )
    print(
        f"[finviz_screener] {universe_label} filter: {len(filtered)} matches "
        f"from {len(rows)} scraped rows (±{abs(price_change_max)}% change, "
        f"{cap_label}, vol×{volume_multiplier}, codes={filter_codes})"
    )
    stats = {
        "raw": int(fetch_meta.get("raw") if fetch_meta.get("raw") is not None else len(rows)),
        "after_filters": len(filtered),
        "scrape_ok": bool(fetch_meta.get("scrape_ok", True)),
        "scrape_error": fetch_meta.get("scrape_error"),
        "provider": str(fetch_meta.get("provider") or "scraper"),
        "elapsed_sec": fetch_meta.get("elapsed_sec"),
        "filter_codes": filter_codes,
        "universe_tier": universe_tier,
    }
    return filtered, stats


def screen_path_a_universe_with_stats(
    price_change_min: float = -0.5,
    price_change_max: float = 0.5,
    volume_multiplier: float = 1.5,
    market_cap_max_billion: float = 2.0,
    max_rows: int = 200,
    screener_cfg: Optional[Dict[str, Any]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Path A discovery: quiet small-cap scan + optional mid/large catalyst scan.

    Mid/large names use a wider price band (catalyst movers) and prefer
    optionable names so the existing liquidity floor sees real chains.
    Downstream scoring/HIGH_ALERT/gates are unchanged — this only widens the pool.
    """
    cfg = screener_cfg or {}
    quiet, quiet_stats = screen_quiet_stocks_with_stats(
        price_change_min=price_change_min,
        price_change_max=price_change_max,
        volume_multiplier=volume_multiplier,
        market_cap_max_billion=market_cap_max_billion,
        max_rows=max_rows,
        screener_cfg=cfg,
        universe_label="quiet-small-cap",
        universe_tier="small_quiet",
    )

    include_mid_large = bool(cfg.get("include_mid_large_cap", True))
    mid_cfg = cfg.get("mid_large") if isinstance(cfg.get("mid_large"), dict) else {}
    mid_rows: List[Dict[str, Any]] = []
    mid_stats: Dict[str, Any] = {
        "raw": 0,
        "after_filters": 0,
        "scrape_ok": True,
        "scrape_error": None,
        "provider": "skipped",
        "elapsed_sec": 0.0,
        "universe_tier": "mid_large_catalyst",
    }

    if include_mid_large:
        mid_min = float(mid_cfg.get("market_cap_min_billion", market_cap_max_billion))
        mid_price_min = float(mid_cfg.get("price_change_min", -8.0))
        mid_price_max = float(mid_cfg.get("price_change_max", 8.0))
        mid_vol_mult = float(mid_cfg.get("volume_multiplier", volume_multiplier))
        mid_max_rows = int(mid_cfg.get("finviz_max_rows", max(80, max_rows // 2)))
        require_optionable = bool(mid_cfg.get("require_optionable", True))
        mid_rows, mid_stats = screen_quiet_stocks_with_stats(
            price_change_min=mid_price_min,
            price_change_max=mid_price_max,
            volume_multiplier=mid_vol_mult,
            market_cap_max_billion=None,
            market_cap_min_billion=mid_min,
            require_optionable=require_optionable,
            max_rows=mid_max_rows,
            screener_cfg=cfg,
            universe_label="mid-large-catalyst",
            universe_tier="mid_large_catalyst",
        )

    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()
    mid_first = list(mid_rows)
    quiet_rest = list(quiet)
    for stock in mid_first + quiet_rest:
        ticker = str(stock.get("ticker") or "").upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        merged.append(stock)

    # Keep both tiers after the hard watchlist cap (mid/large alone would crowd out small-caps).
    max_symbols = int(cfg.get("max_watchlist_symbols", 0) or 0)
    small_share = float(cfg.get("small_quiet_watchlist_share", 0.4))
    small_share = min(0.8, max(0.0, small_share))
    if max_symbols > 0 and len(merged) > max_symbols:
        mid_only = [x for x in merged if str(x.get("universe_tier")) == "mid_large_catalyst"]
        small_only = [x for x in merged if str(x.get("universe_tier")) == "small_quiet"]
        other = [
            x
            for x in merged
            if str(x.get("universe_tier")) not in {"mid_large_catalyst", "small_quiet"}
        ]
        small_slots = min(len(small_only), int(round(max_symbols * small_share))) if small_only else 0
        if small_only and small_slots == 0 and small_share > 0:
            small_slots = 1
        mid_slots = max_symbols - small_slots
        balanced = mid_only[:mid_slots] + small_only[:small_slots]
        if len(balanced) < max_symbols:
            leftovers = mid_only[mid_slots:] + small_only[small_slots:] + other
            for stock in leftovers:
                if len(balanced) >= max_symbols:
                    break
                balanced.append(stock)
        merged = balanced

    scrape_ok = bool(quiet_stats.get("scrape_ok", True)) and bool(mid_stats.get("scrape_ok", True))
    scrape_error = quiet_stats.get("scrape_error") or mid_stats.get("scrape_error")
    elapsed_bits = [
        float(x)
        for x in (quiet_stats.get("elapsed_sec"), mid_stats.get("elapsed_sec"))
        if isinstance(x, (int, float))
    ]
    mid_kept = sum(1 for x in merged if str(x.get("universe_tier")) == "mid_large_catalyst")
    small_kept = sum(1 for x in merged if str(x.get("universe_tier")) == "small_quiet")
    print(
        f"[finviz_screener] Path A universe merge: {len(merged)} unique "
        f"(small_quiet={len(quiet)}→{small_kept}, mid_large={len(mid_rows)}→{mid_kept}, "
        f"include_mid_large={include_mid_large}, cap={max_symbols or 'none'})"
    )
    stats = {
        "raw": int(quiet_stats.get("raw") or 0) + int(mid_stats.get("raw") or 0),
        "after_filters": len(merged),
        "scrape_ok": scrape_ok,
        "scrape_error": scrape_error,
        "provider": str(quiet_stats.get("provider") or mid_stats.get("provider") or "scraper"),
        "elapsed_sec": round(sum(elapsed_bits), 3) if elapsed_bits else None,
        "small_quiet": {
            "raw": quiet_stats.get("raw"),
            "after_filters": quiet_stats.get("after_filters"),
            "filter_codes": quiet_stats.get("filter_codes"),
            "kept": small_kept,
        },
        "mid_large": {
            "raw": mid_stats.get("raw"),
            "after_filters": mid_stats.get("after_filters"),
            "filter_codes": mid_stats.get("filter_codes"),
            "enabled": include_mid_large,
            "kept": mid_kept,
        },
        "mid_large_count": len(mid_rows),
        "small_quiet_count": len(quiet),
        "mid_large_kept": mid_kept,
        "small_quiet_kept": small_kept,
    }
    return merged, stats


def print_screen_results(stocks: List[Dict[str, Any]]) -> None:
    """
    Print screened stocks in a simple readable console table.

    Inputs:
    - stocks: list of stock dictionaries returned by screen_quiet_stocks.

    Output:
    - None. This function prints to the terminal.

    Why this exists:
    - Beginners need human-readable output to quickly verify filtering
      logic before integrating this module into the full pipeline.
    """
    if not stocks:
        print("No matching stocks found right now.")
        return

    print("-" * 110)
    print(f"{'Ticker':<8} {'Company':<40} {'Price':>10} {'%Change':>10} {'Volume':>18}")
    print("-" * 110)
    for stock in stocks:
        print(
            f"{stock['ticker']:<8} "
            f"{stock['company_name'][:40]:<40} "
            f"{stock['current_price']:>10.2f} "
            f"{stock['percent_change']:>10.2f} "
            f"{stock['volume']:>18,}"
        )
    print("-" * 110)
    print(f"Total matches: {len(stocks)}")


def main() -> None:
    """
    Run the FinViz screener demo when this file is executed directly.

    Inputs:
    - None.

    Output:
    - None. Prints table output to the terminal.

    Why this exists:
    - A direct-run test lets us validate Step 2 in isolation before
      wiring this function into the full agent scheduler.
    """
    matches = screen_quiet_stocks()
    print_screen_results(matches)


if __name__ == "__main__":
    main()
