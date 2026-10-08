"""UI API route capability and account-scope policy (TD-005)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from ...operational_identity import OperationalIdentity, derive_paper_identity
from ...ui_api.account_registry import resolve_operational_account, resolve_paper_portfolio_identity
from ...ui_api.store import ReplayStore


class AccountScopeKind(str, Enum):
    NONE = "NONE"
    QUERY_ACCOUNT_ID = "QUERY_ACCOUNT_ID"
    PAPER_PORTFOLIO = "PAPER_PORTFOLIO"
    PAPER_LEDGER = "PAPER_LEDGER"
    CANARY_COMMAND = "CANARY_COMMAND"


@dataclass(frozen=True)
class RoutePolicy:
    capability: str | None
    account_scope: AccountScopeKind = AccountScopeKind.NONE
    public_in_enforced_mode: bool = False


CANARY_ADMIN_COMMANDS = frozenset(
    {
        "authorize_session",
        "revoke_authorization",
        "acknowledge_incident",
        "resolve_incident",
        "record_resume_approval",
    }
)


def policy_for_route(method: str, path: str) -> RoutePolicy:
    method_upper = method.upper()
    if path == "/auth/login" or path == "/auth/status":
        return RoutePolicy(capability=None, public_in_enforced_mode=True)
    if path == "/auth/logout" or path == "/auth/session":
        return RoutePolicy(capability=None)
    if path == "/security/readiness":
        return RoutePolicy(capability="security.config.read")

    if path.startswith("/evaluation/prospective/"):
        # Evaluation artifacts have state-write authority only; never order authority.
        return RoutePolicy(capability="audit.read" if method_upper == "GET" or path.endswith("/rerun") else "state.write",
                           account_scope=AccountScopeKind.PAPER_LEDGER)
    if path == "/screener/action-decisions" and method_upper == "GET":
        return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path == "/screener/action-decision/preview" and method_upper == "POST":
        return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path == "/screener/action-decision/run" and method_upper == "POST":
        return RoutePolicy(capability="state.write", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path == "/screener/action-decision/handoff" and method_upper == "POST":
        return RoutePolicy(capability="paper.order.submit", account_scope=AccountScopeKind.PAPER_LEDGER)
    if (path == "/screener/trade-lifecycles" or path.startswith("/screener/trade-lifecycles/")) and method_upper == "GET":
        # OCT1-10 derived read model over the Paper ledger and decision records. Read only.
        return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path in ("/screener/next-session", "/screener/reevaluation/status", "/screener/reevaluation/history") and method_upper == "GET":
        return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path in ("/screener/next-session/draft", "/screener/next-session/lock", "/screener/next-session/observe",
                "/screener/next-session/evaluate", "/screener/reevaluation/configure", "/screener/reevaluation/start",
                "/screener/reevaluation/stop", "/screener/reevaluation/run-once") and method_upper == "POST":
        # Decision cadence only: none of these carries paper.order.submit.
        return RoutePolicy(capability="state.write", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path in ("/paper/risk-control/sma-stop", "/paper/risk-control/sma-stop/history", "/paper/risk-control/sma-stop/config",
                "/paper/risk-control/sma-stop/evaluation") and method_upper == "GET":
        return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
    if path in ("/paper/risk-control/sma-stop/configure", "/paper/risk-control/sma-stop/evaluate") and method_upper == "POST":
        # Stop monitor only: neither route carries paper.order.submit.
        return RoutePolicy(capability="state.write", account_scope=AccountScopeKind.PAPER_LEDGER)
    if method_upper == "GET":
        if path in {
            "/context",
            "/capabilities",
            "/attention",
            "/replay/session",
            "/state/startup",
            "/operator/state",
            "/operator/investigations",
            "/operator/readiness",
            "/operator/config",
            "/operator/diagnostics",
            "/operator/lifecycle/status",
            "/accounts",
            "/assistant/status",
            "/provider/health",
            "/provider/finviz/health",
            "/discover/screens",
            "/discover/run",
            "/discover/mixed",
            "/symbols/search",
            "/explore/futures",
            "/explore/squeeze/scanner",
            "/research/analytics",
            "/research/models",
            "/research/simulation",
        }:
            return RoutePolicy(capability="state.read")
        if path.startswith("/instruments/") or path.startswith("/market-state/"):
            return RoutePolicy(capability="state.read")
        if path.startswith("/operator/lifecycle/operations/"):
            return RoutePolicy(capability="state.read")
        if path.startswith("/operator/investigations/"):
            return RoutePolicy(capability="state.read")
        if path.startswith("/workspace/") or path.startswith("/explain/") or path.startswith("/inspect/"):
            return RoutePolicy(capability="state.read")
        if path == "/paper/account" or path == "/paper/positions" or path == "/paper/risk":
            return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/portfolio" or path == "/paper/order-history":
            return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.PAPER_PORTFOLIO)
        if path == "/paper/sessions":
            return RoutePolicy(capability="state.read")
        if path in {"/paper/trades", "/paper/equity-history"} or path == "/paper/experiments" or path.startswith("/paper/experiments/"):
            return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.PAPER_PORTFOLIO)
        if path == "/paper/trace":
            return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/strategy-profitability":
            return RoutePolicy(capability="audit.read", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/captures":
            return RoutePolicy(capability="audit.read")
        if path.startswith("/assistant/conversations"):
            return RoutePolicy(capability="state.read")
        if path == "/screener/ai-screener/preview" or path.startswith("/screener/ai-screener/runs/"):
            # Preview and run status are reads: neither starts a run nor calls a model.
            return RoutePolicy(capability="state.read")
        if path == "/canary/snapshot" or path == "/canary/reconciliation":
            return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.QUERY_ACCOUNT_ID)
        if path.startswith("/canary/"):
            return RoutePolicy(capability="state.read")
        if path == "/broker/snapshot":
            return RoutePolicy(capability="state.read", account_scope=AccountScopeKind.QUERY_ACCOUNT_ID)

    if method_upper == "POST":
        if path == "/screener/config":
            return RoutePolicy(capability="state.write")
        if path.startswith("/screener/providers/") and path.endswith("/connect"):
            # Operator-initiated start of an allowlisted local provider process; never a render-time read.
            return RoutePolicy(capability="state.write")
        if path == "/screener/news/synthesis":
            # Operator-initiated model call (paid API or on-demand local model); never a render-time read.
            return RoutePolicy(capability="state.write")
        if path == "/screener/ai-screener":
            # Explicit candidate reduction is a bounded inference action, never a render-time read.
            return RoutePolicy(capability="state.write")
        if path.startswith("/screener/ai-screener/runs/") and path.endswith("/stop"):
            # Operator Stop of this account's own run: it prevents further model calls and grants nothing.
            return RoutePolicy(capability="state.write")
        if path == "/screener/news/synthesis/engine":
            # Operator choice of synthesis engine and model, saved in the IMP cache; calls no model.
            return RoutePolicy(capability="state.write")
        if path == "/paper/orders/preview":
            return RoutePolicy(capability="paper.order.submit", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/orders":
            return RoutePolicy(capability="paper.order.submit", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/orders/cancel":
            return RoutePolicy(capability="paper.order.cancel", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/sessions" or path == "/paper/sessions/close":
            return RoutePolicy(capability="state.write", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path == "/paper/experiments" or (path.startswith("/paper/experiments/") and path.endswith("/close")):
            return RoutePolicy(capability="state.write", account_scope=AccountScopeKind.PAPER_LEDGER)
        if path.startswith("/operator/"):
            if path == "/operator/config/provider":
                return RoutePolicy(capability="security.config.write")
            if path.startswith("/operator/providers/") and path.endswith("/refresh"):
                return RoutePolicy(capability="state.write")
            if path == "/operator/lifecycle/actions":
                return RoutePolicy(capability="operator.lifecycle.write")
            return RoutePolicy(capability="state.write")
        if path == "/captures/replay":
            return RoutePolicy(capability="state.write")
        if path == "/replay/scrub":
            return RoutePolicy(capability="state.write")
        if path == "/controlled-replay/advance-clock":
            return RoutePolicy(capability="state.write")
        if path == "/canary/command":
            return RoutePolicy(capability=None, account_scope=AccountScopeKind.CANARY_COMMAND)
        if path.startswith("/assistant/conversations"):
            return RoutePolicy(capability="state.write")
        if path in {"/discover/mixed/refresh", "/discover/mixed/release", "/discover/promote-to-live-analysis"}:
            return RoutePolicy(capability="state.write")
        if path in {"/subscriptions", "/subscriptions/release"}:
            return RoutePolicy(capability="state.write")
        if path == "/intelligence/ingest/enrichment" or path.startswith("/intelligence/ingest/enrichment/"):
            return RoutePolicy(capability="intelligence.ingest.write")

    if method_upper == "PUT":
        if path.startswith("/intelligence/ingest/enrichment/"):
            return RoutePolicy(capability="intelligence.ingest.write")

    return RoutePolicy(capability="state.read")


def resolve_account_scope(
    store: ReplayStore,
    scope: AccountScopeKind,
    *,
    query: Mapping[str, list[str]],
    body: dict[str, Any] | None = None,
) -> OperationalIdentity | None:
    if scope == AccountScopeKind.NONE:
        return None
    if scope == AccountScopeKind.QUERY_ACCOUNT_ID:
        account_id = (query.get("account_id") or [None])[0]
        if not account_id:
            return None
        return resolve_operational_account(store, account_id=str(account_id))
    if scope == AccountScopeKind.PAPER_PORTFOLIO:
        view_mode = (query.get("view_mode") or ["PAPER"])[0]
        return resolve_paper_portfolio_identity(store, view_mode=str(view_mode))
    if scope == AccountScopeKind.PAPER_LEDGER:
        ledger = store.paper_ledger
        if not ledger.events:
            return None
        return derive_paper_identity(
            paper_account_id=ledger.paper_account_id,
            execution_provider=ledger.execution_provider,
            data_mode=ledger.data_mode,
        )
    if scope == AccountScopeKind.CANARY_COMMAND and body is not None:
        command = str(body.get("command", "")).strip()
        account_id = body.get("account_id")
        if account_id:
            return resolve_operational_account(store, account_id=str(account_id))
        if command in CANARY_ADMIN_COMMANDS:
            return None
    return None


def capability_for_canary_command(body: dict[str, Any]) -> str:
    command = str(body.get("command", "")).strip()
    if command in CANARY_ADMIN_COMMANDS:
        return "role.manage"
    if command in {"confirm_order", "prepare_session_authorization"}:
        return "paper.order.submit"
    return "state.write"
