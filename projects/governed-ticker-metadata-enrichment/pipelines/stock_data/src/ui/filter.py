"""Ticker filtering — interactive prompt + CLI flag parser.

A `FilterSpec` is the canonical, declarative representation of a ticker
filter. It is independent of the UI used to construct it, so the same
spec can come from `parse_filter_args` (CLI flags) or
`prompt_for_filters` (rich prompts). Filters run against the `tickers`
master table and return a list of `{"id", "ticker"}` dicts — the same
shape that `src.scrapers.base.BaseScraper._get_pending_items` consumes.

Supported columns on `tickers`:
    exchange, sector, industry, country, is_etf, market_cap, ticker,
    company_name, ipo_year, is_active

SQL is generated via `to_sql` with named bind parameters so the call
goes through SQLAlchemy's normal parameterization (no string
interpolation; SQL-injection-safe for caller-supplied regex).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rich.prompt import Confirm, Prompt
from sqlalchemy.sql import text

from src.database import get_connection
from src.ui._styles import COLOR_BRAND_PRIMARY, console


# ── Public dataclass ──────────────────────────────────────────


@dataclass(frozen=True)
class FilterSpec:
    """Declarative ticker filter.

    All fields are optional; an empty FilterSpec matches every active
    ticker. Multi-value fields use OR semantics within the same column
    (e.g., sectors=[\"Tech\",\"Finance\"] matches tickers in either).
    """
    exchanges: Tuple[str, ...] = ()
    sectors: Tuple[str, ...] = ()
    industries: Tuple[str, ...] = ()
    countries: Tuple[str, ...] = ()
    is_etf: Optional[bool] = None
    min_market_cap: Optional[float] = None
    max_market_cap: Optional[float] = None
    ticker_regex: Optional[str] = None
    company_name_regex: Optional[str] = None
    limit: Optional[int] = None

    def __bool__(self) -> bool:
        """`True` if any filter is set (i.e., not the empty/none match)."""
        return any([
            self.exchanges, self.sectors, self.industries, self.countries,
            self.is_etf is not None,
            self.min_market_cap is not None,
            self.max_market_cap is not None,
            self.ticker_regex, self.company_name_regex,
            self.limit is not None,
        ])

    def describe(self) -> str:
        """One-line human description of the filter (for confirmations)."""
        parts: List[str] = []
        if self.exchanges:
            parts.append(f"exchange IN ({','.join(self.exchanges)})")
        if self.sectors:
            parts.append(f"sector IN ({','.join(self.sectors)})")
        if self.industries:
            parts.append(f"industry IN ({','.join(self.industries)})")
        if self.countries:
            parts.append(f"country IN ({','.join(self.countries)})")
        if self.is_etf is not None:
            parts.append(f"is_etf={self.is_etf}")
        if self.min_market_cap is not None:
            parts.append(f"market_cap>={_format_money(self.min_market_cap)}")
        if self.max_market_cap is not None:
            parts.append(f"market_cap<={_format_money(self.max_market_cap)}")
        if self.ticker_regex:
            parts.append(f"ticker~/{self.ticker_regex}/")
        if self.company_name_regex:
            parts.append(f"company~/{self.company_name_regex}/")
        if self.limit is not None:
            parts.append(f"limit={self.limit}")
        return " AND ".join(parts) if parts else "(no filter — all active tickers)"

    def to_sql(self) -> Tuple[str, Dict[str, Any]]:
        """Build (WHERE_clause, params) for use with SQLAlchemy `text`."""
        clauses: List[str] = ["t.is_active = 1"]
        params: Dict[str, Any] = {}

        def _in(column: str, values: Sequence[str], prefix: str) -> None:
            placeholders = ", ".join(f":{prefix}_{i}" for i in range(len(values)))
            clauses.append(f"t.{column} IN ({placeholders})")
            for i, v in enumerate(values):
                params[f"{prefix}_{i}"] = v

        if self.exchanges:
            _in("exchange", self.exchanges, "ex")
        if self.sectors:
            _in("sector", self.sectors, "sec")
        if self.industries:
            _in("industry", self.industries, "ind")
        if self.countries:
            _in("country", self.countries, "co")

        if self.is_etf is not None:
            clauses.append("t.is_etf = :is_etf")
            params["is_etf"] = bool(self.is_etf)

        if self.min_market_cap is not None:
            clauses.append("t.market_cap >= :min_cap")
            params["min_cap"] = self.min_market_cap
        if self.max_market_cap is not None:
            clauses.append("t.market_cap <= :max_cap")
            params["max_cap"] = self.max_market_cap

        if self.ticker_regex:
            clauses.append("t.ticker REGEXP :ticker_re")
            params["ticker_re"] = self.ticker_regex
        if self.company_name_regex:
            clauses.append("(t.company_name REGEXP :company_re "
                           "OR t.company_name LIKE :company_like)")
            params["company_re"] = self.company_name_regex
            params["company_like"] = f"%{self.company_name_regex}%"

        return " AND ".join(clauses), params


# ── Money / numeric helpers ───────────────────────────────────


_MULTIPLIERS = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}


def _parse_money(s: str) -> Optional[float]:
    """Parse `"1B"`, `"$500M"`, `"100K"`, `"123"` into a dollar numeric.

    Returns `None` for empty or unparseable input. Case-insensitive.
    """
    if s is None:
        return None
    cleaned = str(s).strip().upper().replace("$", "").replace(",", "").replace(" ", "")
    if not cleaned:
        return None
    if cleaned[-1] in _MULTIPLIERS:
        try:
            return float(cleaned[:-1]) * _MULTIPLIERS[cleaned[-1]]
        except ValueError:
            return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _format_money(value: float) -> str:
    """Format a dollar amount compactly (`1.5B`, `320M`, `5K`)."""
    if value is None:
        return "—"
    for suffix, mult in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= mult:
            return f"${value / mult:.2f}{suffix}".rstrip("0").rstrip(".")
    return f"${value:,.0f}"


def _split_csv(value: Optional[str]) -> List[str]:
    """Split a comma-separated string into a list of stripped strings."""
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


# ── Apply filter against the database ─────────────────────────


def apply_filter(spec: FilterSpec) -> List[Dict[str, Any]]:
    """Return `[{id, ticker}, ...]` matching the spec from the tickers table."""
    where, params = spec.to_sql()
    sql = f"SELECT t.id, t.ticker FROM tickers t WHERE {where} ORDER BY t.ticker"
    if spec.limit:
        sql += f" LIMIT {int(spec.limit)}"
    with get_connection() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [{"id": r[0], "ticker": r[1]} for r in rows]


def count_filter(spec: FilterSpec) -> int:
    """Return the number of tickers matching the spec (without LIMIT)."""
    saved = spec.limit  # ensure no LIMIT for counting
    object.__setattr__(spec, "limit", None)
    where, params = spec.to_sql()
    object.__setattr__(spec, "limit", saved)  # restore
    sql = f"SELECT COUNT(*) FROM tickers t WHERE {where}"
    with get_connection() as conn:
        row = conn.execute(text(sql), params).fetchone()
    return int(row[0]) if row else 0


# ── CLI flag parser ───────────────────────────────────────────


def parse_filter_args(args) -> FilterSpec:
    """Build a `FilterSpec` from argparse-style namespace (or dict).

    Recognised attributes (all optional, accessed via `getattr`):
        --exchange, --sector, --industry, --country
        --is-etf (None|"yes"|"no"|True|False)
        --min-cap, --max-cap  (e.g., "1B", "500M")
        --ticker-regex, --company-regex
        --limit (int)
    """
    if isinstance(args, dict):
        g = args.get
    else:
        g = lambda k, default=None: getattr(args, k, default)

    is_etf_raw = g("is_etf", None) or g("is_etf_flag", None)
    is_etf = _parse_is_etf(is_etf_raw)

    return FilterSpec(
        exchanges=tuple(_split_csv(g("exchange"))),
        sectors=tuple(_split_csv(g("sector"))),
        industries=tuple(_split_csv(g("industry"))),
        countries=tuple(_split_csv(g("country"))),
        is_etf=is_etf,
        min_market_cap=_parse_money(g("min_cap")),
        max_market_cap=_parse_money(g("max_cap")),
        ticker_regex=g("ticker_regex"),
        company_name_regex=g("company_regex"),
        limit=_parse_int(g("limit")),
    )


def _parse_is_etf(value) -> Optional[bool]:
    """Interpret the `--is-etf` flag value as `True`, `False`, or `None`."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    return None


def _parse_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


# ── Interactive wizard ────────────────────────────────────────


def prompt_for_filters(presets: Optional[FilterSpec] = None) -> Optional[FilterSpec]:
    """Multi-step filter wizard driven by `rich.prompt.Prompt.ask`.

    Enter on any prompt = skip / leave unchanged. After all steps the
    filter is shown and confirmed via `Confirm.ask`. Returns `None` if
    the user declines the confirmation or cancels at any step.
    """
    presets = presets or FilterSpec()
    console.print(f"\n[{COLOR_BRAND_PRIMARY}]Filter Tickers[/] "
                  "[dim](press Enter to skip each step)[/]")

    exchanges = _prompt_csv(
        "Exchanges",
        default=",".join(presets.exchanges),
        help_text="e.g., NASDAQ, NYSE (comma-separated)",
    )
    if exchanges is None:
        return None

    sectors = _prompt_csv(
        "Sectors",
        default=",".join(presets.sectors),
        help_text="e.g., Technology, Healthcare",
    )
    if sectors is None:
        return None

    countries = _prompt_csv(
        "Countries",
        default=",".join(presets.countries),
        help_text="e.g., United States, China",
    )
    if countries is None:
        return None

    etf_str = Prompt.ask(
        "Type (leave blank for both)",
        default="" if presets.is_etf is None else ("yes" if presets.is_etf else "no"),
        choices=["", "yes", "no"],
        show_choices=False,
    )
    is_etf = _parse_is_etf(etf_str) if etf_str else None

    cap_min = Prompt.ask(
        "Minimum market cap (e.g., 1B, 500M)",
        default=_format_money(presets.min_market_cap) if presets.min_market_cap is not None else "",
    )
    if cap_min == "":
        cap_min_val: Optional[float] = None
    else:
        cap_min_val = _parse_money(cap_min)
        if cap_min_val is None:
            console.print(f"  [yellow]Could not parse[/] {cap_min!r}; skipping.")

    cap_max = Prompt.ask(
        "Maximum market cap (e.g., 100B, blank=no limit)",
        default=_format_money(presets.max_market_cap) if presets.max_market_cap is not None else "",
    )
    cap_max_val = _parse_money(cap_max) if cap_max else None

    ticker_re_str = Prompt.ask(
        "Ticker regex (e.g., ^[A-C], ^AAPL$)",
        default=presets.ticker_regex or "",
    )
    try:
        if ticker_re_str:
            re.compile(ticker_re_str)
            ticker_regex = ticker_re_str
        else:
            ticker_regex = None
    except re.error as e:
        console.print(f"  [red]Invalid regex[/] '{ticker_re_str}': {e}. Skipping.")
        ticker_regex = None

    company_re_str = Prompt.ask(
        "Company name regex (e.g., Apple, Bank)",
        default=presets.company_name_regex or "",
    )
    if company_re_str:
        try:
            re.compile(company_re_str)
            company_regex: Optional[str] = company_re_str
        except re.error as e:
            console.print(f"  [red]Invalid regex[/] '{company_re_str}': {e}. Skipping.")
            company_regex = None
    else:
        company_regex = None

    limit_str = Prompt.ask(
        "Limit results (blank = no limit)",
        default=str(presets.limit) if presets.limit is not None else "",
    )
    limit_val = _parse_int(limit_str) if limit_str else None

    spec = FilterSpec(
        exchanges=tuple(exchanges),
        sectors=tuple(sectors),
        countries=tuple(countries),
        is_etf=is_etf,
        min_market_cap=cap_min_val,
        max_market_cap=cap_max_val,
        ticker_regex=ticker_regex,
        company_name_regex=company_regex,
        limit=limit_val,
    )
    console.print(f"\n[bold]Filter to apply:[/] {spec.describe()}")
    if not Confirm.ask("[bold]Run with this filter?[/]", default=True):
        return None
    return spec


def _prompt_csv(label: str, default: str, help_text: str = "") -> Optional[List[str]]:
    raw = Prompt.ask(
        f"[bold]{label}[/]" + (f" [dim]{help_text}[/]" if help_text else ""),
        default=default,
    )
    if raw is None:  # user cancelled (Ctrl+C)
        return None
    return _split_csv(raw)
