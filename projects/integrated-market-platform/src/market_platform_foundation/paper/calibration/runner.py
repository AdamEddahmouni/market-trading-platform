"""Fail-closed IMP simulator vs external Paper calibration campaign runner.

Does not fabricate empirical fills. Does not place Live orders. Does not
declare FTEP EMPIRICAL_ACTIVE or CALIBRATED. When credentials are missing the
status is COMPARATOR_NOT_CONFIGURED. When the eligible session is closed the
status is WAITING_FOR_MARKET.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from ...execution.simulator import SIMULATOR_VERSION
from ...intelligence.paper_forward_bridge.paper_handoff import (
    forward_test_correlation_id,
)
from ...intelligence.paper_forward_bridge.repository import ForwardTestRepository
from ...intelligence.paper_forward_bridge.session_policy import is_within_us_equity_rth
from ...intelligence.paper_forward_bridge.types import ForwardTestDecision
from ...market_sessions import us_equity_session_label
from ...providers.adapters.alpaca_paper_http import ALPACA_LIVE_HOST, ALPACA_PAPER_ORIGIN
from .asset_scope import (
    EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
    assert_calibration_unit_asset_scope,
    equity_es_firewall_payload,
)
from .comparator_contract import (
    ComparatorContractError,
    ExternalPaperComparatorBinding,
    validate_comparator_binding,
)
from .metrics import CalibrationMetricReport, compute_calibration_metric_report
from .pairing import pair_imp_and_comparator
from .persistence import persist_pairing_result, persist_run_status

STATUS_COMPARATOR_NOT_CONFIGURED = "COMPARATOR_NOT_CONFIGURED"
STATUS_WAITING_FOR_MARKET = "WAITING_FOR_MARKET"
STATUS_HARNESS_READY = "HARNESS_READY"
STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"
STATUS_ENVIRONMENT_AMBIGUOUS = "ENVIRONMENT_AMBIGUOUS"

_TRADIER_GATES = (
    "IMP_TRADIER_PAPER",
    "IMP_BROKER_PAPER_EXECUTION",
    "IMP_TRADIER_TOKEN",
)
_ALPACA_GATES = (
    "IMP_ALPACA_PAPER",
    "IMP_BROKER_PAPER_EXECUTION",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
)


@dataclass(frozen=True, slots=True)
class CalibrationRunResult:
    status: str
    correlation_id: str | None
    simulator_version: str
    pair_count: int
    metrics: CalibrationMetricReport | None
    observation_label: str
    equity_paper_does_not_validate_es: str
    calibrated: bool
    empirical_active: bool
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "correlation_id": self.correlation_id,
            "simulator_version": self.simulator_version,
            "pair_count": self.pair_count,
            "metrics": self.metrics.to_dict() if self.metrics is not None else None,
            "observation_label": self.observation_label,
            "equity_paper_does_not_validate_es": self.equity_paper_does_not_validate_es,
            "calibrated": False,
            "empirical_active": False,
            "detail": dict(self.detail),
            **equity_es_firewall_payload(),
        }


def tradier_sandbox_configured(env: Mapping[str, str]) -> bool:
    if env.get("IMP_TRADIER_PAPER") != "1":
        return False
    if env.get("IMP_BROKER_PAPER_EXECUTION") != "1":
        return False
    if not str(env.get("IMP_TRADIER_TOKEN") or "").strip():
        return False
    endpoint = env.get("IMP_TRADIER_ENDPOINT") or "https://sandbox.tradier.com/v1"
    if endpoint != "https://sandbox.tradier.com/v1":
        return False
    return True


def _alpaca_base_url(env: Mapping[str, str]) -> str:
    return str(env.get("APCA_API_BASE_URL") or env.get("ALPACA_BASE_URL") or "").strip()


def _hostname(url: str) -> str:
    if not url:
        return ""
    return (urlparse(url).hostname or "").lower()


def alpaca_paper_configured(env: Mapping[str, str]) -> bool:
    if env.get("IMP_ALPACA_PAPER") != "1":
        return False
    if env.get("IMP_BROKER_PAPER_EXECUTION") != "1":
        return False
    if not str(env.get("APCA_API_KEY_ID") or "").strip():
        return False
    if not str(env.get("APCA_API_SECRET_KEY") or "").strip():
        return False
    url = _alpaca_base_url(env) or ALPACA_PAPER_ORIGIN
    parsed = urlparse(url)
    if parsed.hostname != "paper-api.alpaca.markets":
        return False
    if parsed.scheme != "https":
        return False
    path = (parsed.path or "").rstrip("/")
    if path not in ("", "/v2"):
        return False
    return True


def classify_calibration_run(
    *,
    env: Mapping[str, str],
    now_ns: int,
    requested_mode: str = "PAPER",
    session_label: str | None = None,
) -> str:
    if str(requested_mode).upper() == "LIVE":
        return STATUS_LIVE_FORBIDDEN
    endpoint = str(env.get("IMP_TRADIER_ENDPOINT") or "")
    if endpoint and endpoint != "https://sandbox.tradier.com/v1":
        return STATUS_ENVIRONMENT_AMBIGUOUS
    alpaca_url = _alpaca_base_url(env)
    if alpaca_url:
        host = _hostname(alpaca_url)
        if host == ALPACA_LIVE_HOST:
            return STATUS_LIVE_FORBIDDEN
        if host and host != "paper-api.alpaca.markets":
            return STATUS_ENVIRONMENT_AMBIGUOUS
    tradier_ok = tradier_sandbox_configured(env)
    alpaca_ok = alpaca_paper_configured(env)
    if tradier_ok and alpaca_ok:
        return STATUS_ENVIRONMENT_AMBIGUOUS
    if not tradier_ok and not alpaca_ok:
        return STATUS_COMPARATOR_NOT_CONFIGURED
    label = session_label if session_label is not None else us_equity_session_label(
        datetime.fromtimestamp(now_ns / 1_000_000_000)
    )
    if label != "REGULAR" and not is_within_us_equity_rth(now_ns):
        return STATUS_WAITING_FOR_MARKET
    return STATUS_HARNESS_READY


def _empty_result(
    *,
    status: str,
    correlation_id: str | None,
    detail: dict[str, Any],
    observation_label: str,
) -> CalibrationRunResult:
    metrics = compute_calibration_metric_report(imp_fills=(), comparator_fills=())
    return CalibrationRunResult(
        status=status,
        correlation_id=correlation_id,
        simulator_version=SIMULATOR_VERSION,
        pair_count=0,
        metrics=metrics,
        observation_label=observation_label,
        equity_paper_does_not_validate_es=EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
        calibrated=False,
        empirical_active=False,
        detail=detail,
    )


def run_calibration_campaign(
    *,
    env: Mapping[str, str],
    now_ns: int,
    decision: ForwardTestDecision | None = None,
    repository: ForwardTestRepository | None = None,
    comparator_payload: Mapping[str, Any] | None = None,
    imp_fills: Sequence[Mapping[str, Any]] = (),
    comparator_fills: Sequence[Mapping[str, Any]] = (),
    pairing_table: Sequence[Mapping[str, Any]] = (),
    requested_mode: str = "PAPER",
    session_label: str | None = None,
    place_orders: bool = False,
) -> CalibrationRunResult:
    """Classify and optionally score a paired calibration unit.

    Never fabricates comparator fills. ``place_orders`` is refused unless the
    run is HARNESS_READY on the sandbox; this runner still does not submit
    Live or production orders.
    """
    del place_orders  # orders are never placed by this classifier; fail closed
    correlation_id = (
        forward_test_correlation_id(decision.forward_test_id) if decision is not None else None
    )
    if decision is not None:
        assert_calibration_unit_asset_scope(
            asset_class=str((decision.decision_payload or {}).get("asset_class") or "EQUITY"),
            instrument_id=decision.symbol,
            comparator_id=str((comparator_payload or {}).get("comparator_id") or "tradier"),
        )
    status = classify_calibration_run(
        env=env,
        now_ns=now_ns,
        requested_mode=requested_mode,
        session_label=session_label,
    )
    detail = {
        "requested_mode": requested_mode,
        "tradier_gates": {name: bool(env.get(name)) for name in _TRADIER_GATES},
        "alpaca_gates": {name: bool(env.get(name)) for name in _ALPACA_GATES},
        "orders_placed": False,
        "fabricated_fills": False,
    }
    if status != STATUS_HARNESS_READY:
        if status in {STATUS_WAITING_FOR_MARKET, STATUS_COMPARATOR_NOT_CONFIGURED}:
            label = status
        else:
            label = "NOT_OBSERVABLE"
        if decision is not None and repository is not None:
            persist_run_status(
                repository,
                decision=decision,
                status=status,
                detail=detail,
                observed_at_ns=now_ns,
            )
        return _empty_result(
            status=status,
            correlation_id=correlation_id,
            detail=detail,
            observation_label=label,
        )

    if decision is None:
        return _empty_result(
            status=status,
            correlation_id=None,
            detail=detail,
            observation_label="NOT_OBSERVABLE",
        )

    try:
        default_payload: dict[str, Any]
        if alpaca_paper_configured(env):
            default_payload = {
                "comparator_id": "alpaca.paper",
                "environment": ALPACA_PAPER_ORIGIN,
                "account_mode": "paper",
                "limitations": [
                    "equity_only",
                    EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
                    "alpaca_paper_host",
                ],
            }
        else:
            default_payload = {
                "comparator_id": "tradier",
                "environment": "https://sandbox.tradier.com/v1",
                "account_mode": "paper",
                "limitations": [
                    "equity_only",
                    EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
                    "sandbox_delayed_l1",
                ],
            }
        binding = validate_comparator_binding(comparator_payload or default_payload)
    except ComparatorContractError as exc:
        return _empty_result(
            status=STATUS_ENVIRONMENT_AMBIGUOUS,
            correlation_id=correlation_id,
            detail={**detail, "reason": str(exc)},
            observation_label="NOT_OBSERVABLE",
        )

    pairing = pair_imp_and_comparator(
        forward_test_id=decision.forward_test_id,
        imp_fills=imp_fills,
        comparator_fills=comparator_fills,
        pairing_table=pairing_table,
        paper_account_id=decision.account_id,
        instrument_id=decision.symbol,
        asset_class=str((decision.decision_payload or {}).get("asset_class") or "EQUITY"),
    )
    if not pairing.pairs:
        if repository is not None:
            persist_run_status(
                repository,
                decision=decision,
                status=status,
                detail={**detail, "pair_count": 0},
                observed_at_ns=now_ns,
            )
        return _empty_result(
            status=status,
            correlation_id=correlation_id,
            detail={**detail, "pair_count": 0},
            observation_label="NOT_OBSERVABLE",
        )

    metrics = compute_calibration_metric_report(
        imp_fills=[pair.imp.to_dict() for pair in pairing.pairs],
        comparator_fills=[pair.comparator.to_dict() for pair in pairing.pairs],
        unpaired_imp_count=len(pairing.unpaired_imp),
        unpaired_comparator_count=len(pairing.unpaired_comparator),
    )
    if repository is not None:
        persist_pairing_result(
            repository,
            decision=decision,
            pairing=pairing,
            comparator=binding,
            evidence_class="SOFTWARE_FIXTURE_ONLY",
            observation_label="FIXTURE_BACKED_NOT_PROSPECTIVE",
            observed_at_ns=now_ns,
        )
    return CalibrationRunResult(
        status=status,
        correlation_id=correlation_id,
        simulator_version=SIMULATOR_VERSION,
        pair_count=pairing.pair_count,
        metrics=metrics,
        observation_label="FIXTURE_BACKED_NOT_PROSPECTIVE",
        equity_paper_does_not_validate_es=EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
        calibrated=False,
        empirical_active=False,
        detail={**detail, "pair_count": pairing.pair_count},
    )


__all__ = [
    "STATUS_COMPARATOR_NOT_CONFIGURED",
    "STATUS_ENVIRONMENT_AMBIGUOUS",
    "STATUS_HARNESS_READY",
    "STATUS_LIVE_FORBIDDEN",
    "STATUS_WAITING_FOR_MARKET",
    "CalibrationRunResult",
    "alpaca_paper_configured",
    "classify_calibration_run",
    "run_calibration_campaign",
    "tradier_sandbox_configured",
]
