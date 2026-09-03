"""MODE B / MODE C — read-only current data from the local IB Gateway.

What this mode does: resolves a symbol's contract and retrieves recent completed
historical bars through the already-validated read-only session in
``tools.ibkr_historical_export``, then displays those observations with full provenance
and an explicit freshness age.

What this mode deliberately does **not** do: publish Phase 3A rule outcomes. Live bars
carry the same provider semantics that Batch 06 left UNRESOLVED (historical volume unit,
volume corporate-action treatment, intraday timestamp boundary) and they have never been
through the Batch 07 admissibility gate. Publishing rule outcomes over them would assert
an admissibility that has not been established, so every rule is reported ``UNKNOWN``
with that exact reason. The frozen research mode remains the only mode with published
rule outcomes.

No order method, no account method, no position, no balance. Localhost only.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from . import reasons
from .paths import repository_root
from .truth import DataMode, Freshness, FieldValue, ValueStatus, known, missing


def _ensure_tools_importable() -> None:
    """``tools/`` lives at the repository root and is not an installed package.

    Put the repository root on ``sys.path`` so the read-only IBKR session is importable
    regardless of the working directory the launcher was started from.
    """
    root = str(repository_root())
    if root not in sys.path:
        sys.path.insert(0, root)

#: Presentation-only freshness thresholds. They label a displayed age; they are not
#: research thresholds and they never affect a rule outcome.
FRESH_WITHIN_S = 300
STALE_AFTER_S = 1800

#: Read-only request shape for the current window.
LIVE_REQUEST_NAME = "CURRENT_CONTEXT_TRAILING_1D"
LIVE_DURATION = "1 D"
LIVE_BAR_SIZE = "1 min"
LIVE_WHAT_TO_SHOW = "TRADES"
LIVE_USE_RTH = 0
LIVE_FORMAT_DATE = 2
REQUEST_TIMEOUT_S = 30.0

#: The single reason every rule carries in live mode.
LIVE_RULES_NOT_PUBLISHED_CODE = "LIVE_EVIDENCE_NOT_ADMISSIBILITY_GATED"
LIVE_RULES_NOT_PUBLISHED_REASON = (
    "Current provider observations have not passed the Batch 07 admissibility gate and "
    "have not been frozen through the Phase 3A pipeline. Publishing a rule outcome over "
    "them would assert an admissibility that has not been established, so no outcome is "
    "published. Frozen Research mode carries the published outcomes."
)

#: Symbols must look like a plain equity ticker before any request is issued.
MAX_SYMBOL_LENGTH = 12


class LiveModeUnavailable(RuntimeError):
    """The local gateway could not be reached, or ``ibapi`` is not installed."""


class InvalidSymbolError(ValueError):
    """The requested symbol is not a plausible equity ticker."""


def normalize_symbol(raw: str) -> str:
    """Validate and upper-case a manually entered ticker."""
    candidate = (raw or "").strip().upper()
    if not candidate:
        raise InvalidSymbolError("Enter a ticker symbol.")
    if len(candidate) > MAX_SYMBOL_LENGTH:
        raise InvalidSymbolError(
            f"{candidate!r} is longer than {MAX_SYMBOL_LENGTH} characters; that is not a "
            "ticker symbol."
        )
    if not all(char.isalnum() or char in ".-" for char in candidate):
        raise InvalidSymbolError(
            f"{candidate!r} contains characters that are not valid in a ticker symbol."
        )
    return candidate


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def classify_freshness(age_seconds: float | None) -> Freshness:
    """Label an age. The raw age is always displayed alongside the label."""
    if age_seconds is None:
        return Freshness.UNKNOWN_AGE
    if age_seconds <= FRESH_WITHIN_S:
        return Freshness.CURRENT
    if age_seconds <= STALE_AFTER_S:
        return Freshness.DELAYED
    return Freshness.STALE


@dataclass(frozen=True, slots=True)
class LiveBar:
    """One completed provider bar, exactly as received."""

    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float


def _request_spec(end: datetime):
    _ensure_tools_importable()
    from tools.ibkr_historical_export.cohort import HistoricalRequestSpec

    return HistoricalRequestSpec(
        request_name=LIVE_REQUEST_NAME,
        end_datetime="",  # empty string = the provider's current time
        duration_str=LIVE_DURATION,
        bar_size_setting=LIVE_BAR_SIZE,
        what_to_show=LIVE_WHAT_TO_SHOW,
        use_rth=LIVE_USE_RTH,
        format_date=LIVE_FORMAT_DATE,
        keep_up_to_date=False,
        expected_window_start=end - timedelta(days=1),
        expected_window_end=end,
    )


class LiveSource:
    """One read-only gateway conversation. Always used as a context manager."""

    def __init__(self, *, timeout: float = REQUEST_TIMEOUT_S) -> None:
        self.timeout = timeout
        self._session = None
        self._connection: Any = None

    def __enter__(self) -> "LiveSource":
        _ensure_tools_importable()
        try:
            from tools.ibkr_historical_export.collector import probe_and_connect
            from tools.ibkr_historical_export.session import IbkrSession
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise LiveModeUnavailable(
                "The official IBKR API package is not importable in this environment, so "
                "current-data mode is unavailable. Frozen Research mode is unaffected."
            ) from exc
        session, result = probe_and_connect(IbkrSession)
        if session is None:
            raise LiveModeUnavailable(
                "No local IB Gateway / TWS API socket accepted a read-only connection. "
                "Start IB Gateway, or use Frozen Research mode."
            )
        self._session = session
        self._connection = result
        return self

    def __exit__(self, *exc_info) -> None:
        if self._session is not None:
            self._session.shutdown()
            self._session = None

    # ------------------------------------------------------------------ info

    def connection_info(self) -> dict[str, Any]:
        result = self._connection
        return {
            "status": str(getattr(result, "status", "UNKNOWN")),
            "port": getattr(result, "observed_port", None),
            "server_version": getattr(result, "server_version", None),
            "provider_current_time": (
                _iso(datetime.fromtimestamp(result.current_time_epoch, tz=UTC))
                if getattr(result, "current_time_epoch", None)
                else None
            ),
        }

    # -------------------------------------------------------------- symbol

    def collect(self, symbol: str) -> dict[str, Any]:
        """Resolve the contract and pull the trailing completed-bar window."""
        symbol = normalize_symbol(symbol)
        session = self._session
        if session is None:
            raise LiveModeUnavailable("Live source used outside its context manager.")

        candidates, contract_errors = session.request_contract_details(
            1, symbol, self.timeout
        )
        if not candidates:
            return {
                "symbol": symbol,
                "resolved": False,
                "reason": (
                    f"The provider returned no US equity contract for {symbol!r}. "
                    "Nothing was assumed and no value was substituted."
                ),
                "provider_errors": [
                    {"code": code, "message": message} for _rid, message, code in contract_errors
                ],
            }
        chosen = candidates[0]
        _ensure_tools_importable()
        from tools.ibkr_historical_export.session import make_conid_contract

        contract = make_conid_contract(chosen.con_id, symbol)
        spec = _request_spec(_now())
        bars, bar_errors, completed = session.request_historical(
            2, spec, symbol, chosen.con_id, contract, self.timeout
        )
        retrieved_at = _now()
        parsed = [
            LiveBar(
                timestamp_utc=bar.timestamp_utc,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
            )
            for bar in bars
        ]
        return {
            "symbol": symbol,
            "resolved": True,
            "con_id": chosen.con_id,
            "long_name": chosen.long_name,
            "primary_exchange": chosen.primary_exchange,
            "currency": chosen.currency,
            "request_name": LIVE_REQUEST_NAME,
            "request_completed": bool(completed),
            "bars": parsed,
            "retrieved_at": _iso(retrieved_at),
            "provider_errors": [
                {"code": code, "message": message} for _rid, message, code in bar_errors
            ],
        }


# --------------------------------------------------------------- presentation


def _live_missing(reason: str, code: str, status: ValueStatus = ValueStatus.UNAVAILABLE) -> FieldValue:
    return missing(status, reason, reason_code=code, provider="IBKR", data_mode=DataMode.UNAVAILABLE)


def build_live_row(collected: dict[str, Any]) -> dict[str, Any]:
    """Turn a collection result into a screener row with honest labels."""
    symbol = collected["symbol"]
    retrieved_at = collected.get("retrieved_at")

    if not collected.get("resolved"):
        unresolved = _live_missing(collected["reason"], "CONTRACT_NOT_RESOLVED")
        fields = {
            name: unresolved.as_dict()
            for name in (
                "reference_price", "percentage_change", "relative_volume", "float_shares",
                "short_float", "borrow_fee", "borrow_availability", "catalyst", "sentiment",
            )
        }
        return _live_row_envelope(symbol, fields, collected, bar_count=0, event_time=None,
                                  freshness=Freshness.NOT_APPLICABLE,
                                  data_mode=DataMode.UNAVAILABLE)

    bars: list[LiveBar] = collected["bars"]
    if not bars:
        empty = _live_missing(
            "The provider accepted the request but returned no completed bars for this "
            "window. No value was substituted.",
            "NO_BARS_RETURNED",
        )
        fields = {
            name: empty.as_dict()
            for name in (
                "reference_price", "percentage_change", "relative_volume", "float_shares",
                "short_float", "borrow_fee", "borrow_availability", "catalyst", "sentiment",
            )
        }
        return _live_row_envelope(symbol, fields, collected, bar_count=0, event_time=None,
                                  freshness=Freshness.NOT_APPLICABLE,
                                  data_mode=DataMode.UNAVAILABLE)

    last = bars[-1]
    event_time = last.timestamp_utc
    age = None
    try:
        parsed = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
        age = (_now() - parsed).total_seconds()
    except ValueError:
        age = None
    freshness = classify_freshness(age)

    price = known(
        round(last.close, 4),
        unit="PRICE",
        provider="IBKR",
        event_time=event_time,
        received_time=retrieved_at,
        freshness=freshness,
        data_mode=DataMode.HISTORICAL,
        evidence_id=f"live:{symbol}:{event_time}",
        readiness="NOT_ADMISSIBILITY_GATED",
    )
    fields = {
        "reference_price": price.as_dict(),
        "percentage_change": _live_missing(
            "No percentage change is published in current-data mode: the canonical "
            "metric path is only run over Batch 07-admissible evidence. "
            + LIVE_RULES_NOT_PUBLISHED_REASON,
            LIVE_RULES_NOT_PUBLISHED_CODE,
            ValueStatus.UNKNOWN,
        ).as_dict(),
        "relative_volume": _live_missing(
            reasons.BLOCKING_REASONS["VOLUME_SEMANTICS_BLOCKED_BY_BATCH07"],
            "VOLUME_SEMANTICS_BLOCKED_BY_BATCH07",
            ValueStatus.UNKNOWN,
        ).as_dict(),
        "float_shares": _live_missing(
            "No float provider is configured.", "FLOAT_NOT_CONFIGURED", ValueStatus.NOT_CONFIGURED
        ).as_dict(),
        "short_float": _live_missing(
            "No short-interest provider is configured.",
            "SHORT_FLOAT_NOT_CONFIGURED",
            ValueStatus.NOT_CONFIGURED,
        ).as_dict(),
        "borrow_fee": _live_missing(
            "No borrow-fee provider is configured.",
            "BORROW_FEE_NOT_CONFIGURED",
            ValueStatus.NOT_CONFIGURED,
        ).as_dict(),
        "borrow_availability": _live_missing(
            "No borrow-availability provider is configured.",
            "BORROW_AVAILABILITY_NOT_CONFIGURED",
            ValueStatus.NOT_CONFIGURED,
        ).as_dict(),
        "catalyst": _live_missing(
            "No news or filing provider is configured.",
            "CATALYST_NOT_CONFIGURED",
            ValueStatus.NOT_CONFIGURED,
        ).as_dict(),
        "sentiment": _live_missing(
            "No sentiment provider is configured.",
            "SENTIMENT_NOT_CONFIGURED",
            ValueStatus.NOT_CONFIGURED,
        ).as_dict(),
    }
    return _live_row_envelope(
        symbol, fields, collected, bar_count=len(bars), event_time=event_time,
        freshness=freshness, data_mode=DataMode.HISTORICAL, age_seconds=age,
    )


def _live_row_envelope(
    symbol: str,
    fields: dict[str, Any],
    collected: dict[str, Any],
    *,
    bar_count: int,
    event_time: str | None,
    freshness: Freshness,
    data_mode: DataMode,
    age_seconds: float | None = None,
) -> dict[str, Any]:
    total = 25
    return {
        "symbol": symbol,
        "case_id": None,
        "candidate_id": None,
        "data_mode": str(data_mode),
        "mode_label": "CURRENT — READ-ONLY PROVIDER DATA (NOT ADMISSIBILITY-GATED)",
        "fields": fields,
        "phase3a": {
            "counts": {"PASS": 0, "FAIL": 0, "UNKNOWN": total},
            "total_rules": total,
            "summary": f"0 PASS / 0 FAIL / {total} UNKNOWN",
            "not_published_reason": LIVE_RULES_NOT_PUBLISHED_REASON,
        },
        "research_detection": {
            "status": "UNEVALUABLE",
            "reasons": [LIVE_RULES_NOT_PUBLISHED_REASON],
            "preview_banner": None,
        },
        "outcome": {
            "status": "INCOMPLETE",
            "reasons": [
                "No forward outcome window exists for a current observation, by construction."
            ],
        },
        "evidence_coverage": {
            "supported": 0,
            "total": total,
            "label": f"0 / {total} rules supported",
        },
        "freshness": str(freshness),
        "age_seconds": None if age_seconds is None else round(age_seconds, 1),
        "last_updated": event_time,
        "retrieved_at": collected.get("retrieved_at"),
        "bar_count": bar_count,
        "provider": "IBKR",
        "provider_errors": collected.get("provider_errors", []),
        "global_preflight_status": "PREFLIGHT_REJECTED",
    }


def live_rule_table() -> list[dict[str, Any]]:
    """All 25 rules, all UNKNOWN, each stating the same honest reason."""
    from .frozen import FrozenLayout, FrozenResearchSource

    try:
        source = FrozenResearchSource(FrozenLayout())
        rule_ids = source.canonical_rule_order
        categories = {
            rule_id: entry["category"] for rule_id, entry in source.rule_matrix.items()
        }
    except Exception:  # noqa: BLE001 - frozen artifacts absent is not a live-mode failure
        return []
    return [
        {
            "rule_id": rule_id,
            "rule_version": None,
            "category": categories.get(rule_id, "UNKNOWN"),
            "outcome": "UNKNOWN",
            "observed_value": None,
            "observed_unit": None,
            "observed_display": "—",
            "threshold": "—",
            "evidence_ids": [],
            "evidence_display": "—",
            "explanation_code": LIVE_RULES_NOT_PUBLISHED_CODE,
            "reason": LIVE_RULES_NOT_PUBLISHED_REASON,
            "blocking_reason_codes": [LIVE_RULES_NOT_PUBLISHED_CODE],
            "batch07_admissibility_status": "NOT_ASSESSED",
            "quality_state": "UNAVAILABLE",
        }
        for rule_id in rule_ids
    ]


__all__ = [
    "FRESH_WITHIN_S",
    "LIVE_RULES_NOT_PUBLISHED_CODE",
    "LIVE_RULES_NOT_PUBLISHED_REASON",
    "STALE_AFTER_S",
    "InvalidSymbolError",
    "LiveBar",
    "LiveModeUnavailable",
    "LiveSource",
    "build_live_row",
    "classify_freshness",
    "live_rule_table",
    "normalize_symbol",
]
