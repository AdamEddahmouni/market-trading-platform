"""G2/G3 handoff for ranked opportunities.

Ranking orders operator review. It is not risk authority. This boundary
consumes a ranked opportunity as payload, evaluates G3 ``evaluate_pretrade``
and optional G2 book-exposure limits, and never grants Live execution.
It does not mutate the book, submit orders, or rank candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..portfolio.canonical import CanonicalPortfolio
from .book_exposure import BookLimitPolicy, BookExposureReport, aggregate_book_exposure
from .decision import REJECT_KILL_SWITCH
from .kill_switch import KillSwitchState
from .pretrade import PreTradeRiskContext, RiskDecision, evaluate_pretrade

HANDOFF_AUTHORITY = "G2_G3_RISK_NOT_RANKING"
HANDOFF_IDENTITY_MISMATCH = "HANDOFF_IDENTITY_MISMATCH"
LIVE_OBSERVATIONAL_NO_EXECUTION = "LIVE_OBSERVATIONAL_NO_EXECUTION"

RANKING_PAYLOAD_KEYS = frozenset(
    {
        "rank_order",
        "rank_score",
        "ranking_vector",
        "ranking",
        "provisional_rank_score",
    }
)


@dataclass(frozen=True, slots=True)
class RankedOpportunityIntent:
    """Ranked opportunity payload. Ranking fields are observational only."""

    opportunity_id: str
    instrument_id: str
    account_id: str
    mode: str
    side: str
    quantity: int
    rank_order: int | None = None
    rank_score: float | None = None
    ranking_vector: object | None = None


@dataclass(frozen=True, slots=True)
class RiskHandoffReport:
    """Authoritative G2/G3 decision. Must not carry ranking fields."""

    authority: str
    accepted: bool
    decision: str
    reason_codes: tuple[str, ...]
    pretrade: RiskDecision
    book_exposure: BookExposureReport | None = None
    kill_switch_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "authority": self.authority,
            "accepted": self.accepted,
            "decision": self.decision,
            "reason_codes": list(self.reason_codes),
            "kill_switch_active": self.kill_switch_active,
            "pretrade": {
                "accepted": self.pretrade.accepted,
                "decision": self.pretrade.decision,
                "reason_codes": list(self.pretrade.reason_codes),
                "required_cash_minor": self.pretrade.required_cash_minor,
                "available_cash_minor": self.pretrade.available_cash_minor,
            },
        }
        if self.book_exposure is not None:
            body["book_exposure"] = {
                "status": self.book_exposure.status,
                "within_limits": self.book_exposure.within_limits,
                "limit_breaches": list(self.book_exposure.limit_breaches),
                "reason_codes": list(self.book_exposure.reason_codes),
            }
        leaked = RANKING_PAYLOAD_KEYS.intersection(body)
        if leaked:
            raise RuntimeError("RANKING_LEAKED_INTO_RISK")
        return body


def _filled_mismatch(left: str, right: str) -> bool:
    a = str(left or "").strip()
    b = str(right or "").strip()
    if not a or not b:
        return False
    return a.upper() != b.upper()


def _side_to_pretrade(side: str | None) -> str:
    value = str(side or "").strip().upper()
    if value in {"SHORT", "SELL"}:
        return "SELL"
    return "BUY"


def intent_from_ranked_summary(summary: Any, *, quantity: int) -> RankedOpportunityIntent:
    """Lift operator ranking payload into a risk intent. Quantity is explicit."""

    return RankedOpportunityIntent(
        opportunity_id=str(getattr(summary, "opportunity_id", None) or summary.summary_id),
        instrument_id=str(summary.instrument_id),
        account_id=str(getattr(summary, "account_id", None) or ""),
        mode=str(getattr(summary, "mode", None) or ""),
        side=_side_to_pretrade(getattr(summary, "side", None)),
        quantity=int(quantity),
        rank_order=getattr(summary, "rank_order", None),
        rank_score=getattr(summary, "rank_score", None),
        ranking_vector=getattr(summary, "ranking_vector", None),
    )


def evaluate_ranked_opportunity_handoff(
    intent: RankedOpportunityIntent,
    *,
    context: PreTradeRiskContext,
    kill_switch: KillSwitchState | None = None,
    portfolio: CanonicalPortfolio | None = None,
    book_policy: BookLimitPolicy | None = None,
) -> RiskHandoffReport:
    """Evaluate a ranked opportunity against G3 pretrade and G2 book limits.

    ``intent.rank_order`` / ``rank_score`` / ``ranking_vector`` are ignored.
    Live mode is observational: pretrade may accept, the handoff never does.
    """

    halt = kill_switch if kill_switch is not None else KillSwitchState(active=False)
    reasons: list[str] = []

    if (
        _filled_mismatch(intent.instrument_id, context.instrument_id)
        or _filled_mismatch(intent.account_id, context.account_id)
        or _filled_mismatch(intent.mode, context.mode)
    ):
        reasons.append(HANDOFF_IDENTITY_MISMATCH)

    pretrade = evaluate_pretrade(context)
    if not pretrade.accepted:
        reasons.extend(code for code in pretrade.reason_codes if code not in reasons)

    if halt.active:
        reasons.append(REJECT_KILL_SWITCH)

    mode = str(intent.mode or context.mode).strip().upper()
    if mode == "LIVE":
        reasons.append(LIVE_OBSERVATIONAL_NO_EXECUTION)

    book_report: BookExposureReport | None = None
    if portfolio is not None:
        book_report = aggregate_book_exposure(portfolio, policy=book_policy)
        if not book_report.within_limits:
            extra = book_report.limit_breaches or book_report.reason_codes
            reasons.extend(code for code in extra if code not in reasons)

    unique = tuple(dict.fromkeys(reasons))
    accepted = not unique
    return RiskHandoffReport(
        authority=HANDOFF_AUTHORITY,
        accepted=accepted,
        decision="APPROVE" if accepted else "REJECT",
        reason_codes=unique,
        pretrade=pretrade,
        book_exposure=book_report,
        kill_switch_active=halt.active,
    )


__all__ = [
    "HANDOFF_AUTHORITY",
    "HANDOFF_IDENTITY_MISMATCH",
    "LIVE_OBSERVATIONAL_NO_EXECUTION",
    "RANKING_PAYLOAD_KEYS",
    "RankedOpportunityIntent",
    "RiskHandoffReport",
    "evaluate_ranked_opportunity_handoff",
    "intent_from_ranked_summary",
]
