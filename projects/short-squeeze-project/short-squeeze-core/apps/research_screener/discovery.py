"""Current discovery candidates and the discovery profiles that produce them.

A :class:`CurrentDiscoveryCandidate` is an **application-session** object. It is not a
Batch 01 research case, it carries no case identity, it is never outcome-labelled, and it
never enters any research registry. Historical research statistics and current screen
statistics are reported separately and are never summed.

Discovery profiles are transparent: each one states the exact provider scanner
configuration it issues, and the price bounds of the rubric-like profile are read from the
committed Phase 3A ``PRICE_RANGE`` thresholds rather than invented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

#: The label every current-discovery surface must carry.
DISCOVERY_LABEL = "CURRENT DISCOVERY"

#: What the label explicitly is not.
DISCOVERY_DISCLAIMER = (
    "Current discovery candidates. No predictive validity is claimed; this is not a "
    "validated squeeze scanner."
)

#: Scanner rows requested. Kept modest so a full evidence sweep of the screen completes
#: inside the provider's rolling historical-data pacing window.
DEFAULT_ROW_LIMIT = 15
SCANNER_TIMEOUT_S = 10.0


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    """Exactly what is sent to the provider's scanner. Nothing hidden, nothing weighted."""

    instrument: str = "STK"
    location_code: str = "STK.US.MAJOR"
    scan_code: str = "TOP_PERC_GAIN"
    number_of_rows: int = DEFAULT_ROW_LIMIT
    # Price bounds are the committed policy's own threshold objects, passed through
    # untouched. They are deliberately not typed as a numeric: this package performs no
    # metric arithmetic, and a committed guard asserts the name never appears here.
    above_price: Any = None
    below_price: Any = None
    above_volume: int | None = None
    market_cap_below: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "locationCode": self.location_code,
            "scanCode": self.scan_code,
            "numberOfRows": self.number_of_rows,
            "abovePrice": None if self.above_price is None else str(self.above_price),
            "belowPrice": None if self.below_price is None else str(self.below_price),
            "aboveVolume": self.above_volume,
            "marketCapBelow": self.market_cap_below,
        }

    def to_subscription(self):
        """Build the official ``ScannerSubscription``. Only documented fields are set."""
        from ibapi.scanner import ScannerSubscription

        subscription = ScannerSubscription()
        subscription.instrument = self.instrument
        subscription.locationCode = self.location_code
        subscription.scanCode = self.scan_code
        subscription.numberOfRows = self.number_of_rows
        if self.above_price is not None:
            subscription.abovePrice = float(self.above_price)
        if self.below_price is not None:
            subscription.belowPrice = float(self.below_price)
        if self.above_volume is not None:
            subscription.aboveVolume = int(self.above_volume)
        if self.market_cap_below is not None:
            subscription.marketCapBelow = int(self.market_cap_below)
        return subscription


@dataclass(frozen=True, slots=True)
class DiscoveryProfile:
    """A named discovery configuration plus the plain-language criteria it declares."""

    profile_id: str
    title: str
    purpose: str
    criteria: tuple[str, ...]
    scanner: ScannerConfig | None
    uses_provider_scanner: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "title": self.title,
            "purpose": self.purpose,
            "criteria": list(self.criteria),
            "scanner_config": None if self.scanner is None else self.scanner.as_dict(),
            "uses_provider_scanner": self.uses_provider_scanner,
            "label": DISCOVERY_LABEL,
            "disclaimer": DISCOVERY_DISCLAIMER,
            "ordering": "Provider scanner order",
        }


def price_range_bounds(policy) -> tuple[Any, Any]:
    """Read the committed ``PRICE_RANGE`` bounds. No number is invented here."""
    from squeeze_core.evaluation.models import ThresholdOperator

    for rule in policy.rules:
        if rule.rule_id != "PRICE_RANGE":
            continue
        low = next(
            (t.value for t in rule.thresholds
             if t.operator is ThresholdOperator.GREATER_THAN_OR_EQUAL), None
        )
        high = next(
            (t.value for t in rule.thresholds
             if t.operator is ThresholdOperator.LESS_THAN_OR_EQUAL), None
        )
        return low, high
    return None, None


def build_profiles(policy=None) -> dict[str, DiscoveryProfile]:
    """The discovery profiles offered by the application, in display order."""
    low, high = (None, None) if policy is None else price_range_bounds(policy)
    rubric_criteria = [
        "US equities on major exchanges (provider location STK.US.MAJOR).",
        "Provider scan class TOP_PERC_GAIN (largest percentage gainers).",
    ]
    if low is not None and high is not None:
        rubric_criteria.append(
            f"Price between {low} and {high}, read directly from the committed Phase 3A "
            "PRICE_RANGE thresholds — not a number chosen here."
        )
    rubric_criteria.append(
        "No short-interest, borrow, float or catalyst filter is applied, because no "
        "provider supplies those fields to the scanner."
    )
    rubric_criteria.append(
        "Approximating the original workflow's discovery step."
    )

    profiles = [
        DiscoveryProfile(
            profile_id="BROAD_MOVERS",
            title="Broad movers",
            purpose="Find active US stocks that are currently moving, for current research evaluation.",
            criteria=(
                "US equities on major exchanges (provider location STK.US.MAJOR).",
                "Provider scan class TOP_PERC_GAIN (largest percentage gainers).",
                "No price, capitalisation or volume filter — deliberately unfiltered.",
                "Ordering is the provider's scanner order.",
            ),
            scanner=ScannerConfig(scan_code="TOP_PERC_GAIN"),
        ),
        DiscoveryProfile(
            profile_id="MOST_ACTIVE",
            title="Most active",
            purpose="Find the most actively traded US equities currently reported by the provider.",
            criteria=(
                "US equities on major exchanges (provider location STK.US.MAJOR).",
                "Provider scan class MOST_ACTIVE.",
                "Activity here is the provider's own definition; the project's own volume "
                "semantics remain unresolved and no volume rule is evaluated from it.",
            ),
            scanner=ScannerConfig(scan_code="MOST_ACTIVE"),
        ),
        DiscoveryProfile(
            profile_id="HISTORICAL_RUBRIC_LIKE",
            title="Historical-rubric-like",
            purpose=(
                "Approximate the original operational workflow's discovery step, using only "
                "criteria the current provider actually supports."
            ),
            criteria=tuple(rubric_criteria),
            scanner=ScannerConfig(
                scan_code="TOP_PERC_GAIN", above_price=low, below_price=high
            ),
        ),
        DiscoveryProfile(
            profile_id="FINVIZ_SCREENER",
            title="Finviz Elite Screener",
            purpose="Candidates sourced directly from the Finviz Elite export screener — no IBKR scanner required. Provides float, short float, relative volume, and more for every symbol.",
            criteria=(
                "US equities from the Finviz Elite export API.",
                "Filter: short float < 50%, price < $50 (sh_float_u50,sh_price_u50).",
                "Every symbol carries provider-supplied fundamentals: float, short float, "
                "short ratio, relative volume, market cap, RSI, sector, and industry.",
                "No IBKR connection required for these candidates. They enrich the screen "
                "alongside IBKR-discovered symbols.",
            ),
            scanner=None,
            uses_provider_scanner=False,
        ),
        DiscoveryProfile(
            profile_id="MANUAL_SYMBOL",
            title="Manual symbol",
            purpose="Evaluate specific tickers you enter yourself.",
            criteria=(
                "No scanner is used. The symbols are exactly the ones you type.",
                "Each symbol is resolved to a US equity contract before any request is issued.",
            ),
            scanner=None,
            uses_provider_scanner=False,
        ),
    ]
    return {profile.profile_id: profile for profile in profiles}


@dataclass(slots=True)
class CurrentDiscoveryCandidate:
    """One current-session candidate."""

    symbol: str
    profile_id: str
    con_id: int | None = None
    long_name: str = ""
    primary_exchange: str = ""
    currency: str = ""
    provider_rank: int | None = None
    first_seen_at: str = field(default_factory=_now_iso)
    discovered_at: str = field(default_factory=_now_iso)
    in_current_scan: bool = True

    @property
    def candidate_key(self) -> str:
        """Deterministic within a snapshot: contract identity when known, else symbol."""
        return f"{self.profile_id}:{self.symbol}:{self.con_id if self.con_id else 'UNRESOLVED'}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "candidate_key": self.candidate_key,
            "discovery_profile": self.profile_id,
            "con_id": self.con_id,
            "long_name": self.long_name,
            "primary_exchange": self.primary_exchange,
            "currency": self.currency,
            "provider_scanner_order": self.provider_rank,
            "first_seen_at": self.first_seen_at,
            "discovered_at": self.discovered_at,
            "in_current_scan": self.in_current_scan,
            # Explicitly absent, by construction:
            "case_id": None,
            "outcome": None,
            "research_registry_member": False,
        }


def candidates_from_scanner(
    rows, profile_id: str, *, limit: int = DEFAULT_ROW_LIMIT
) -> list[CurrentDiscoveryCandidate]:
    """Turn provider scanner rows into candidates, preserving provider order."""
    out: list[CurrentDiscoveryCandidate] = []
    seen: set[str] = set()
    for row in rows:
        symbol = (row.symbol or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        if row.sec_type and row.sec_type != "STK":
            continue
        seen.add(symbol)
        out.append(
            CurrentDiscoveryCandidate(
                symbol=symbol,
                profile_id=profile_id,
                con_id=row.con_id or None,
                long_name=row.long_name,
                primary_exchange=row.primary_exchange,
                currency=row.currency,
                provider_rank=row.rank,
            )
        )
        if len(out) >= limit:
            break
    return out


__all__ = [
    "DEFAULT_ROW_LIMIT",
    "DISCOVERY_DISCLAIMER",
    "DISCOVERY_LABEL",
    "SCANNER_TIMEOUT_S",
    "CurrentDiscoveryCandidate",
    "DiscoveryProfile",
    "ScannerConfig",
    "build_profiles",
    "candidates_from_scanner",
    "price_range_bounds",
]
